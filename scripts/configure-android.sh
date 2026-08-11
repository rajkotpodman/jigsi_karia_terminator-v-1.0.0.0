#!/usr/bin/env bash
# ========================================================
# JIGSI KARIA TERMINATOR - ANDROID SIGNING & MIN-SDK CONFIG
# Generates a release keystore, wires up signingConfig in
# the Capacitor-generated android project and sets
# minSdkVersion 26 (Android 8.0+).
# ========================================================
set -euo pipefail

ANDROID_DIR="${1:-android}"
STORE_PASSWORD="${KEYSTORE_PASSWORD:-jigsikaria-terminator-2024}"
KEY_ALIAS="jigsi-karia"
KEYSTORE="$ANDROID_DIR/jigsi-release.keystore"
PROPS_FILE="$ANDROID_DIR/keystore.properties"

if [ ! -d "$ANDROID_DIR" ]; then
    echo "[android] Android project directory '$ANDROID_DIR' not found. Run 'npx cap add android' first." >&2
    exit 1
fi

echo "[android] Configuring Android signing for $ANDROID_DIR"

if [ ! -f "$KEYSTORE" ]; then
    echo "[android] Generating release keystore..."
    keytool -genkeypair -v \
        -keystore "$KEYSTORE" \
        -alias "$KEY_ALIAS" \
        -keyalg RSA \
        -keysize 2048 \
        -validity 10000 \
        -storepass "$STORE_PASSWORD" \
        -keypass "$STORE_PASSWORD" \
        -dname "CN=Jigsi Karia, OU=Security Grid, O=JigsiKaria, L=Ahmedabad, ST=Gujarat, C=IN" >/dev/null 2>&1
fi

echo "[android] Writing keystore.properties..."
cat > "$PROPS_FILE" <<EOF
storeFile=jigsi-release.keystore
storePassword=$STORE_PASSWORD
keyAlias=$KEY_ALIAS
keyPassword=$STORE_PASSWORD
EOF

APP_GRADLE="$ANDROID_DIR/app/build.gradle"

echo "[android] Patching $APP_GRADLE with release signingConfig..."
python3 - "$APP_GRADLE" "$KEY_ALIAS" <<'PYEOF'
import sys

gradle_path = sys.argv[1]
alias = sys.argv[2]

with open(gradle_path, 'r', encoding='utf-8') as f:
    content = f.read()

if 'signingConfigs.release' not in content:
    signing_block = '''        signingConfigs {
            def keystorePropertiesFile = rootProject.file("keystore.properties")
            def keystoreProperties = new Properties()
            if (keystorePropertiesFile.exists()) {
                keystoreProperties.load(new FileInputStream(keystorePropertiesFile))
            }
            release {
                storeFile keystorePropertiesFile.exists() ? rootProject.file(keystoreProperties['storeFile']) : null
                storePassword keystoreProperties['storePassword']
                keyAlias keystoreProperties['keyAlias']
                keyPassword keystoreProperties['keyPassword']
            }
        }

'''
    marker = 'android {\n'
    if marker in content:
        content = content.replace(marker, marker + signing_block, 1)
    else:
        raise SystemExit('[android] Could not find "android {" block in ' + gradle_path)

    release_marker = 'minifyEnabled false\n'
    if release_marker in content:
        content = content.replace(
            release_marker,
            release_marker + '            signingConfig signingConfigs.release\n',
            1
        )
    else:
        raise SystemExit('[android] Could not find release buildType block in ' + gradle_path)

    with open(gradle_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('[android] build.gradle patched with release signingConfig.')
else:
    print('[android] build.gradle already has signingConfigs.release; skipping.')
PYEOF

VARIABLES_GRADLE="$ANDROID_DIR/variables.gradle"

echo "[android] Setting minSdkVersion to 26 (Android 8.0+)..."
python3 - "$VARIABLES_GRADLE" <<'PYEOF'
import re
import sys

gradle_path = sys.argv[1]

with open(gradle_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_content = re.sub(
    r'minSdkVersion\s*=\s*\d+',
    'minSdkVersion = 26',
    content,
    count=1
)

with open(gradle_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('[android] minSdkVersion set to 26.')
PYEOF

echo "[android] Android signing configuration complete."
