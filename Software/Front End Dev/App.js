import React, { useState } from 'react';
import axios from 'axios';
import { Button, Container, Typography, Box } from '@mui/material';

function App() {
  const [status, setStatus] = useState('Unknown');

  const handleLights = async (action) => {
    try {
      const response = await axios.get(`http://192.168.4.127:3000/api/lights/${action}`);
      setStatus(response.data.status);
    } catch (error) {
      console.error('Error communicating with backend:', error);
      setStatus('Error');
    }
  };

  // Background style for the outer div
  const backgroundStyle = {
    backgroundImage: 'url(https://your-background-image-url)',
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    height: '100vh',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
  };

  return (
    <div style={backgroundStyle}>
      <Container sx={{ textAlign: 'center', backgroundColor: 'rgba(0, 0, 0, 0.7)', padding: '30px', borderRadius: '10px' }}>
        <Box sx={{ color: 'white', padding: '50px' }}>
          <Typography variant="h3" sx={{ marginBottom: '20px' }}>Neon Sign Control</Typography>
          
          <Button 
            variant="contained" 
            sx={{ marginRight: '20px', backgroundColor: '#1db954', padding: '15px 30px', fontSize: '18px' }} 
            onClick={() => handleLights('on')}
          >
            Turn Lights On
          </Button>

          <Button 
            variant="contained" 
            sx={{ backgroundColor: '#ff4f58', padding: '15px 30px', fontSize: '18px' }} 
            onClick={() => handleLights('off')}
          >
            Turn Lights Off
          </Button>

          <Typography variant="h4" sx={{ marginTop: '30px' }}>Status: {status}</Typography>
        </Box>
      </Container>
    </div>
  );
}

export default App;
