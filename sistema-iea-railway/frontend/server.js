const express = require('express');
const path = require('path');

const app = express();
const PORT = parseInt(process.env.PORT, 10) || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'https://sistema-de-horarios-iea-production.up.railway.app';

console.log(`Backend relay → ${BACKEND_URL}`);

// Relay ALL /api requests to backend (GET, POST, PUT, DELETE)
app.all('/api/*', async (req, res) => {
  try {
    const url = `${BACKEND_URL}${req.originalUrl}`;

    const headers = {};
    if (req.headers['content-type']) {
      headers['Content-Type'] = req.headers['content-type'];
    }

    const fetchOptions = {
      method: req.method,
      headers,
    };

    // For POST/PUT/PATCH, forward the body
    if (['POST', 'PUT', 'PATCH'].includes(req.method)) {
      const chunks = [];
      for await (const chunk of req) {
        chunks.push(chunk);
      }
      const body = Buffer.concat(chunks);
      if (body.length > 0) {
        fetchOptions.body = body;
      }
    }

    const response = await fetch(url, fetchOptions);

    // Forward status and content-type
    res.status(response.status);
    const ct = response.headers.get('content-type');
    if (ct) res.setHeader('Content-Type', ct);

    const data = await response.text();
    res.send(data);
  } catch (err) {
    console.error('Relay error:', err.message);
    res.status(502).json({ detail: 'Backend no disponible: ' + err.message });
  }
});

// Static files
app.use(express.static(path.join(__dirname, 'build')));

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'build', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Frontend IEA en 0.0.0.0:${PORT}`);
  console.log(`API relay → ${BACKEND_URL}`);
});
