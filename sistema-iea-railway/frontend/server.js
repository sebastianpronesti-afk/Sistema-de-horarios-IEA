const express = require('express');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = parseInt(process.env.PORT, 10) || 3000;

// URL del backend - Railway internal URL o public URL
const BACKEND_URL = process.env.BACKEND_URL || 'https://sistema-de-horarios-iea-production.up.railway.app';

console.log(`Proxy API → ${BACKEND_URL}`);

// Proxy: todas las llamadas /api/* van al backend
app.use('/api', createProxyMiddleware({
  target: BACKEND_URL,
  changeOrigin: true,
  pathRewrite: { '^/api': '/api' },
  onError: (err, req, res) => {
    console.error('Proxy error:', err.message);
    res.status(502).json({ error: 'Backend no disponible' });
  }
}));

// Archivos estáticos del frontend React
app.use(express.static(path.join(__dirname, 'build')));

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'build', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Frontend IEA corriendo en 0.0.0.0:${PORT}`);
  console.log(`API proxy → ${BACKEND_URL}`);
});
