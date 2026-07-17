# Health Check, Sleep Sensor & Waveform Display Components - Analysis

## Overview
This document maps the health check, sleep detection, and waveform display components across the RespirationHealth project.

---

## 1. MODE STRUCTURE

### Three Operating Modes
The application supports three distinct monitoring modes:

1. **Health Check (Normal Mode)** - Standard front-facing vital sign monitoring
2. **Behind-Wall Detection** - Monitoring through obstacles
3. **Sleep Detection** - Extended sleep monitoring with sleep stage classification

### Navigation Flow (Navbar)
**File:** [gpp-project/src/components/Navbar.jsx](gpp-project/src/components/Navbar.jsx#L44-L60)

```jsx
// Run Sensor Dropdown menu with three options:
<button onClick={() => handleDropdownClick("/run-sensor")}>
  Health Check
</button>
<button onClick={() => handleDropdownClick("/run-sensor-behindwall")}>
  Behind Wall Detection
</button>
<button onClick={() => handleDropdownClick("/run-sensor-sleep")}>
  Sleep Detection
</button>
```

---

## 2. WAVEFORM DISPLAY COMPONENT

### Component Definition
**File:** [gpp-project/src/components/WaveformDisplay.jsx](gpp-project/src/components/WaveformDisplay.jsx#L1-L50)

**Props:**
- `isActive` (boolean) - Controls whether component actively polls for data
- `userEmail` (string) - User email for data fetching

**Data Structure:**
```javascript
const [waveformData, setWaveformData] = useState({
  heart_waveform: [],        // Raw heart signal data points
  respiration_waveform: [],  // Raw respiration signal data points
  heart_rate: [],            // Calculated heart rate values
  respiration_rate: [],      // Calculated respiration rate values
  timestamps: []             // Time markers for each data point
});
```

**Polling Mechanism:**
```javascript
// Fetches from: http://localhost:5004/get-latest-vitals
// Polls every 2 seconds when isActive=true
// Updates visualization with real-time waveforms
```

### Canvas-Based Rendering
- Displays multi-channel waveforms in real-time
- Shows grid lines and time/value axes
- Handles hover interactions for detailed data inspection

---

## 3. HEALTH CHECK MODE (Default)

### Page Component
**File:** [gpp-project/src/pages/RunSensor.jsx](gpp-project/src/pages/RunSensor.jsx#L1-L80)

**Route:** `/run-sensor`

**Key Features:**
- Configuration selection (Front or Back setup)
- Sensor execution button
- ML results display (Predicted HR, HR Class, RR Class, Stress Class)

**Backend Endpoint:**
- `POST http://localhost:5000/run-sensor`
- Returns: `{ success, stats_text, ml_results, waveform }`

**WaveformDisplay Usage:**
```jsx
// Conditional rendering based on successful sensor run
{predictedHR && (
  <div>
    <p>Your estimated heart rate is {predictedHR} bpm</p>
    <WaveformDisplay isActive={showWaveforms} userEmail={userEmail} />
  </div>
)}
```

---

## 4. BEHIND-WALL DETECTION MODE

### Page Component
**File:** [gpp-project/src/pages/RunSensorBehindWall.jsx](gpp-project/src/pages/RunSensorBehindWall.jsx#L1-L80)

**Route:** `/run-sensor-behindwall`

**Key Features:**
- Specialized for through-wall detection
- Front/Back configuration options (sensor placement)
- Same ML results display pattern as Health Check

**Backend Endpoint:**
- `POST http://localhost:5002/bw/run-sensor`
- Returns similar structure to `/run-sensor`

**Code Structure:**
```javascript
const [config, setConfig] = useState(null);     // 0=Front, 1=Back
const [predictedHR, setPredictedHR] = useState(null);
const [waveform, setWaveform] = useState(null);

// Sensor execution with behind-wall specific processing
fetch("http://localhost:5002/bw/run-sensor", {
  method: "POST",
  body: JSON.stringify({ userEmail, configuration: config })
})
```

---

## 5. SLEEP DETECTION MODE

### Combined Page Component
**File:** [gpp-project/src/pages/RunSensorSleep.jsx](gpp-project/src/pages/RunSensorSleep.jsx#L1-L150)

**Route:** `/run-sensor-sleep`

**Page Title:** "Radarix | Sleep Detection"

**State Management:**
```javascript
// Collection phase
const [collecting, setCollecting] = useState(false);      // Step 1: sensor
const [analyzing, setAnalyzing] = useState(false);        // Step 2: pipeline
const [sessionCsv, setSessionCsv] = useState(null);       // Path to collected data
const [waveformData, setWaveformData] = useState(null);   // Live waveform
const [duration, setDuration] = useState(120);            // Collection duration in seconds

// Analysis phase - Dashboard state
const [summary, setSummary] = useState(null);
const [events, setEvents] = useState([]);
const [sleepStructure, setSleepStructure] = useState(null);
const [stageEpochs, setStageEpochs] = useState([]);       // Sleep stage data
const [motionTimeline, setMotionTimeline] = useState([]);  // Motion detection
const [motionStats, setMotionStats] = useState(null);
```

**Two-Phase Workflow:**

#### Phase 1: Data Collection
```javascript
// POST http://localhost:5002/api/sleep/collect
// Input: { userEmail, configuration, duration }
// Returns: { session_csv, waveform, stats_text }
fetch(`${API_BASE}/api/sleep/collect`, {
  method: "POST",
  body: JSON.stringify({ 
    userEmail, 
    configuration: config, 
    duration: 120  // seconds
  })
})
```

#### Phase 2: Sleep Analysis
```javascript
// AUTO-TRIGGERED when sessionCsv is set
// POST http://localhost:5002/api/sleep/analyze
fetch(`${API_BASE}/api/sleep/analyze`, {
  method: "POST",
  body: JSON.stringify({ session_csv, userEmail })
})
```

#### Phase 3: Dashboard Display
```javascript
// GET http://localhost:5002/api/sleep/full-session
// Returns all sleep analysis results
fetch(`${API_BASE}/api/sleep/full-session`)
```

**Sleep Analysis Features:**
- Waveform display during collection
- Real-time vital signs charts
- Sleep structure visualization
- Sleep stage epochs (Wake → REM → Light → Deep)
- Motion timeline analysis
- Sleep quality metrics

---

## 6. STATISTICS PAGE (MODE-BASED FILTERING)

### Page Component
**File:** [gpp-project/src/pages/Statistics.jsx](gpp-project/src/pages/Statistics.jsx#L207-L250)

**Mode Selector:**
```jsx
const [mode, setMode] = useState("normal"); // "normal", "wall", "sleep"
const [userFilter, setUserFilter] = useState("all"); // "current" or "all"

// Mode buttons with conditional rendering
<button onClick={() => setMode("normal")}>Normal</button>
<button onClick={() => setMode("wall")}>Behind-Wall</button>
<button onClick={() => setMode("sleep")} disabled>
  Sleep (Coming Soon)
</button>
```

**API Calls Based on Mode:**
- **normal**: Fetches standard vital signs data
- **wall**: Fetches behind-wall detection data
- **sleep**: Currently disabled (coming soon)

**Data Filtered By:**
- Selected mode (normal/wall/sleep)
- User scope (current user or all users)

---

## 7. BACKEND HEALTH CHECK ENDPOINT

### Health Check Endpoint
**File:** [gpp-project-behindwall/backend/api/pipeline.py](gpp-project-behindwall/backend/api/pipeline.py#L181-L195)

```python
@app.get("/")
def home():
    log_data = {
        "location": "pipeline.py:176",
        "message": "Health check endpoint called",
        "data": {
            "method": request.method,
            "url": request.url,
            "remote_addr": request.remote_addr
        },
        "timestamp": int(time.time() * 1000)
    }
    return jsonify({"status": "Radar pipeline API running"})
```

**Frontend Health Check (RunSensor.jsx):**
```javascript
// Performed on component mount in gpp-project-behindwall/src/pages/RunSensor.jsx
useEffect(() => {
  fetch("http://localhost:5000/", { method: "GET" })
    .then(res => res.json())
    .then(data => {
      // Log health check success
      console.log('Backend health check passed');
    })
    .catch(error => {
      // Handle connection failure
      console.error('Backend unavailable');
    });
}, []);
```

---

## 8. MODE CONDITIONAL RENDERING PATTERNS

### Pattern 1: Statistics Page Mode Switching
```jsx
// In Statistics.jsx line 207+
const [mode, setMode] = useState("normal");

useEffect(() => {
  // Reset all data when mode changes
  setRows([]);
  setOverviewStats(null);
  
  // Fetch data based on mode
  if (mode === "normal") {
    // Fetch /statistics/normal endpoint
  } else if (mode === "wall") {
    // Fetch /statistics/wall endpoint
  } else if (mode === "sleep") {
    // Fetch /statistics/sleep endpoint
  }
}, [mode]);
```

### Pattern 2: RunSensorSleep Workflow
```jsx
// Step 1: Collect
<button onClick={handleStartCollection}>
  Start Collection ({duration}s)
</button>

// Step 2: Auto-analyze (triggered by useEffect when sessionCsv changes)
useEffect(() => {
  if (sessionCsv && !analyzing) {
    setAnalyzing(true);
    fetch(`${API_BASE}/api/sleep/analyze`, {...})
  }
}, [sessionCsv]);

// Step 3: Display results
{loading ? <spinner /> : <SleepDashboard data={summary} />}
```

### Pattern 3: WaveformDisplay Activation
```jsx
// Health Check & Behind-Wall modes
{predictedHR && (
  <WaveformDisplay 
    isActive={showWaveforms}  // Activated after ML results
    userEmail={userEmail} 
  />
)}
```

---

## 9. API ENDPOINTS SUMMARY

### Health Check Mode
| Method | Endpoint | Port | Purpose |
|--------|----------|------|---------|
| POST | `/run-sensor` | 5000 | Execute health check sensor |
| GET | `/get-latest-vitals` | 5004 | Fetch waveform data for display |
| GET | `/` | 5000 | Health check |

### Behind-Wall Mode
| Method | Endpoint | Port | Purpose |
|--------|----------|------|---------|
| POST | `/bw/run-sensor` | 5002 | Execute behind-wall sensor |
| POST | `/bw/upload` | 5002 | Upload CSV data |
| POST | `/bw/run_pipeline` | 5002 | Run pipeline |

### Sleep Detection Mode
| Method | Endpoint | Port | Purpose |
|--------|----------|------|---------|
| POST | `/api/sleep/collect` | 5002 | Start data collection |
| POST | `/api/sleep/analyze` | 5002 | Analyze collected data |
| GET | `/api/sleep/full-session` | 5002 | Retrieve full sleep results |

### Statistics/Analysis
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/statistics/{mode}` | Fetch mode-specific aggregated data |

---

## 10. FILE DEPENDENCIES TREE

```
gpp-project/
├── src/
│   ├── pages/
│   │   ├── RunSensor.jsx              [Health Check Page]
│   │   ├── RunSensorBehindWall.jsx    [Behind-Wall Page]
│   │   ├── RunSensorSleep.jsx         [Sleep Detection Page]
│   │   ├── Statistics.jsx             [Mode-based Analytics]
│   │   └── SleepPattern.jsx           [Sleep Analysis Dashboard]
│   ├── components/
│   │   ├── WaveformDisplay.jsx        [Real-time Waveform Component]
│   │   ├── Navbar.jsx                 [Mode Navigation]
│   │   └── protectedroute.jsx
│   └── GPPApp.jsx                     [Route Configuration]
└── backend/
    ├── api/
    │   └── pipeline.py                [Main API with all endpoints]
    ├── sleep_staging/
    │   ├── models_classical.py        [Sleep Stage ML]
    │   └── models_deep.py             [Sleep Stage DL]
    └── (other analysis modules)

gpp-project-behindwall/
└── src/
    ├── pages/
    │   └── RunSensor.jsx              [Behind-wall with health check]
    └── components/
        └── WaveformDisplay.jsx        [Waveform display - light theme]
```

---

## 11. KEY TAKEAWAYS

### Component Organization
- **Three separate page components** for each monitoring mode
- **Shared WaveformDisplay component** used across modes (with theming)
- **Conditional rendering** based on mode state and user actions

### Data Flow
1. **User selects mode** → Navigate to corresponding page
2. **Page initializes** → Sets configuration, user context
3. **User triggers action** → StartCollection/RunSensor
4. **Backend processes** → Data collection, cleaning, ML inference
5. **Results displayed** → ML predictions + Waveform visualization
6. **Dashboard updated** → Statistics page aggregates results

### Sleep Mode Uniqueness
- **Two-phase process**: Collect → Analyze
- **Auto-triggering analysis** when collection completes
- **Extended dashboard** with sleep stages, motion, events
- **Currently disabled** in Statistics page (coming soon)

