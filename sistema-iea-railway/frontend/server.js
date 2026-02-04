const express = require('express');
const path = require('path');
const app = express();

// Railway asigna el puerto en la variable PORT
// IMPORTANTE: No hardcodear el puerto
const PORT = parseInt(process.env.PORT, 10) || 3000;

app.use(express.static(path.join(__dirname, 'build')));

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'build', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Frontend IEA corriendo en 0.0.0.0:${PORT}`);
});
