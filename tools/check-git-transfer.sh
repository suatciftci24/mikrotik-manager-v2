#!/usr/bin/env bash
# Read-only local preflight. This script has no network or transfer mode.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "$root/tools/local-terminal-target.sh"

if [[ $# != 0 ]]; then
  printf 'GIT_TRANSFER_BLOCKED: Bu kontrol argüman almaz ve aktarım yapmaz.\n' >&2
  exit 1
fi
require_local_terminal_target "$root" git-transfer

# get-url expands insteadOf/pushInsteadOf and includes origin's explicit pushurl.
# Validate every resulting destination without printing any configured value.
if ! read_url="$(git -C "$root" remote get-url --all origin 2>/dev/null)" ||
   ! write_url="$(git -C "$root" remote get-url --push --all origin 2>/dev/null)" ||
   ! is_canonical_git_origin "$read_url" || ! is_canonical_git_origin "$write_url"; then
  printf 'GIT_TRANSFER_BLOCKED: Tekil ve doğrulanmış GitHub origin okuma/yazma hedefi gerekli.\n' >&2
  exit 1
fi

mirror_status=0
mirror="$(git -C "$root" config --bool --get-all remote.origin.mirror 2>/dev/null)" || mirror_status=$?
if [[ "$mirror_status" != 1 && ( "$mirror_status" != 0 || "$mirror" != false ) ]]; then
  printf 'GIT_TRANSFER_BLOCKED: Origin mirror ayarı kapalı olmalı.\n' >&2
  exit 1
fi

printf 'GIT_TRANSFER_TARGET_OK: Yerel checkout, dal ve GitHub origin doğrulandı. Ağ işlemi yapılmadı.\n'
