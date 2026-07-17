import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import { 
  Activity, 
  Heart, 
  User, 
  Ruler, 
  AlertCircle,
  Zap,
  Play,
  Square,
  BarChart2
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';
import { motion, AnimatePresence } from 'framer-motion';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const socket = io('http://127.0.0.1:6666');

// --- REUSABLE COMPONENTS ---

const WaveformChart = ({ data, color, label, min, max }) => {
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { display: false },
      y: { 
        display: true, 
        min: min, 
        max: max,
        grid: { color: 'rgba(255, 255, 255, 0.03)' },
        ticks: { display: false }
      },
    },
    plugins: { legend: { display: false } },
    elements: {
      point: { radius: 0 },
      line: { tension: 0.4, borderWidth: 2 }
    },
    animation: false,
  };

  const chartData = {
    labels: Array.from({ length: 100 }, (_, i) => i),
    datasets: [{
      data: data,
      borderColor: color,
      backgroundColor: 'transparent',
    }],
  };

  return (
    <div className="waveform-cell">
      <div className="waveform-label">{label}</div>
      <div style={{ height: '70px' }}><Line data={chartData} options={options} /></div>
    </div>
  );
};

const SpectrumChart = ({ specData }) => {
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { 
        grid: { display: false },
        ticks: { display: false } 
      },
      y: { 
        display: true,
        grid: { color: 'rgba(255, 255, 255, 0.03)' },
        ticks: { display: false } 
      },
    },
    plugins: { legend: { display: false } },
    animation: false,
  };

  const chartData = {
    labels: specData?.freqs || [],
    datasets: [{
      data: specData?.magnitude || [],
      backgroundColor: 'rgba(148, 163, 184, 0.2)',
      borderColor: 'rgba(148, 163, 184, 0.5)',
      borderWidth: 1,
      fill: true,
    }],
  };

  return (
    <div className="waveform-cell">
      <div className="waveform-label">Frequency Spectrum (FFT)</div>
      <div style={{ height: '70px' }}><Line data={chartData} options={options} /></div>
    </div>
  );
};

const SubjectCard = ({ subject }) => {
  return (
    <motion.div 
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className={`subject-card ${subject.invalid ? 'invalid-signal' : ''}`}
    >
      <div className="card-header">
        <div className="avatar">
          <User size={18} />
        </div>
        <div className="header-text">
          <h3>Person #{subject.id}</h3>
          <span className="distance-badge">
            <Ruler size={12} style={{marginRight: '4px'}} />
            {subject.distance}m
          </span>
        </div>
        {!subject.invalid && <div className="status-indicator active"></div>}
      </div>

      {subject.invalid ? (
        <div className="weak-signal-overlay">
          <AlertCircle size={24} />
          <p>Signal Too Weak</p>
          <span>Reposition sensor/person</span>
        </div>
      ) : (
        <>
          <div className="vitals-grid">
            <div className="vital-item">
              <Activity size={16} className="vital-icon resp" />
              <div className="huge-val">{subject.respiration_rate || '--'}</div>
              <div className="vital-label">Respiration (BPM)</div>
            </div>
            <div className="vital-item">
              <Heart size={16} className="vital-icon hr" />
              <div className="huge-val">{subject.heart_rate || '--'}</div>
              <div className="vital-label">Heart Rate (BPM)</div>
            </div>
          </div>

          <div className="triple-graph-layout">
            <WaveformChart data={subject.respiration_wave} color="#38bdf8" label="Respiration waveform" />
            <WaveformChart data={subject.heart_wave} color="#f43f5e" label="Heart rate waveform" />
            <SpectrumChart specData={subject.freq_spectrum} />
          </div>
        </>
      )}
    </motion.div>
  );
};

const RangeProfile = ({ data }) => {
  const chartData = {
    labels: data.map((_, i) => i),
    datasets: [{
      data: data,
      borderColor: 'rgba(56, 189, 248, 0.4)',
      backgroundColor: 'rgba(56, 189, 248, 0.05)',
      fill: true,
      pointRadius: 0,
      borderWidth: 1.5,
    }],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: { x: { display: false }, y: { display: false, min: 0, max: 1.1 } },
    plugins: { legend: { display: false } },
    animation: false,
  };

  return (
    <div className="range-panel">
      <div className="panel-header">
        <BarChart2 size={14} />
        <span>Range Profile</span>
      </div>
      <div style={{ height: '100px' }}>
        <Line data={chartData} options={options} />
      </div>
    </div>
  );
};

function App() {
  const [data, setData] = useState({ num_people: 0, people: [], range_profile: [] });
  const [isConnected, setIsConnected] = useState(false);
  const [isSensorAtive, setIsSensorActive] = useState(false);

  useEffect(() => {
    console.log("🔧 App initialized. Attempting to connect to backend on http://127.0.0.1:6666");
    
    socket.on('connect', () => {
      console.log("✅ WebSocket connected!");
      setIsConnected(true);
    });
    socket.on('disconnect', () => {
      console.log("❌ WebSocket disconnected");
      setIsConnected(false);
    });
    socket.on('radar_data', (receivedData) => {
      console.log("📊 Received radar data:", receivedData);
      setData(receivedData);
    });
    socket.on('connect_error', (error) => {
      console.error("🔴 Connection error:", error);
    });

    return () => {
      socket.off('connect');
      socket.off('disconnect');
      socket.off('radar_data');
      socket.off('connect_error');
    };
  }, []);

  const handleStart = async () => {
    try {
      console.log("▶️  Sending START command to backend...");
      const response = await fetch('http://127.0.0.1:6666/start', { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (response.ok) {
        setIsSensorActive(true);
        console.log("✅ Sensor started successfully");
      } else {
        console.error("❌ Backend returned status:", response.status);
        alert(`Backend error (${response.status}). Check browser console.`);
      }
    } catch (e) {
      console.error("🔴 Failed to connect to backend:", e.message);
      const msg = `Failed to connect to backend. Is app_demo.py running on port 6666?\n\nError: ${e.message}\n\nSolution:\n1. Open terminal\n2. Run: cd backend\n3. Run: py app_demo.py`;
      alert(msg);
    }
  };

  const handleStop = async () => {
    try {
      console.log("Stopping sensor...");
      const response = await fetch('http://127.0.0.1:6666/stop', { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (response.ok) {
        setIsSensorActive(false);
        console.log("Sensor stopped successfully");
      } else {
        console.error("Backend returned status:", response.status);
      }
    } catch (e) {
      console.error("Hardware communication error", e);
      alert("Failed to connect to backend. Is app_demo.py running on port 6666?");
    }
  };

  return (
    <div className="app-container">
      <header className="main-header">
        <div className="branding">
          <Zap className="brand-icon" />
          <h1>VitalGuard <span>IWR6843 Core</span></h1>
        </div>
        
        <div className="controls">
          <div className="sensor-btns">
            <button className={`p-btn start ${isSensorAtive ? 'running' : ''}`} onClick={handleStart}>
              <Play size={14} fill="currentColor" /> START SENSOR
            </button>
            <button className="p-btn stop" onClick={handleStop}>
              <Square size={14} fill="currentColor" /> STOP SENSOR
            </button>
          </div>
          
          <div className="live-pill">
            <div className={`status-dot ${isConnected ? 'live' : 'dead'}`}></div>
            <span>{isConnected ? 'Hardware Connected' : 'Seeking Radar...'}</span>
          </div>
        </div>
      </header>

      <main className="main-content">
        <div className="view-grid">
          <aside className="left-aside">
            <div className="stat-card">
              <div className="stat-val">{data.num_people}</div>
              <div className="stat-label">People Detected</div>
            </div>
            <RangeProfile data={data.range_profile} />
          </aside>

          <section className="dashboard-view">
            <AnimatePresence mode="popLayout">
              {data.num_people > 0 ? (
                <div className="subjects-grid">
                  {data.people.map(p => (
                    <SubjectCard key={p.id} subject={p} />
                  ))}
                </div>
              ) : (
                <div className="no-target-state">
                  <div className="radar-scanner">
                    <div className="scan-line"></div>
                  </div>
                  <h2>NO PERSON DETECTED</h2>
                  <p>Sensor range: 0.5 - 4.0 meters</p>
                </div>
              )}
            </AnimatePresence>
          </section>
        </div>
      </main>

      <footer className="footer-bar">
        <span>Backend: Node + Python DSP</span>
        <span>|</span>
        <span>Interface: UART @ 921600 Baud</span>
        <div className="latency-box">Latency: 32ms</div>
      </footer>
    </div>
  );
}

export default App;
