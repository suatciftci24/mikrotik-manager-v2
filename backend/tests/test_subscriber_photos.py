from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import os

from PIL import Image
from fastapi import HTTPException

from app.services.subscriber_photos import PhotoError, SubscriberPhotoStore


def encoded_image(fmt="PNG", size=(48, 32), **kwargs):
    image = Image.new("RGB", size, (30, 90, 140))
    output = BytesIO()
    image.save(output, format=fmt, **kwargs)
    return output.getvalue()


class SubscriberPhotoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SubscriberPhotoStore(Path(self.temp.name) / "private-photos")

    def test_jpeg_and_png_are_reencoded_without_metadata(self):
        exif = Image.Exif()
        exif[271] = "Sensitive camera make"
        for subscriber_id, source, payload in (("demo-sub-photo-local", "LOCAL", encoded_image()), ("demo-sub-photo-radius", "RADIUS", encoded_image("JPEG", exif=exif))):
            with self.subTest(source=source):
                item = self.store.add(subscriber_id, source, "PPPOE", "operator-test", payload)
                full = self.store.read(subscriber_id, source, "PPPOE", item["id"])
                thumb = self.store.read(subscriber_id, source, "PPPOE", item["id"], True)
                with Image.open(BytesIO(full)) as image:
                    self.assertEqual(image.format, "JPEG")
                    self.assertFalse(image.getexif())
                    self.assertEqual(image.size, (48, 32))
                with Image.open(BytesIO(thumb)) as image:
                    self.assertEqual(image.format, "JPEG")
                self.assertEqual(self.store.list(subscriber_id, source, "PPPOE")[0]["id"], item["id"])

    def test_rejects_untrusted_or_oversized_image_content(self):
        for payload, status in ((b"not an image", 415), (encoded_image("WEBP"), 415), (encoded_image(size=(5001, 5000)), 413)):
            with self.subTest(expected=status):
                with self.assertRaises(PhotoError) as caught:
                    self.store.add("demo-sub-photo-test", "LOCAL", "PPPOE", "operator", payload)
                self.assertEqual(caught.exception.status, status)

    def test_identity_scope_blocks_traversal_cross_subscriber_reads_and_deletes(self):
        photo = self.store.add("demo-sub-first", "LOCAL", "PPPOE", "operator", encoded_image())
        with self.assertRaises(PhotoError) as bad_id:
            self.store.list("../demo-sub-first", "LOCAL", "PPPOE")
        self.assertEqual(bad_id.exception.status, 404)
        with self.assertRaises(PhotoError) as wrong_owner:
            self.store.read("demo-sub-second", "LOCAL", "PPPOE", photo["id"])
        self.assertEqual(wrong_owner.exception.status, 404)
        with self.assertRaises(PhotoError) as wrong_source:
            self.store.read("demo-sub-first", "RADIUS", "PPPOE", photo["id"])
        self.assertEqual(wrong_source.exception.status, 503)
        self.store.delete("demo-sub-first", "LOCAL", "PPPOE", photo["id"])
        self.assertEqual(self.store.list("demo-sub-first", "LOCAL", "PPPOE"), [])

    def test_rejects_unknown_authority_and_caps_per_subscriber(self):
        with self.assertRaises(PhotoError):
            self.store.list("demo-sub-photo-test", "UNKNOWN", "PPPOE")
        payload = encoded_image()
        for _ in range(20):
            self.store.add("demo-sub-photo-test", "LOCAL", "HOTSPOT", "operator", payload)
        with self.assertRaises(PhotoError) as caught:
            self.store.add("demo-sub-photo-test", "LOCAL", "HOTSPOT", "operator", payload)
        self.assertEqual(caught.exception.status, 413)

    def test_default_demo_profile_cannot_open_photo_store(self):
        with patch.dict(os.environ, {"V2_DEPLOYMENT_PROFILE": "local-demo"}, clear=True):
            with self.assertRaises(PhotoError) as caught:
                SubscriberPhotoStore().list("demo-sub-photo-test", "LOCAL", "PPPOE")
        self.assertEqual(caught.exception.status, 404)

    def test_api_subject_uses_router_authority_and_requires_write_permission(self):
        from app.api.v1 import subscriber_center

        calls = []
        detail = {"is_demo": True, "persistence": "process-memory", "item": {
            "id": "demo-sub-photo-test", "source": "RADIUS", "access_type": "HOTSPOT",
            "router_id": "demo-router-fixture", "router_missing": False,
        }}

        def lookup(user, item_id, permission="can_view"):
            calls.append((item_id, permission))
            if permission == "can_manage_hotspot" and not user.get("manage"):
                raise HTTPException(403, "denied")
            return detail

        with patch.object(subscriber_center, "subscriber_for", lookup):
            subject = subscriber_center.photo_subject("demo-sub-photo-test", {"id": "reader"})
            self.assertEqual(subject["source"], "RADIUS")
            self.assertEqual(subject["access_type"], "HOTSPOT")
            with self.assertRaises(HTTPException) as denied:
                subscriber_center.photo_subject("demo-sub-photo-test", {"id": "reader"}, write=True)
        self.assertEqual(denied.exception.status_code, 403)
        self.assertEqual(calls, [("demo-sub-photo-test", "can_view"), ("demo-sub-photo-test", "can_view"), ("demo-sub-photo-test", "can_manage_hotspot")])


if __name__ == "__main__":
    unittest.main()
