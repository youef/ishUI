#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
USER_BIN="$HOME/.local/bin"
SYSTEM_BIN="/usr/local/bin"

if ! command -v python3 >/dev/null 2>&1; then
  if command -v apk >/dev/null 2>&1; then
    echo "Installing Python 3..."
    apk update
    apk add python3
  else
    echo "Python 3 is required. Install it, then run this script again."
    exit 1
  fi
fi

if ! command -v git >/dev/null 2>&1; then
  if command -v apk >/dev/null 2>&1; then
    echo "Installing Git..."
    apk add git
  else
    echo "Git is required for automatic repository updates."
    exit 1
  fi
fi

if [ ! -d "$APP_DIR/.git" ]; then
  echo "This is not a Git checkout. Automatic updates are disabled."
  exit 1
fi

# Prefer the existing system command location so older /usr/local/bin/ish
# launchers are replaced; otherwise install into the user's PATH.
if [ -d "$SYSTEM_BIN" ] && [ -w "$SYSTEM_BIN" ]; then
  BIN_DIR="$SYSTEM_BIN"
else
  BIN_DIR="$USER_BIN"
  mkdir -p "$BIN_DIR"
fi

# Both commands safely update only a clean checkout. Local edits are never
# stashed, reset, overwritten, or discarded automatically.
cat > "$BIN_DIR/ish" <<EOF
#!/bin/sh
APP_DIR="$APP_DIR"
if command -v git >/dev/null 2>&1 && [ -d "\$APP_DIR/.git" ]; then
  if [ -z "\$(git -C "\$APP_DIR" status --porcelain 2>/dev/null)" ]; then
    git -C "\$APP_DIR" pull --ff-only --quiet || echo "ISH UI: update skipped (network or Git issue)." >&2
  else
    echo "ISH UI: local changes detected; automatic update skipped to protect your files." >&2
  fi
fi
exec python3 "\$APP_DIR/ishui.py" "\$@"
EOF
chmod +x "$BIN_DIR/ish"

cat > "$BIN_DIR/ishui" <<EOF
#!/bin/sh
exec "$BIN_DIR/ish" "\$@"
EOF
chmod +x "$BIN_DIR/ishui"

PROFILE="$HOME/.profile"
touch "$PROFILE"
if ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "$PROFILE"; then
  printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$PROFILE"
fi

echo ""
echo "ISH UI 5.5.0 installed."
echo "Commands: ish  |  ishui"
echo "The repository is checked and fast-forward updated before each launch."
echo "If local files are modified, the update is skipped to protect them."
