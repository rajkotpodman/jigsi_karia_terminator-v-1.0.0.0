const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const http = require('http');
const express = require('express');

const PORT = 39281;
const HOST = '127.0.0.1';
const DIST_DIR = path.join(__dirname, 'dist');

let mainWindow = null;
let server = null;

function startServer() {
    const expressApp = express();
    expressApp.use(express.static(DIST_DIR));

    expressApp.get('*', (req, res) => {
        res.sendFile(path.join(DIST_DIR, 'index.html'), (err) => {
            if (err) {
                console.error('[electron-main] Failed to serve index.html:', err.message);
                res.status(500).send('Application assets not found. Run "npm run build" first.');
            }
        });
    });

    expressApp.use((err, req, res, next) => {
        console.error('[electron-main] Request error:', err.message);
        if (res.headersSent) return next(err);
        res.status(500).send('Internal Server Error');
    });

    server = http.createServer(expressApp);

    return new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(PORT, HOST, () => {
            console.log('[electron-main] Local embedded OSINT server running on ' + HOST + ':' + PORT);
            resolve();
        });
    });
}

function stopServer() {
    if (server) {
        server.close();
        server = null;
        console.log('[electron-main] Embedded server stopped.');
    }
}

async function createWindow() {
    try {
        await startServer();
    } catch (err) {
        console.error('[electron-main] Failed to start embedded server:', err.message);
    }

    mainWindow = new BrowserWindow({
        width: 1440,
        height: 920,
        backgroundColor: '#000000',
        title: 'Jigsi Karia Terminator v4.0 - Cyber OSINT Gateway',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            sandbox: false
        }
    });

    const devUrl = process.env.ELECTRON_START_URL;
    const loadTarget = devUrl || ('http://' + HOST + ':' + PORT);

    mainWindow.loadURL(loadTarget).catch((err) => {
        console.error('[electron-main] Failed to load ' + loadTarget + ':', err.message);
    });

    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url).catch((err) => {
            console.error('[electron-main] Failed to open external URL:', err.message);
        });
        return { action: 'deny' };
    });

    mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
        if (errorCode !== -3) {
            console.error('[electron-main] Page failed to load (' + errorCode + '):', errorDescription);
        }
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
        stopServer();
    });
}

app.on('ready', () => {
    createWindow().catch((err) => {
        console.error('[electron-main] App initialization failed:', err.message);
        app.quit();
    });
});

app.on('window-all-closed', () => {
    stopServer();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow().catch((err) => {
            console.error('[electron-main] Failed to recreate window:', err.message);
        });
    }
});

process.on('uncaughtException', (err) => {
    console.error('[electron-main] Uncaught exception:', err);
});

process.on('unhandledRejection', (reason) => {
    console.error('[electron-main] Unhandled rejection:', reason);
});
