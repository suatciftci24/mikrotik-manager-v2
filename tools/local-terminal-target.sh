# Local development entry points share the Office and Home WSL identities.
is_canonical_git_origin() {
  case "${1%.git}" in
    https://github.com/suatciftci24/mikrotik-manager-v2|git@github.com:suatciftci24/mikrotik-manager-v2|ssh://git@github.com/suatciftci24/mikrotik-manager-v2) return 0 ;;
    *) return 1 ;;
  esac
}

require_local_terminal_target() {
  local root="$1" host system kernel user expected_root expected_user expected_branch origin
  if ! host="$(hostname)" || ! system="$(uname -s)" || ! kernel="$(uname -r)" ||
     ! user="$(id -un)" || [[ "$system" != Linux || "${kernel,,}" != *microsoft* ]]; then
    printf 'TERMINAL_TARGET_BLOCKED: Yerel işlem Linux Ofis veya Ev WSL terminali gerektirir.\n' >&2
    return 1
  fi

  case "$host" in
    DESKTOP-VD5T7VG)
      expected_user='suatpc'
      expected_root='/home/suatpc/v26-transfer/mikrotik-v26-next'
      expected_branch='development/v2.6.2-pppoe'
      if [[ "${2:-}" == git-transfer &&
            "$root" == '/home/suatpc/Codex-Projects/mikrotik-manager-v2' &&
            "$(git -C "$root" symbolic-ref --quiet --short HEAD 2>/dev/null)" == 'development/v2.6.18-multi-router' ]]; then
        expected_root="$root"
        expected_branch='development/v2.6.18-multi-router'
      fi
      ;;
    DESKTOP-MT2JS7H)
      expected_user='suat'
      expected_root='/home/suat/Codex-Projects/mikrotik-manager-v2'
      expected_branch='main-guncel'
      ;;
    *)
      printf 'TERMINAL_TARGET_BLOCKED: Bilinen Ofis veya Ev WSL makinesi gerekli.\n' >&2
      return 1
      ;;
  esac

  if [[ "$user" != "$expected_user" || "$root" != "$expected_root" ||
        "$(git -C "$root" rev-parse --show-toplevel 2>/dev/null)" != "$expected_root" ||
        "$(git -C "$root" symbolic-ref --quiet --short HEAD 2>/dev/null)" != "$expected_branch" ]]; then
    printf 'TERMINAL_TARGET_BLOCKED: %s@%s, %s ve %s dalı gerekli.\n' \
      "$expected_user" "$host" "$expected_root" "$expected_branch" >&2
    return 1
  fi
  origin="$(git -C "$root" config --local --get remote.origin.url 2>/dev/null || true)"
  if ! is_canonical_git_origin "$origin"; then
    printf 'TERMINAL_TARGET_BLOCKED: V2 deposunun origin kimliği doğrulanamadı.\n' >&2
    return 1
  fi
}

require_local_demo_environment() {
  PYTHONPATH="$1/backend" python3 -B -m app.core.config
}
