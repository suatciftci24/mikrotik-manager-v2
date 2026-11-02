#!/usr/bin/env bash
# Office WSL only. No commit/push; immutable Git source, no local secrets uploaded.
set -euo pipefail
cd /home/suatpc/Codex-Projects/mikrotik-manager-v2
mode=${1:-}
[[ $# -le 1 && ( -z $mode || $mode == --check-only || $mode == --release-check-only ) ]] || { echo 'BLOCKED reason=INVALID_MODE' >&2; exit 1; }
target=7bb617c4838c1bd94b8cbe612981cabe5186b6b1
sha=$(git rev-parse "$target^{commit}" 2>/dev/null) || { echo 'BLOCKED reason=TARGET_REVISION_NOT_FOUND' >&2; exit 1; }
[[ $sha == "$target" ]] || { echo 'BLOCKED reason=TARGET_REVISION_MISMATCH' >&2; exit 1; }
# Read-only verification of the requested GitHub main revision; never fetch/push.
origin=$(git remote get-url origin)
[[ $origin == *github.com* ]]
main_sha=$(GIT_TERMINAL_PROMPT=0 git ls-remote "$origin" refs/heads/main)
[[ ${main_sha%%[[:space:]]*} == "$sha" ]]
work=$(mktemp -d /tmp/v2-approved.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
umask 077
git archive --format=tar "$sha" > "$work/source.tar"
cp deploy/cebeci-v2-pilot/update-approved-vds.py "$work/update.py"
printf '%s' "$sha" > "$work/version"
(cd "$work" && sha256sum source.tar > source.sha256 && sha256sum update.py > updater.sha256)
echo "Local updater SHA256=$(sha256sum "$work/update.py" | cut -d' ' -f1); application revision=$sha"
ssh_args=(-i /home/suatpc/.ssh/mikrotik_manager_ed25519 -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10)
# No retry: any SSH failure terminates this command.
remote=$(ssh "${ssh_args[@]}" -o BatchMode=yes mikadmin@185.139.5.51 'umask 077; mktemp -d /home/mikadmin/v2-update.XXXXXXXX')
[[ $remote =~ ^/home/mikadmin/v2-update\.[A-Za-z0-9]{8}$ ]]
tar -C "$work" -cf - source.tar source.sha256 update.py updater.sha256 version | ssh "${ssh_args[@]}" -o BatchMode=yes mikadmin@185.139.5.51 "tar -xf - -C '$remote'"
ssh -tt "${ssh_args[@]}" mikadmin@185.139.5.51 "cd '$remote' && sha256sum --check updater.sha256 && sudo python3 '$remote/update.py' '$remote' $mode"
