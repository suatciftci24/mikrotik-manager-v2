"""Private, re-encoded subscriber photos for the isolated V2.6 acceptance profile."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
from threading import RLock

from PIL import Image, ImageOps


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_THUMB_BYTES = 1024 * 1024
MAX_PIXELS = 24_000_000
MAX_DIMENSION = 8_000
MAX_PHOTOS_PER_SUBSCRIBER = 20
PHOTO_ID = re.compile(r"^[0-9a-f]{32}$")
SUBSCRIBER_ID = re.compile(r"^demo-(?:managed-)?sub-[A-Za-z0-9-]{1,64}$")


class PhotoError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _safe_identity(subscriber_id: str, source: str, access_type: str) -> None:
    if not isinstance(subscriber_id, str) or not SUBSCRIBER_ID.fullmatch(subscriber_id):
        raise PhotoError(404, "Sentetik abone bulunamadı.")
    if source not in ("LOCAL", "RADIUS") or access_type not in ("PPPOE", "HOTSPOT"):
        raise PhotoError(409, "Abonenin yetkili kaynak veya erişim türü doğrulanamadı.")


class SubscriberPhotoStore:
    """One generated-file namespace per validated subscriber; no user filenames."""

    _lock = RLock()

    def __init__(self, root: Path | str | None = None):
        self._test_root = Path(root) if root is not None else None

    def _root(self) -> Path:
        if self._test_root is not None:
            root = self._test_root
        else:
            from app.core import v26_acceptance
            if os.environ.get("V2_DEPLOYMENT_PROFILE") != v26_acceptance.PROFILE:
                raise PhotoError(404, "Fotoğraf alanı yalnız V2.6 izole kabul ortamında kullanılabilir.")
            try:
                v26_acceptance.validate(root=v26_acceptance.ROOT)
            except RuntimeError:
                raise PhotoError(404, "V2.6 izole kabul yapılandırması doğrulanamadı.") from None
            root = v26_acceptance.ROOT / "subscriber-photos"
            try:
                if v26_acceptance.ROOT.resolve(strict=True) != Path("/tmp/mikrotik-v26-acceptance"):
                    raise PhotoError(503, "V2.6 fotoğraf alanı doğrulanamadı.")
            except OSError:
                raise PhotoError(503, "V2.6 fotoğraf alanı hazır değil.") from None
        try:
            root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if root.parent.is_symlink() or not root.parent.is_dir():
                raise PhotoError(503, "Fotoğraf alanı doğrulanamadı.")
            root.mkdir(mode=0o700, exist_ok=True)
            info = root.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise PhotoError(503, "Fotoğraf alanı izinleri güvenli değil.")
            return root
        except PhotoError:
            raise
        except OSError:
            raise PhotoError(503, "İzole fotoğraf alanına erişilemiyor.") from None

    @staticmethod
    def _directory(root: Path, subscriber_id: str, create: bool) -> Path:
        digest = sha256(subscriber_id.encode("utf-8")).hexdigest()
        directory = root / digest
        try:
            if create:
                directory.mkdir(mode=0o700, exist_ok=True)
            info = directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise PhotoError(503, "Abone fotoğraf alanı güvenli değil.")
            return directory
        except FileNotFoundError:
            return directory
        except PhotoError:
            raise
        except OSError:
            raise PhotoError(503, "Abone fotoğraf alanına erişilemiyor.") from None

    @staticmethod
    def _paths(directory: Path, photo_id: str) -> tuple[Path, Path, Path]:
        if not PHOTO_ID.fullmatch(photo_id):
            raise PhotoError(404, "Fotoğraf bulunamadı.")
        return directory / (photo_id + ".jpg"), directory / (photo_id + ".thumb.jpg"), directory / (photo_id + ".json")

    @staticmethod
    def _clean_images(data: bytes) -> tuple[bytes, bytes]:
        try:
            with Image.open(BytesIO(data)) as check:
                image_format = check.format
                width, height = check.size
                frames = getattr(check, "n_frames", 1)
                if image_format not in ("JPEG", "PNG"):
                    raise PhotoError(415, "Yalnız JPEG veya PNG görüntüsü kabul edilir.")
                if width < 1 or height < 1 or width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_PIXELS:
                    raise PhotoError(413, "Görüntü boyut veya piksel sınırını aşıyor.")
                if frames != 1:
                    raise PhotoError(415, "Hareketli veya çok kareli görüntüler kabul edilmez.")
                check.verify()
            with Image.open(BytesIO(data)) as opened:
                image = ImageOps.exif_transpose(opened)
                image.load()
                if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                    image = Image.alpha_composite(background, rgba).convert("RGB")
                else:
                    image = image.convert("RGB")
                full = BytesIO()
                image.save(full, format="JPEG", quality=85, optimize=True, progressive=True)
                if not full.tell() or full.tell() > MAX_OUTPUT_BYTES:
                    raise PhotoError(413, "Güvenli görüntü boyutu sınırı aşıldı.")
                thumb_image = image.copy()
                thumb_image.thumbnail((640, 640), Image.Resampling.LANCZOS)
                thumb = BytesIO()
                thumb_image.save(thumb, format="JPEG", quality=78, optimize=True, progressive=True)
                if not thumb.tell() or thumb.tell() > MAX_THUMB_BYTES:
                    raise PhotoError(413, "Önizleme boyutu sınırı aşıldı.")
                return full.getvalue(), thumb.getvalue()
        except PhotoError:
            raise
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
            raise PhotoError(415, "Dosya geçerli ve okunabilir bir JPEG/PNG görüntüsü değil.") from None

    @staticmethod
    def _atomic_write(directory: Path, destination: Path, data: bytes) -> None:
        fd, temporary = tempfile.mkstemp(prefix=".upload-", dir=directory)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    @staticmethod
    def _metadata(path: Path, subscriber_id: str, source: str, access_type: str) -> dict:
        try:
            if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > 4096:
                raise ValueError
            value = json.loads(path.read_text("utf-8"))
            photo_id = value["id"]
            if (not PHOTO_ID.fullmatch(photo_id) or value.get("subscriber_id") != subscriber_id
                    or path.stem != photo_id
                    or value.get("source") != source or value.get("access_type") != access_type
                    or not isinstance(value.get("created_at"), str)
                    or not isinstance(value.get("size_bytes"), int) or value["size_bytes"] < 1):
                raise ValueError
            return value
        except FileNotFoundError:
            raise PhotoError(404, "Fotoğraf bulunamadı.") from None
        except (OSError, ValueError, KeyError, TypeError):
            raise PhotoError(503, "Fotoğraf kayıt bilgisi doğrulanamadı.") from None

    def list(self, subscriber_id: str, source: str, access_type: str) -> list[dict]:
        _safe_identity(subscriber_id, source, access_type)
        root = self._root()
        directory = self._directory(root, subscriber_id, False)
        if not directory.exists():
            return []
        with self._lock:
            result = []
            for path in directory.glob("*.json"):
                meta = self._metadata(path, subscriber_id, source, access_type)
                full, thumb, _ = self._paths(directory, meta["id"])
                for image_path in (full, thumb):
                    try:
                        info = image_path.lstat()
                    except OSError:
                        raise PhotoError(503, "Fotoğraf dosyası bulunamadı.") from None
                    if not stat.S_ISREG(info.st_mode) or info.st_size < 1 or info.st_size > MAX_OUTPUT_BYTES:
                        raise PhotoError(503, "Fotoğraf dosyası doğrulanamadı.")
                result.append({"id": meta["id"], "created_at": meta["created_at"], "size_bytes": meta["size_bytes"], "media_type": "image/jpeg"})
            return sorted(result, key=lambda item: (item["created_at"], item["id"]), reverse=True)

    def add(self, subscriber_id: str, source: str, access_type: str, actor_id: str, data: bytes) -> dict:
        _safe_identity(subscriber_id, source, access_type)
        if not isinstance(data, bytes) or not data or len(data) > MAX_UPLOAD_BYTES:
            raise PhotoError(413 if data else 400, "Dosya boş veya yükleme boyutu sınırını aşıyor.")
        full, thumb = self._clean_images(data)
        root = self._root()
        directory = self._directory(root, subscriber_id, True)
        with self._lock:
            existing = self.list(subscriber_id, source, access_type)
            if len(existing) >= MAX_PHOTOS_PER_SUBSCRIBER:
                raise PhotoError(413, "Abone başına en fazla 20 fotoğraf saklanabilir.")
            photo_id = secrets.token_hex(16)
            full_path, thumb_path, meta_path = self._paths(directory, photo_id)
            metadata = {"id": photo_id, "subscriber_id": subscriber_id, "source": source, "access_type": access_type,
                        "actor_id": actor_id, "created_at": datetime.now(timezone.utc).isoformat(), "size_bytes": len(full)}
            try:
                self._atomic_write(directory, full_path, full)
                self._atomic_write(directory, thumb_path, thumb)
                self._atomic_write(directory, meta_path, json.dumps(metadata, separators=(",", ":")).encode("utf-8"))
            except OSError:
                for path in (full_path, thumb_path, meta_path):
                    try:
                        path.unlink()
                    except OSError:
                        pass
                raise PhotoError(503, "Fotoğraf güvenli biçimde kaydedilemedi.") from None
        return {"id": photo_id, "created_at": metadata["created_at"], "size_bytes": metadata["size_bytes"], "media_type": "image/jpeg"}

    def read(self, subscriber_id: str, source: str, access_type: str, photo_id: str, thumbnail: bool = False) -> bytes:
        _safe_identity(subscriber_id, source, access_type)
        directory = self._directory(self._root(), subscriber_id, False)
        full_path, thumb_path, meta_path = self._paths(directory, photo_id)
        with self._lock:
            self._metadata(meta_path, subscriber_id, source, access_type)
            image_path = thumb_path if thumbnail else full_path
            try:
                info = image_path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_size < 1 or info.st_size > MAX_OUTPUT_BYTES:
                    raise PhotoError(503, "Fotoğraf dosyası doğrulanamadı.")
                return image_path.read_bytes()
            except FileNotFoundError:
                raise PhotoError(404, "Fotoğraf bulunamadı.") from None
            except OSError:
                raise PhotoError(503, "Fotoğraf okunamadı.") from None

    def delete(self, subscriber_id: str, source: str, access_type: str, photo_id: str) -> None:
        _safe_identity(subscriber_id, source, access_type)
        directory = self._directory(self._root(), subscriber_id, False)
        full_path, thumb_path, meta_path = self._paths(directory, photo_id)
        with self._lock:
            self._metadata(meta_path, subscriber_id, source, access_type)
            try:
                for path in (full_path, thumb_path, meta_path):
                    info = path.lstat()
                    if not stat.S_ISREG(info.st_mode):
                        raise PhotoError(503, "Fotoğraf dosyası doğrulanamadı.")
                for path in (full_path, thumb_path, meta_path):
                    path.unlink()
            except FileNotFoundError:
                raise PhotoError(404, "Fotoğraf bulunamadı.") from None
            except OSError:
                raise PhotoError(503, "Fotoğraf güvenli biçimde silinemedi.") from None
