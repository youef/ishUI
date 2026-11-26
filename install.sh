#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

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

if [ ! -d "$APP_DIR/.git" ]; then
  echo "Note: this is not a Git checkout; in-app updates will be unavailable."
fi

cat > "$BIN_DIR/ishui" <<EOF
#!/bin/sh
exec python3 "$APP_DIR/ishui.py" "\$@"
EOF
chmod +x "$BIN_DIR/ishui"

PROFILE="$HOME/.profile"
touch "$PROFILE"
if ! grep -Fq '.local/bin' "$PROFILE"; then
  printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$PROFILE"
fi

echo ""
echo "ISH UI 4.0 installed."
echo 'If needed, run: export PATH="$HOME/.local/bin:$PATH"'
echo "Launch with: ishui"
