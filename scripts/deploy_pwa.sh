#!/usr/bin/env bash
set -euo pipefail

: "${DEPLOY_HOST:?Set DEPLOY_HOST, for example ubuntu@13.229.72.146}"
: "${DEPLOY_KEY:?Set DEPLOY_KEY to the SSH private key path}"

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
release_id="$(date -u +%Y%m%dT%H%M%SZ)-$(git -C "$project_root" rev-parse --short HEAD)"
archive_path="$(mktemp /tmp/english7-pwa.XXXXXX.tar.gz)"
remote_archive="/tmp/english7-pwa-${release_id}.tar.gz"
remote_config="/tmp/english7-Caddyfile-${release_id}"

cleanup() {
  rm -f "$archive_path"
}
trap cleanup EXIT

cd "$project_root"
make build-pwa
tar -C mobile/build/web -czf "$archive_path" .

ssh_args=(-o BatchMode=yes -o ConnectTimeout=10 -i "$DEPLOY_KEY")
scp "${ssh_args[@]}" "$archive_path" "$DEPLOY_HOST:$remote_archive"
scp "${ssh_args[@]}" deploy/Caddyfile "$DEPLOY_HOST:$remote_config"

ssh "${ssh_args[@]}" "$DEPLOY_HOST" bash -s -- \
  "$release_id" "$remote_archive" "$remote_config" <<'REMOTE'
set -euo pipefail
release_id="$1"
remote_archive="$2"
remote_config="$3"
base_dir="/var/www/english7-pwa"
release_dir="$base_dir/releases/$release_id"

sudo caddy validate --adapter caddyfile --config "$remote_config"
sudo install -d -o root -g caddy -m 0755 "$base_dir/releases"
sudo install -d -o root -g caddy -m 0755 "$release_dir"
sudo tar -xzf "$remote_archive" -C "$release_dir"
sudo chown -R root:caddy "$release_dir"
sudo find "$release_dir" -type d -exec chmod 0755 {} +
sudo find "$release_dir" -type f -exec chmod 0644 {} +

sudo ln -sfn "releases/$release_id" "$base_dir/current.next"
sudo mv -Tf "$base_dir/current.next" "$base_dir/current"
sudo cp -a /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.before-pwa-$release_id"
sudo install -o root -g root -m 0644 "$remote_config" /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo systemctl is-active --quiet caddy
rm -f "$remote_archive" "$remote_config"
REMOTE

curl --fail --silent --show-error --max-time 20 \
  https://13.229.72.146.sslip.io/app/ >/dev/null
curl --fail --silent --show-error --max-time 20 \
  https://13.229.72.146.sslip.io/api/v1/health >/dev/null

echo "PWA deployed: https://13.229.72.146.sslip.io/app/"
