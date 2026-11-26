#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 غير مثبت."
  if command -v apk >/dev/null 2>&1; then
    echo "جاري تثبيت Python 3..."
    apk update
    apk add python3
  else
    echo "ثبّت Python 3 ثم أعد تشغيل install.sh."
    exit 1
  fi
fi

cat > "$BIN_DIR/ishui" <<EOF
#!/bin/sh
exec python3 "$APP_DIR/ishui.py" "\$@"
EOF
chmod +x "$BIN_DIR/ishui"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) 
    PROFILE="$HOME/.profile"
    touch "$PROFILE"
    if ! grep -Fq "$BIN_DIR" "$PROFILE"; then
      printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$PROFILE"
    fi
    ;;
esac

echo ""
echo "تم تثبيت ISH UI بنجاح."
echo "أغلق iSH وافتحه مجدداً أو نفّذ:"
echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "ثم شغّل: ishui"
