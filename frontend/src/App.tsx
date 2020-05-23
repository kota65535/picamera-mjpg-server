import React from 'react';
import './App.css';

function App() {
  return (
    <div className="App">
      <h1>PiCamera MJPEG Streaming Demo</h1>
      <img alt="video" src="http://raspberrypi.local:8000/stream.mjpg" width="640" height="480" />
    </div>
 );
}

export default App;
