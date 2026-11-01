const express = require('express');
const http = require('http');
const { Server } = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = new Server(server);

// Serve a simple API route
app.get('/api/lights/on', (req, res) => {
  console.log('Lights turned ON');
  res.json({ status: 'Lights are ON' });
});

app.get('/api/lights/off', (req, res) => {
  console.log('Lights turned OFF');
  res.json({ status: 'Lights are OFF' });
});

// Socket.IO for real-time updates
io.on('connection', (socket) => {
  console.log('A user connected');
  socket.on('disconnect', () => {
    console.log('User disconnected');
  });
});

const PORT = 3000;
server.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
