const express = require('express');
const path = require('path');
const https = require('https');
const http = require('http');

const app = express();
const PORT = parseInt(process.env.PORT, 10) || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'https://sistema-de-horarios-iea-production.up.railway.app';

console.log(`Backend relay → ${BACKEND_URL}`);

// Relay /api/* to backend using pipe (handles ALL content types: JSON, multipart, etc.)
app.all('/api/*', (req, res) => {
  const backendUrl = new URL(`${BACKEND_URL}${req.originalUrl}`);
  const lib = backendUrl.protocol === 'https:' ? https : http;

  const proxyReq = lib.request({
    hostname: backendUrl.hostname,
    port: backendUrl.port || (backendUrl.protocol === 'https:' ? 443 : 80),
    path: backendUrl.pathname + backendUrl.search,
    method: req.method,
    headers: {
      ...req.headers,
      host: backendUrl.hostname,
    },
  }, (proxyRes) => {
    res.status(proxyRes.statusCode);
    // Forward response headers (except transfer-encoding which Express handles)
    Object.entries(proxyRes.headers).forEach(([key, value]) => {
      if (key.toLowerCase() !== 'transfer-encoding') {
        try { res.setHeader(key, value); } catch(e) {}
      }
    });
    proxyRes.pipe(res);
  });

  proxyReq.on('error', (err) => {
    console.error('Relay error:', err.message);
    res.status(502).json({ detail: 'Backend no disponible' });
  });

  // Pipe request body directly (works for JSON, file uploads, everything)
  req.pipe(proxyReq);
});

// Static files
app.use(express.static(path.join(__dirname, 'build')));

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'build', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Frontend IEA en 0.0.0.0:${PORT}`);
});
