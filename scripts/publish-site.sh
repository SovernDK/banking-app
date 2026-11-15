#!/usr/bin/env bash
# Copies site/ into the public repo served by GitHub Pages. This repo is private, and Pages is not
# available for private repos on the free plan, so the static pages live in a separate public repo.
set -euo pipefail

repo="${1:-https://github.com/SovernDK/yiji-site.git}"
root="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

git clone --quiet "$repo" "$work"
find "$work" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -R "$root/site/." "$work/"
# Serve files as-is; Jekyll processing is not needed.
touch "$work/.nojekyll"

git -C "$work" add --all
if git -C "$work" diff --cached --quiet; then
  echo "Site already up to date."
  exit 0
fi
git -C "$work" commit --quiet -m "chore: publish site from banking-app"
git -C "$work" push --quiet origin HEAD:main
echo "Published site/ to $repo"
