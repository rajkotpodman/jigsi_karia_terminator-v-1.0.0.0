const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;
const DIST_DIR = path.join(__dirname, 'dist');

if (!fs.existsSync(path.join(DIST_DIR, 'index.html'))) {
    console.error('[server] Web assets not found in ' + DIST_DIR + '. Run "npm run build" first.');
    process.exit(1);
}

app.use(express.static(DIST_DIR));

app.get('*', (req, res) => {
    res.sendFile(path.join(DIST_DIR, 'index.html'), (err) => {
        if (err) {
            console.error('[server] Failed to serve index.html:', err.message);
            res.status(500).send('Internal Server Error');
        }
    });
});

app.use((err, req, res, next) => {
    console.error('[server] Request error:', err.message);
    if (res.headersSent) return next(err);
    res.status(500).send('Internal Server Error');
});

const server = app.listen(PORT, '0.0.0.0', () => {
    console.log('Server running on http://0.0.0.0:' + PORT);
});

server.on('error', (err) => {
    console.error('[server] Failed to start server:', err.message);
    process.exit(1);
});

process.on('SIGTERM', () => {
    console.log('[server] Shutting down...');
    server.close(() => process.exit(0));
});
