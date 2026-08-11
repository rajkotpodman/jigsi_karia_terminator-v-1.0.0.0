const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

exports.default = async function (context) {
    if (process.platform !== 'darwin') {
        return;
    }

    const productName = context.packager.appInfo.productFilename;
    const appPath = path.join(context.appOutDir, productName + '.app');

    if (!fs.existsSync(appPath)) {
        console.warn('[afterPack] App bundle not found at ' + appPath + ', skipping ad-hoc signing.');
        return;
    }

    console.log('[afterPack] Ad-hoc signing ' + appPath);
    try {
        execSync('codesign --force --deep --sign - "' + appPath + '"', { stdio: 'inherit' });
        console.log('[afterPack] Ad-hoc signing completed for ' + productName + '.app');
    } catch (err) {
        console.error('[afterPack] Ad-hoc signing failed:', err.message);
        throw err;
    }
};
