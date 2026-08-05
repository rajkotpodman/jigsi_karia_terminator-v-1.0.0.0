#!/usr/bin/env bash
# ========================================================
# JIGSI KARIA TERMINATOR - LINUX PACKAGE BUILDER (.deb, .rpm, .AppImage)
# ========================================================
set -e

APP_NAME="jigsi-karia-terminator"
VERSION="4.0.0"
ARCH="amd64"

echo "🐧 Building Linux Packages (.deb, .rpm, .AppImage) for v${VERSION}..."

# Ensure npm build is ready
npm run build

# Create build workspace
WORK_DIR="linux_pkg_build"
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR/usr/share/$APP_NAME"
mkdir -p "$WORK_DIR/usr/bin"
mkdir -p "$WORK_DIR/usr/share/applications"

# Copy files
cp -r index.html server.js package.json package-lock.json node_modules "$WORK_DIR/usr/share/$APP_NAME/"

# Create launcher wrapper in /usr/bin
cat << 'EOF' > "$WORK_DIR/usr/bin/jigsi-karia-terminator"
#!/usr/bin/env bash
cd /usr/share/jigsi-karia-terminator
exec node server.js "$@"
EOF
chmod +x "$WORK_DIR/usr/bin/jigsi-karia-terminator"

# Create Desktop Entry
cp jigsi-karia.desktop "$WORK_DIR/usr/share/applications/jigsi-karia-terminator.desktop"

# Check if fpm is available for .deb and .rpm
if command -v fpm &> /dev/null; then
    echo "[+] Building .deb package with fpm..."
    fpm -s dir -t deb -n "$APP_NAME" -v "$VERSION" -a "$ARCH" \
        --description "Cyber OSINT Gateway & Hacker Scanner" \
        --maintainer "Jigsi Karia Security Grid <admin@jigsikaria.com>" \
        --depends "nodejs" \
        -C "$WORK_DIR" usr/
        
    echo "[+] Building .rpm package with fpm..."
    fpm -s dir -t rpm -n "$APP_NAME" -v "$VERSION" -a "$ARCH" \
        --description "Cyber OSINT Gateway & Hacker Scanner" \
        --maintainer "Jigsi Karia Security Grid <admin@jigsikaria.com>" \
        --depends "nodejs" \
        -C "$WORK_DIR" usr/
else
    echo "[!] fpm not found. Skipping direct .deb/.rpm binary generation (install via: gem install fpm)."
fi

# AppImage creation simulation / build
echo "[+] Creating AppImage structure..."
APPDIR="JigsiKariaTerminator.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -r "$WORK_DIR/usr/share/$APP_NAME"/* "$APPDIR/"
cp jigsi-karia.desktop "$APPDIR/jigsi-karia-terminator.desktop"
cp jigsi-karia.desktop "$APPDIR/usr/share/applications/"

cat << 'EOF' > "$APPDIR/AppRun"
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
cd "$HERE"
exec node server.js
EOF
chmod +x "$APPDIR/AppRun"

if command -v appimagetool &> /dev/null; then
    appimagetool "$APPDIR" "${APP_NAME}-${VERSION}-x86_64.AppImage"
    echo "✅ AppImage generated successfully."
else
    echo "[!] appimagetool not found. Packed AppDir ready at $APPDIR"
fi

echo "✅ Linux packaging script completed successfully."
