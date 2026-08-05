#!/usr/bin/env bash
# ========================================================
# JIGSI KARIA TERMINATOR - macOS DMG PACKAGER SCRIPT
# ========================================================
set -e

APP_NAME="JigsiKariaTerminator"
VERSION="4.0.0"
DMG_NAME="jigsi-karia-terminator-${VERSION}-universal.dmg"
TEMP_DIR="dmg_temp"

echo "🍏 Building macOS DMG Installer for ${APP_NAME} v${VERSION}..."

# Ensure create-dmg is available or use hdiutil
if ! command -v create-dmg &> /dev/null; then
    echo "[+] Installing create-dmg utility via Homebrew..."
    brew install create-dmg || true
fi

# Clean previous builds
rm -rf "$TEMP_DIR" "${DMG_NAME}"
mkdir -p "$TEMP_DIR/Jigsi Karia Terminator"

# Copy app bundle or files
cp -R dist-mac/JigsiKariaTerminator.app "$TEMP_DIR/Jigsi Karia Terminator/" 2>/dev/null || {
    echo "[+] Creating app bundle structure..."
    mkdir -p "$TEMP_DIR/Jigsi Karia Terminator/JigsiKariaTerminator.app/Contents/MacOS"
    mkdir -p "$TEMP_DIR/Jigsi Karia Terminator/JigsiKariaTerminator.app/Contents/Resources"
    cp Info.plist "$TEMP_DIR/Jigsi Karia Terminator/JigsiKariaTerminator.app/Contents/"
    cp index.html server.js package.json package-lock.json "$TEMP_DIR/Jigsi Karia Terminator/JigsiKariaTerminator.app/Contents/Resources/"
}

# Create Applications symlink
ln -s /Applications "$TEMP_DIR/Jigsi Karia Terminator/Applications"

if command -v create-dmg &> /dev/null; then
    create-dmg \
      --volname "Jigsi Karia Terminator Installer" \
      --window-pos 200 120 \
      --window-size 660 400 \
      --icon-size 100 \
      --icon "JigsiKariaTerminator.app" 180 170 \
      --hide-extension "JigsiKariaTerminator.app" \
      --app-drop-link 480 170 \
      "${DMG_NAME}" \
      "$TEMP_DIR/Jigsi Karia Terminator"
else
    echo "[+] Fallback to hdiutil..."
    hdiutil create -volname "Jigsi Karia Terminator" -srcfolder "$TEMP_DIR/Jigsi Karia Terminator" -ov -format UDZO "${DMG_NAME}"
fi

rm -rf "$TEMP_DIR"
echo "✅ macOS DMG successfully created: ${DMG_NAME}"
