#!/usr/bin/env bash
# bootstrap.sh — fetch the published data snapshot instead of re-harvesting Wikipedia.
#
# The pipeline's first stage downloads hundreds of megabytes of article revisions and takes
# hours. Everything downstream of it is deterministic, so for reproduction you want the same
# snapshot the published site was built from, not a fresh harvest of a moving encyclopedia.
set -euo pipefail
cd "$(dirname "$0")/.."

TAG=${SLASHYEAR_SNAPSHOT_TAG:-v1.0.0}
ASSET=slashyear-data-snapshot.tar.gz
URL="https://github.com/ctrl-maud/slashyear/releases/download/${TAG}/${ASSET}"
SHA256=0801b65e3cd905fd21e120e618aa6e9f2eb44b516c0d0396c3d90c94ce20bd07

if [ -d data/claims ]; then
  echo "data/claims already present — nothing to fetch. Delete it to re-download."
  exit 0
fi

echo "downloading ${URL} (~105 MB)"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fSL --retry 3 -o "$tmp/$ASSET" "$URL"

if [ "$TAG" = v1.0.0 ]; then
  echo "verifying checksum"
  echo "${SHA256}  $tmp/$ASSET" | sha256sum -c -
fi

echo "unpacking into ./data"
tar -xzf "$tmp/$ASSET" -C .

echo
echo "unpacked:"
du -sh data/claims data/raw
ls data/*.json data/*.npz 2>/dev/null | sed 's/^/  /'
echo
echo "done. now run: scripts/reproduce.sh"
