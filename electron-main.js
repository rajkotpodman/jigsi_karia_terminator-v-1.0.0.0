const { app, BrowserWindow, Menu, shell } = require('electron');
const path = require('path');
const http = require('http');
const express = require('express');

let mainWindow;
let server;

function startServer() {
    const expressApp = express();
    expressApp.use(express.static(__dirname));
    expressApp.get('*', (req, res) => {
        res.sendFile(path.join(__dirname, 'index.html'));
    });
    server = http.createServer(expressApp);
    server.listen(39281, '127.0.0.1', () => {
        console.log('Local embedded OSINT server running on port 39281');
    });
}

function createWindow() {
    startServer();

    mainWindow = new BrowserWindow({
        width: 1440,
        height: 920,
        backgroundColor: '#000000',
        title: 'Jigsi Karia Terminator v4.0 - Cyber OSINT Gateway',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            sandbox: false
        },
        icon: path.join(__dirname, 'manifest.json')
    });

    // Load local server URL
    setTimeout(() => {
        mainWindow.loadURL('http://127.0.0.1:39281');
    }, 500);

    // Open external links in default browser
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: 'deny' };
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
        if (server) server.close();
    });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (server) server.close();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});
