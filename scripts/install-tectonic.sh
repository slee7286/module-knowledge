#!/bin/sh
set -eu

VERSION=0.17.0
ARCHIVE=tectonic-0.17.0-x86_64-unknown-linux-gnu.tar.gz
URL='https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.17.0/tectonic-0.17.0-x86_64-unknown-linux-gnu.tar.gz'
SHA256=1a715688baf591e650c8aeb160ae934e181685eecbb38b317de30b269ac5d606
DEST="$HOME/.local/share/module-knowledge/tools/tectonic-$VERSION"

[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] || {
  printf 'This pinned build supports Linux x86_64 only.\n' >&2
  exit 1
}
mkdir -p "$DEST"
curl --fail --location --retry 3 --output "$DEST/$ARCHIVE" "$URL"
printf '%s  %s\n' "$SHA256" "$DEST/$ARCHIVE" | sha256sum --check --status
tar -xzf "$DEST/$ARCHIVE" -C "$DEST"
[ "$("$DEST/tectonic" --version)" = "Tectonic $VERSION" ]
rm "$DEST/$ARCHIVE"
printf 'Installed Tectonic %s at %s/tectonic\n' "$VERSION" "$DEST"
