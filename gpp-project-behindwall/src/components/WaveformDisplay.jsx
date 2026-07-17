import React, { useState, useEffect, useRef } from 'react';

const WaveformDisplay = ({ isActive, userEmail }) => {
  const [waveformData, setWaveformData] = useState({
    heart_waveform: [],
    respiration_waveform: [],
    heart_rate: [],
    respiration_rate: [],
    timestamps: []
  });
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  const [hoverInfo, setHoverInfo] = useState(null);
  
  const canvasRef = useRef(null);
  const animationRef = useRef(null);
  const pollingIntervalRef = useRef(null);

  // Polling function to get latest data
  const fetchWaveformData = async () => {
    try {
      const response = await fetch('http://localhost:5004/get-latest-vitals');
      const data = await response.json();
      
      if (data.success) {
        setWaveformData(data.data);
        setError(null);
      } else {
        setError(data.error || 'Failed to fetch waveform data');
      }
    } catch (err) {
      setError('Connection error. Is the backend running?');
      console.error('Waveform fetch error:', err);
    }
  };

  // Start polling when component is active
  useEffect(() => {
    if (isActive) {
      // Initial fetch
      fetchWaveformData();
      
      // Set up polling every 2 seconds
      pollingIntervalRef.current = setInterval(fetchWaveformData, 2000);
      
      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
      };
    }
  }, [isActive]);

  // Canvas drawing function
  const drawWaveforms = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Set canvas size
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
    
    const dataLength = waveformData.heart_waveform.length;
    if (dataLength === 0) {
      // Draw placeholder text
      ctx.fillStyle = '#9CA3AF';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Waiting for sensor data...', width / 2, height / 2);
      return;
    }
    
    // Chart dimensions
    const padding = { left: 60, right: 20, top: 30, bottom: 40 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const halfChartHeight = chartHeight / 2;
    
    // Draw grid lines
    ctx.strokeStyle = '#E5E7EB';
    ctx.lineWidth = 0.5;
    ctx.setLineDash([2, 3]);
    
    // Vertical grid lines (time)
    for (let i = 0; i <= 10; i++) {
      const x = padding.left + (i / 10) * chartWidth;
      ctx.beginPath();
      ctx.moveTo(x, padding.top);
      ctx.lineTo(x, height - padding.bottom);
      ctx.stroke();
    }
    
    // Horizontal grid lines (value)
    for (let i = 0; i <= 8; i++) {
      const y = padding.top + (i / 8) * chartHeight;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    
    // Draw axes
    ctx.strokeStyle = '#374151';
    ctx.lineWidth = 1;
    
    // Y-axis
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, height - padding.bottom);
    ctx.stroke();
    
    // X-axis (center line)
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top + halfChartHeight);
    ctx.lineTo(width - padding.right, padding.top + halfChartHeight);
    ctx.stroke();
    
    // Draw Y-axis labels
    ctx.fillStyle = '#374151';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'right';
    
    // Heart signal Y-axis labels (left)
    const heartMin = 40, heartMax = 180;
    for (let i = 0; i <= 4; i++) {
      const value = heartMin + (heartMax - heartMin) * (1 - i / 4);
      const y = padding.top + (i / 4) * halfChartHeight;
      ctx.fillText(`${Math.round(value)} BPM`, padding.left - 5, y + 3);
    }
    
    // Breathing signal Y-axis labels (right)
    const breathMin = 10, breathMax = 30;
    ctx.textAlign = 'left';
    for (let i = 0; i <= 4; i++) {
      const value = breathMin + (breathMax - breathMin) * (i / 4);
      const y = padding.top + halfChartHeight + (i / 4) * halfChartHeight;
      ctx.fillText(`${Math.round(value)} BrPM`, width - padding.right + 5, y + 3);
    }
    
    // Draw X-axis labels (time)
    ctx.textAlign = 'center';
    const maxTimeSeconds = 20; // Show last 20 seconds
    for (let i = 0; i <= 4; i++) {
      const time = (i / 4) * maxTimeSeconds;
      const x = padding.left + (i / 4) * chartWidth;
      ctx.fillText(`${time}s`, x, height - padding.bottom + 15);
    }
    
    // Draw right Y-axis for breathing signal
    ctx.strokeStyle = '#374151';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(width - padding.right, padding.top + halfChartHeight);
    ctx.lineTo(width - padding.right, height - padding.bottom);
    ctx.stroke();
    
    // Draw heart waveform (top half)
    if (waveformData.heart_rate.length > 0) {
      ctx.strokeStyle = '#EF4444';
      ctx.lineWidth = 2;
      ctx.beginPath();
      
      const heartRateData = waveformData.heart_rate.slice(-50); // Last 50 points
      heartRateData.forEach((value, index) => {
        const x = padding.left + (index / (heartRateData.length - 1)) * chartWidth;
        // Map actual heart rate values to BPM range (40-180)
        const normalizedValue = (value - 40) / (180 - 40);
        const y = padding.top + (1 - normalizedValue) * halfChartHeight;
        
        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });
      ctx.stroke();
      
      // Add label
      ctx.fillStyle = '#EF4444';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText('❤️ Heart Signal', padding.left + 5, padding.top - 5);
    }
    
    // Draw respiration waveform (bottom half)
    if (waveformData.respiration_rate.length > 0) {
      ctx.strokeStyle = '#3B82F6';
      ctx.lineWidth = 2;
      ctx.beginPath();
      
      const respirationRateData = waveformData.respiration_rate.slice(-50); // Last 50 points
      respirationRateData.forEach((value, index) => {
        const x = padding.left + (index / (respirationRateData.length - 1)) * chartWidth;
        // Map actual respiration rate values to BrPM range (10-30)
        const normalizedValue = (value - 10) / (30 - 10);
        const y = padding.top + halfChartHeight + normalizedValue * halfChartHeight;
        
        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });
      ctx.stroke();
      
      // Add label
      ctx.fillStyle = '#3B82F6';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText('🫁 Breathing Signal', padding.left + 5, padding.top + halfChartHeight - 5);
    }
  };

  // Mouse move handler for hover tooltips
  const handleMouseMove = (event) => {
    const canvas = canvasRef.current;
    if (!canvas || waveformData.heart_rate.length === 0) return;
    
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    
    const width = canvas.width;
    const height = canvas.height;
    
    // Chart dimensions
    const padding = { left: 60, right: 20, top: 30, bottom: 40 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const halfChartHeight = chartHeight / 2;
    
    // Check if mouse is within chart area
    if (x >= padding.left && x <= width - padding.right && 
        y >= padding.top && y <= height - padding.bottom) {
      
      // Calculate time position
      const relativeX = (x - padding.left) / chartWidth;
      const timeSeconds = relativeX * 20; // 20 seconds max
      const dataIndex = Math.floor(relativeX * Math.min(49, waveformData.heart_rate.length - 1));
      
      // Determine which signal based on Y position
      let signalType, signalValue, unit;
      
      if (y < padding.top + halfChartHeight) {
        // Heart signal area
        signalType = 'Heart Signal';
        if (dataIndex < waveformData.heart_rate.length) {
          signalValue = waveformData.heart_rate[dataIndex]; // Use actual ML-predicted heart rate
          unit = 'BPM';
        }
      } else {
        // Breathing signal area
        signalType = 'Breathing Signal';
        if (dataIndex < waveformData.respiration_rate.length) {
          signalValue = waveformData.respiration_rate[dataIndex]; // Use actual ML-predicted respiration rate
          unit = 'BrPM';
        }
      }
      
      setHoverInfo({
        x: event.clientX,
        y: event.clientY,
        time: timeSeconds.toFixed(1),
        signalType,
        signalValue: signalValue ? signalValue.toFixed(1) : '--',
        unit
      });
    } else {
      setHoverInfo(null);
    }
  };

  const handleMouseLeave = () => {
    setHoverInfo(null);
  };

  // Animation loop
  useEffect(() => {
    const animate = () => {
      drawWaveforms();
      animationRef.current = requestAnimationFrame(animate);
    };
    
    if (isActive) {
      animate();
    }
    
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [waveformData, isActive]);

  if (!isActive) {
    return null;
  }

  return (
    <div className="w-full max-w-4xl mt-8 bg-white border border-gray-300 rounded-xl p-6 shadow-lg">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xl font-semibold text-gray-800">Live Waveforms</h3>
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-yellow-500'} animate-pulse`}></div>
          <span className="text-sm text-gray-600">
            {isConnected ? 'Connected' : 'Connecting...'}
          </span>
        </div>
      </div>
      
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Combined Canvas Display */}
        <div className="lg:col-span-2 bg-gray-50 border border-gray-200 rounded-lg p-4 relative">
          <canvas
            ref={canvasRef}
            className="w-full h-64 bg-white rounded border border-gray-300 cursor-crosshair"
            style={{ imageRendering: 'crisp-edges' }}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
          />
          
          {/* Tooltip */}
          {hoverInfo && (
            <div
              className="absolute bg-gray-900 text-white px-2 py-1 rounded text-xs pointer-events-none z-10"
              style={{
                left: `${hoverInfo.x - canvasRef.current.getBoundingClientRect().left + 10}px`,
                top: `${hoverInfo.y - canvasRef.current.getBoundingClientRect().top - 30}px`
              }}
            >
              <div>Time: {hoverInfo.time}s</div>
              <div>{hoverInfo.signalType}: {hoverInfo.signalValue} {hoverInfo.unit}</div>
            </div>
          )}
        </div>
        
        {/* Heart Rate Statistics */}
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <h4 className="text-lg font-medium mb-3 text-gray-700 flex items-center gap-2">
            <span className="text-red-500">❤️</span>
            Heart Rate
          </h4>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Current:</span>
              <span className="text-lg font-semibold text-gray-900">
                {waveformData.heart_rate.length > 0 
                  ? `${waveformData.heart_rate[waveformData.heart_rate.length - 1]?.toFixed(1) || '--'} BPM`
                  : '--'
                }
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Average:</span>
              <span className="text-md font-medium text-gray-700">
                {waveformData.heart_rate.length > 0
                  ? `${(waveformData.heart_rate.reduce((a, b) => a + b, 0) / waveformData.heart_rate.length).toFixed(1)} BPM`
                  : '--'
                }
              </span>
            </div>
          </div>
        </div>

        {/* Respiration Rate Statistics */}
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <h4 className="text-lg font-medium mb-3 text-gray-700 flex items-center gap-2">
            <span className="text-blue-500">🫁</span>
            Respiration Rate
          </h4>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Current:</span>
              <span className="text-lg font-semibold text-gray-900">
                {waveformData.respiration_rate.length > 0 
                  ? `${waveformData.respiration_rate[waveformData.respiration_rate.length - 1]?.toFixed(1) || '--'} BPM`
                  : '--'
                }
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Average:</span>
              <span className="text-md font-medium text-gray-700">
                {waveformData.respiration_rate.length > 0
                  ? `${(waveformData.respiration_rate.reduce((a, b) => a + b, 0) / waveformData.respiration_rate.length).toFixed(1)} BPM`
                  : '--'
                }
              </span>
            </div>
          </div>
        </div>
      </div>
      
      <div className="mt-4 text-sm text-gray-500 text-center">
        Real-time data from UWB radar sensor • Updates every 2 seconds
      </div>
    </div>
  );
};

export default WaveformDisplay;
