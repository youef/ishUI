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

# Create a small launcher that always points to this checkout.
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
echo "ISH UI installed successfully."
echo "Run this once if the command is not found in the current session:"
echo 'export PATH="$HOME/.local/bin:$PATH"'
echo "Then launch with: ishui"
echo ""
