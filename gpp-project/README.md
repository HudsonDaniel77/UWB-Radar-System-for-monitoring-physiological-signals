# GPP-Project - Vital Signs Monitoring Web Application

<div align="center">

![React](https://img.shields.io/badge/React-18.3.1-61dafb?logo=react)
![Vite](https://img.shields.io/badge/Vite-7.1.7-646cff?logo=vite)
![Flask](https://img.shields.io/badge/Flask-2.3.3-000000?logo=flask)
![Python](https://img.shields.io/badge/Python-3.8+-3776ab?logo=python)
![TailwindCSS](https://img.shields.io/badge/Tailwind-4.1.14-38bdf8?logo=tailwindcss)

**Primary web application for front-facing mmWave vital signs monitoring**

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [API](#api-reference) • [ML Models](#machine-learning)

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Pages & Components](#pages--components)
- [Backend Services](#backend-services)
- [Machine Learning](#machine-learning)
- [Data Flow](#data-flow)
- [API Reference](#api-reference)
- [Development](#development)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

**GPP-Project** is the primary web application for the RespirationHealth platform. It provides a complete user interface for:

- Real-time vital signs monitoring using TI mmWave radar
- User authentication and session management
- Live data visualization with interactive charts
- Comprehensive statistical analysis and EDA
- Machine learning-powered calibration
- Historical data tracking and export

This is designed for **front-facing detection** scenarios where the subject is directly in front of the radar sensor (e.g., desk monitoring, clinical settings).

---

## ✨ Features

### Frontend Features

- ✅ **Responsive React UI** with Tailwind CSS
- ✅ **Firebase Authentication** (Email/Password)
- ✅ **Protected Routes** for authenticated users
- ✅ **Real-time Charts** using Chart.js and React-Chartjs-2
- ✅ **Multiple Monitoring Modes**:
  - Front-facing vital signs
  - Behind-wall detection
  - Sleep monitoring
- ✅ **Interactive Statistics Dashboard**:
  - Histograms
  - Time series plots
  - Scatter plots
  - Correlation matrices
  - Box plots
  - Summary statistics
- ✅ **Live Data Streaming** with WebSocket support
- ✅ **CSV Export** functionality
- ✅ **User-specific Data Filtering**
- ✅ **Dark Mode UI** with modern design

### Backend Features

- ✅ **Flask REST API** for sensor control
- ✅ **Multi-endpoint Architecture**:
  - Sensor control (Port 5004)
  - Statistics/EDA (Port 5001)
  - User management
- ✅ **UART Communication** with TI mmWave radar
- ✅ **Real-time Data Processing**
- ✅ **CSV-based Data Storage**
- ✅ **User Validation** from users.csv
- ✅ **Automated Data Cleaning**
- ✅ **Session Management**
- ✅ **Calibration System** with ML models

### Data Analysis Features

- ✅ **XGBoost Regression** for HR/RR prediction
- ✅ **Multi-class Classification** (HR class, RR class, Stress)
- ✅ **Feature Engineering** (10+ features)
- ✅ **Signal Quality Index (SQI)** calculation
- ✅ **Statistical Hypothesis Testing**
- ✅ **Incremental Learning** from new data
- ✅ **Model Metrics Tracking** (JSON files)
- ✅ **Calibration Offsets** from real ground truth data

---

## 🛠️ Technology Stack

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18.3.1 | UI framework |
| Vite | 7.1.7 | Build tool & dev server |
| React Router | 6.30.1 | Client-side routing |
| Chart.js | 4.5.1 | Chart rendering engine |
| React-Chartjs-2 | 5.3.0 | React wrapper for Chart.js |
| Tailwind CSS | 4.1.14 | Utility-first CSS |
| Firebase | 12.6.0 | Authentication & database |

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Flask | 2.3.3 | Web framework |
| Flask-CORS | 4.0.0 | Cross-origin requests |
| Flask-SocketIO | 5.3.6 | WebSocket support |
| Pandas | 2.0.3 | Data manipulation |
| NumPy | 1.24.3 | Numerical computing |
| SciPy | 1.11.4 | Scientific computing |
| XGBoost | Latest | Machine learning |
| Scikit-learn | Latest | ML utilities |
| Joblib | Latest | Model serialization |
| PySerial | Latest | UART communication |
| Matplotlib | Latest | Data visualization |

---

## 📁 Project Structure

```
gpp-project/
│
├── src/                           # React frontend source
│   ├── pages/                     # Page components
│   │   ├── Home.jsx               # Landing page
│   │   ├── About.jsx              # About page
│   │   ├── Login.jsx              # Login page
│   │   ├── Signup.jsx             # Registration page
│   │   ├── RunSensor.jsx          # Main sensor control (Protected)
│   │   ├── RunSensorBehindWall.jsx # Behind-wall mode (Protected)
│   │   ├── RunSensorSleep.jsx     # Sleep monitoring (Protected)
│   │   └── Statistics.jsx         # Analytics dashboard (Protected)
│   │
│   ├── components/                # Reusable components
│   │   ├── Navbar.jsx             # Navigation bar
│   │   └── ProtectedRoute.jsx     # Auth guard
│   │
│   ├── assets/                    # Images, icons, etc.
│   ├── firebase.js                # Firebase configuration
│   ├── GPPApp.jsx                 # Main app component
│   ├── main.jsx                   # Entry point
│   ├── App.css                    # Global styles
│   └── index.css                  # Tailwind base styles
│
├── backend/                       # Flask backend
│   ├── app.py                     # Main sensor control API (Port 5004)
│   ├── vst.py                     # Vital signs tracker script
│   ├── eda_flask.py               # Statistics & EDA API (Port 5001)
│   ├── add_user_api.py            # User registration API
│   ├── uploadingdata.py           # Data upload utilities
│   ├── TIGraph.py                 # Radar data parsing
│   ├── vitalsigns.py              # Legacy vital signs script
│   ├── vitalsigns_back.py         # Behind-wall variant
│   ├── allframes.py               # Frame-by-frame analyzer (root level)
│   ├── users.csv                  # User database
│   └── vital_signs_data_new.csv   # Primary data file
│
├── data_analysis/                 # ML & analytics pipeline
│   ├── cleaning_data.py           # Data preprocessing
│   ├── calibration.py             # ML calibration & feature engineering
│   ├── train_hr_model.py          # Heart rate regression model
│   ├── train_hr_classifier.py     # HR classification model
│   ├── hypotheses_tests.py        # Statistical hypothesis testing
│   ├── predict_with_model.py      # Inference script
│   │
│   ├── hr_model.joblib            # Trained HR regression model
│   ├── hr_class_model.joblib      # HR classifier
│   ├── rr_class_model.joblib      # RR classifier
│   ├── stress_class_model.joblib  # Stress classifier
│   ├── vitals_classifier.joblib   # Combined classifier
│   ├── calibration_model.joblib   # Calibration model
│   │
│   ├── hr_model_metrics.json      # Model performance metrics
│   ├── hr_class_metrics.json
│   ├── rr_class_metrics.json
│   ├── stress_class_metrics.json
│   ├── vitals_class_metrics.json
│   ├── calibration_metrics.json
│   ├── calibration_offsets.json   # Learned offsets
│   ├── class_label_encodings.json # Class mappings
│   │
│   ├── cleaned_vital_signs_new_tryingsomething.csv  # Cleaned samples
│   ├── final_run_stats_new_tryingsomething.csv      # Run statistics
│   └── VariousData.csv            # Ground truth calibration data
│
├── vital_signs_data/              # Collected session data
│   ├── range_profile.npy          # Range profile data
│   ├── summary.txt                # Session summary
│   └── vital_signs_live_session.csv
│
├── public/                        # Static assets
├── index.html                     # HTML template
├── package.json                   # Frontend dependencies
├── vite.config.js                 # Vite configuration
├── eslint.config.js               # ESLint rules
└── README.md                      # This file
```

---

## 🚀 Installation

### Prerequisites

- **Node.js** 16+ and npm
- **Python** 3.8+ and pip
- **TI mmWave Radar** (IWR6843/AWR6843)
- **Git** (optional)

### Step 1: Install Frontend Dependencies

```bash
cd gpp-project
npm install
```

This installs:
- React, React DOM, React Router
- Chart.js, React-Chartjs-2
- Firebase SDK
- Tailwind CSS
- Vite and build tools

### Step 2: Install Backend Dependencies

```bash
# In gpp-project directory
pip install flask flask-cors flask-socketio pandas numpy scipy scikit-learn xgboost joblib matplotlib pyserial python-socketio python-engineio
```

Or create a `requirements.txt`:

```txt
Flask==2.3.3
Flask-CORS==4.0.0
Flask-SocketIO==5.3.6
pandas==2.0.3
numpy==1.24.3
scipy==1.11.4
scikit-learn>=1.3.0
xgboost>=2.0.0
joblib>=1.3.0
matplotlib>=3.7.0
pyserial>=3.5
python-socketio==5.9.0
python-engineio==4.7.1
```

Then:
```bash
pip install -r requirements.txt
```

### Step 3: Configure Firebase

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project (or use existing)
3. Enable **Authentication** → Email/Password
4. Enable **Cloud Firestore** (optional, for future features)
5. Copy your Firebase config
6. Update `src/firebase.js`:

```javascript
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_PROJECT.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID",
  storageBucket: "YOUR_PROJECT.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};
```

### Step 4: Configure COM Ports

Edit `backend/vst.py`:

```python
USER_PORT = 'COM5'  # Check Device Manager
DATA_PORT = 'COM6'
CFG_FILE = r"C:\ti\mmwave_industrial_toolbox_4_12_1\labs\Vital_Signs\68xx_vital_signs\gui\profiles\xwr68xx_profile_VitalSigns_20fps_Front.cfg"
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the root:

```env
# Backend URLs
VITE_EDA_BASE=http://127.0.0.1:5001
VITE_SENSOR_API=http://localhost:5004

# Firebase (optional if already in firebase.js)
VITE_FIREBASE_API_KEY=your_api_key
VITE_FIREBASE_AUTH_DOMAIN=your_domain
```

### Backend Paths

Update paths in `backend/eda_flask.py`:

```python
NORMAL_SAMPLE_CSV = r"C:\path\to\gpp-project\data_analysis\cleaned_vital_signs_new_tryingsomething.csv"
NORMAL_RUN_CSV = r"C:\path\to\gpp-project\data_analysis\final_run_stats_new_tryingsomething.csv"
WALL_SAMPLE_CSV = r"C:\path\to\gpp-project-behindwall\data_analysis\cleaned_vital_signs_new.csv"
WALL_RUN_CSV = r"C:\path\to\gpp-project-behindwall\data_analysis\final_run_stats_new.csv"
```

### Vite Configuration

`vite.config.js` is pre-configured for React. Modify if needed:

```javascript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: true
  }
})
```

---

## 🎬 Running the Application

### Development Mode

You need **3 terminals** running simultaneously:

**Terminal 1: Sensor Control API**

```bash
cd backend
python app.py
```

- Runs on `http://localhost:5004`
- Handles sensor start/stop commands
- Validates users from `users.csv`
- Executes `vst.py` script

**Terminal 2: Statistics API**

```bash
cd backend
python eda_flask.py
```

- Runs on `http://127.0.0.1:5001`
- Provides EDA endpoints
- Serves run stats, sample stats, histograms, correlations

**Terminal 3: React Frontend**

```bash
npm run dev
```

- Runs on `http://localhost:5173`
- Hot module replacement enabled
- Auto-opens browser

### Access the Application

Open [http://localhost:5173](http://localhost:5173) in your browser.

### Production Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

This generates optimized static files in `dist/` directory.

---

## 📄 Pages & Components

### Public Pages

#### Home (`src/pages/Home.jsx`)

- Landing page with project overview
- Call-to-action buttons
- Feature highlights

#### About (`src/pages/About.jsx`)

- Project information
- Technology details
- Team information

#### Login (`src/pages/Login.jsx`)

- Firebase email/password authentication
- Redirects to RunSensor on success
- Registration link

#### Signup (`src/pages/Signup.jsx`)

- User registration with Firebase
- Automatically adds user to Firestore
- Auto-login after signup

### Protected Pages (Require Authentication)

#### RunSensor (`src/pages/RunSensor.jsx`)

**Primary sensor control interface**

Features:
- Configuration selection (0: Front, 1: Side)
- Start/Stop monitoring button
- Real-time charts:
  - Heart Rate (BPM)
  - Respiration Rate (BPM)
  - Range (meters)
  - Heart Waveform
  - Breath Waveform
- Live data updates via backend
- Session management
- Error popups for user feedback

User Flow:
1. Select configuration
2. Click "Start Monitoring"
3. Backend runs `vst.py` with user email + config
4. Data saved to `vital_signs_data_new.csv`
5. Real-time charts update
6. Stop automatically after duration or manually

#### RunSensorBehindWall (`src/pages/RunSensorBehindWall.jsx`)

- Similar to RunSensor but for behind-wall detection
- Uses different backend endpoint
- Optimized for attenuated signals

#### RunSensorSleep (`src/pages/RunSensorSleep.jsx`)

- Sleep monitoring variant
- Extended duration sessions
- Specific configurations for bed scenarios

#### Statistics (`src/pages/Statistics.jsx`)

**Comprehensive analytics dashboard**

Features:
- **Mode Selection**: Normal vs. Behind-Wall data
- **User Filtering**: View all users or specific user
- **Date Range Filtering**: Filter by timestamp
- **Multiple Chart Types**:
  - **Run-Level Stats**: Aggregated per session
  - **Sample-Level Stats**: Individual measurements
  - **Histograms**: Distribution plots for HR, RR, Range, etc.
  - **Time Series**: Trends over time
  - **Scatter Plots**: Correlation visualization
  - **Correlation Matrix**: Heatmap of variable relationships
  - **Box Plots**: Statistical distribution
- **Summary Statistics**: Mean, median, min, max, std dev, count
- **CSV Export**: Download filtered data
- **Real-time Data Refresh**: Auto-updates when new data available

Backend Integration:
- Fetches from `eda_flask.py` API
- Endpoints: `/run-stats`, `/sample-stats`, `/histogram`, `/correlation`
- Supports query parameters: `mode`, `user_email`, `variable`, `bins`

### Components

#### Navbar (`src/components/Navbar.jsx`)

- Responsive navigation bar
- Auth-aware (shows login/logout)
- Links to all pages
- User email display

#### ProtectedRoute (`src/components/ProtectedRoute.jsx`)

- Authentication guard
- Redirects to login if not authenticated
- Uses Firebase `onAuthStateChanged`

---

## 🔧 Backend Services

### 1. Sensor Control API (`backend/app.py`)

**Port:** 5004

**Endpoints:**

#### POST `/run-sensor`

Start vital signs data collection.

**Request Body:**
```json
{
  "userEmail": "user@example.com",
  "configuration": 0
}
```

**Response:**
```json
{
  "success": true,
  "output": "Data collection completed. Saved to vital_signs_data_new.csv"
}
```

**Logic:**
1. Validate user exists in `users.csv`
2. Run `vst.py` script with user email and config
3. `vst.py` connects to radar, collects data, saves to CSV
4. Return success/failure

### 2. Statistics API (`backend/eda_flask.py`)

**Port:** 5001

**Endpoints:**

#### GET `/run-stats`

Fetch run-level aggregated statistics.

**Query Parameters:**
- `mode`: "normal" | "wall" (default: "normal")
- `user_email`: Filter by user (optional)

**Response:**
```json
{
  "data": [
    {
      "Run": 1,
      "User": "user@example.com",
      "Timestamp": "12-02-2026 14:30",
      "Config": 0,
      "Final_Accurate_HR": 72.5,
      "Final_Accurate_RR": 16.2,
      "Avg_HR_clean": 71.8,
      "Avg_RR_clean": 15.9,
      "Avg_Range": 0.75,
      "SQI": 0.92,
      "HR_SD": 3.2,
      "RR_SD": 1.1,
      "Range_SD": 0.05,
      "HR_P2P": 8.5,
      "RR_P2P": 4.2,
      "Range_Slope": 0.001,
      "Duration": 10.0
    }
  ]
}
```

#### GET `/sample-stats`

Fetch sample-level (individual measurements) statistics.

**Response:** Similar to `/run-stats` but individual samples, not aggregated.

#### GET `/histogram`

Get histogram data for a variable.

**Query Parameters:**
- `mode`: "normal" | "wall"
- `user_email`: Filter (optional)
- `variable`: "Heart_clean" | "Resp_clean" | "Range_clean" | ...
- `bins`: Number of bins (default: 20)

**Response:**
```json
{
  "bins": [60.0, 62.5, 65.0, ...],
  "counts": [5, 12, 18, ...]
}
```

#### GET `/correlation`

Get correlation matrix between numeric variables.

**Query Parameters:**
- `mode`: "normal" | "wall"
- `user_email`: Filter (optional)

**Response:**
```json
{
  "columns": ["Heart_clean", "Resp_clean", "Range_clean"],
  "data": [
    [1.0, 0.15, 0.02],
    [0.15, 1.0, -0.08],
    [0.02, -0.08, 1.0]
  ]
}
```

### 3. User Management API (`backend/add_user_api.py`)

**Endpoints:**

#### POST `/add-user`

Add user to users.csv (typically called after Firebase signup).

**Request:**
```json
{
  "email": "newuser@example.com"
}
```

---

## 🤖 Machine Learning

### Data Processing Pipeline

```
Raw Radar Data (vst.py)
    │
    ▼
Cleaning (cleaning_data.py)
    │  - Remove outliers (IQR method)
    │  - Interpolate missing values
    │  - Forward-fill short gaps
    ▼
Calibration (calibration.py)
    │  - Learn HR offsets from ground truth
    │  - Feature engineering (10 features)
    │  - Run-level aggregation
    │  - Calculate SQI
    ▼
Model Training
    │  - train_hr_model.py → hr_model.joblib
    │  - train_hr_classifier.py → hr_class_model.joblib, etc.
    ▼
Prediction (predict_with_model.py)
    │  - Load models
    │  - Predict on new data
    ▼
Analysis (hypotheses_tests.py)
    │  - Statistical tests
    │  - Validation
```

### Models

#### 1. Heart Rate Regression (`hr_model.joblib`)

**Algorithm:** XGBoost Regressor

**Features:**
```python
[
    "Avg_HR_clean",     # Average cleaned HR
    "Avg_RR_clean",     # Average cleaned RR
    "Avg_Range",        # Average distance
    "Range_SD",         # Range variability
    "HR_SD",            # HR variability
    "RR_SD",            # RR variability
    "HR_P2P",           # HR peak-to-peak amplitude
    "RR_P2P",           # RR peak-to-peak amplitude
    "Range_Slope",      # Range trend (movement)
    "SQI"               # Signal quality index
]
```

**Target:** `Final_Accurate_HR` (calibrated heart rate)

**Hyperparameters:**
- n_estimators: 350
- learning_rate: 0.04
- max_depth: 5
- subsample: 0.9
- colsample_bytree: 0.9

**Metrics:** Stored in `hr_model_metrics.json`

#### 2. HR Classifier (`hr_class_model.joblib`)

**Classes:**
- Normal (60-100 bpm)
- Elevated (>100 bpm)
- Low (<60 bpm)

#### 3. RR Classifier (`rr_class_model.joblib`)

**Classes:**
- Normal (12-20 bpm)
- Fast (>20 bpm)
- Slow (<12 bpm)

#### 4. Stress Classifier (`stress_class_model.joblib`)

**Classes:**
- Low Stress
- Moderate Stress
- High Stress

(Based on HR and RR combined patterns)

#### 5. Combined Vitals Classifier (`vitals_classifier.joblib`)

Multi-output classifier predicting all classes simultaneously.

### Calibration System

**File:** `data_analysis/calibration.py`

**Purpose:** Learn offsets between radar measurements and ground truth (smartwatch + finger pulse oximeter).

**Process:**
1. Load `VariousData.csv` (ground truth comparisons)
2. Calculate mean offset per configuration:
   - `offset_0`: Front-facing offset
   - `offset_1`: Side-facing offset
3. Apply offset to raw HR: `Final_Accurate_HR = Avg_HR_clean + offset`
4. Save offsets to `calibration_offsets.json`
5. Generate run-level features and statistics
6. Save to `final_run_stats_new_tryingsomething.csv`

**Incremental Mode:**
- Only processes new runs (based on timestamp)
- Appends to existing final_run_stats
- Maintains run numbering continuity

### Training Your Own Models

```bash
cd data_analysis

# Step 1: Clean data
python cleaning_data.py

# Step 2: Calibrate and extract features
python calibration.py

# Step 3: Train regression model
python train_hr_model.py

# Step 4: Train classifiers
python train_hr_classifier.py

# Step 5: Test predictions
python predict_with_model.py

# Step 6: Statistical analysis
python hypotheses_tests.py
```

**View Metrics:**

```bash
# Model performance
cat hr_model_metrics.json
cat hr_class_metrics.json

# Calibration offsets
cat calibration_offsets.json
```

---

## 🔄 Data Flow

### Data Collection Flow

```
User clicks "Start Monitoring"
    │
    ▼
Frontend sends POST /run-sensor
    │
    ▼
Backend validates user in users.csv
    │
    ▼
Backend runs: python vst.py <email> <config>
    │
    ▼
vst.py:
  │  1. Connect to radar (COM5, COM6)
  │  2. Send configuration file
  │  3. Start sensor
  │  4. Parse UART data frames
  │  5. Extract HR, RR, Range, waveforms
  │  6. Append to vital_signs_data_new.csv
  │  7. Display live plots
    ▼
Backend returns success/failure
    │
    ▼
Frontend displays result
```

### Data Processing Flow

```
vital_signs_data_new.csv (Raw)
    │
    ▼
cleaning_data.py
    │  - Remove outliers (IQR: Q1-1.5*IQR, Q3+1.5*IQR)
    │  - Drop NaN in critical columns
    │  - Interpolate (limit=3 samples)
    │  - Forward-fill (limit=2 samples)
    ▼
cleaned_vital_signs_new_tryingsomething.csv
    │
    ▼
calibration.py
    │  - Load calibration offsets
    │  - Group by Run
    │  - Aggregate features (mean, SD, P2P, slope, SQI)
    │  - Apply HR offset
    │  - Calculate Final_Accurate_HR
    ▼
final_run_stats_new_tryingsomething.csv
    │
    ▼
train_hr_model.py / train_hr_classifier.py
    │  - Load final_run_stats
    │  - Split train/test (80/20)
    │  - Train XGBoost models
    │  - Save models (.joblib)
    │  - Save metrics (.json)
    ▼
Models ready for prediction
```

### Statistics Flow

```
Frontend: Statistics.jsx
    │
    ▼
GET /run-stats?mode=normal&user_email=...
    │
    ▼
eda_flask.py:
  │  1. Load final_run_stats CSV
  │  2. Filter by mode (normal/wall)
  │  3. Filter by user_email (if provided)
  │  4. Return JSON
    ▼
Frontend renders charts
```

---

## 📡 API Reference

### Sensor Control API (Port 5004)

Base URL: `http://localhost:5004`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/run-sensor` | POST | Start data collection |

### Statistics API (Port 5001)

Base URL: `http://127.0.0.1:5001`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/run-stats` | GET | Get run-level statistics |
| `/sample-stats` | GET | Get sample-level statistics |
| `/histogram` | GET | Get histogram data |
| `/correlation` | GET | Get correlation matrix |
| `/time-series` | GET | Get time series data (future) |

**Common Query Parameters:**

- `mode`: "normal" or "wall"
- `user_email`: Filter by specific user
- `variable`: Variable name for histograms
- `bins`: Number of bins (default: 20)

---

## 🛠️ Development

### Code Style

**JavaScript/React:**
- ESLint configuration in `eslint.config.js`
- Prettier recommended
- Use functional components with hooks
- Destructure props

**Python:**
- PEP 8 style guide
- Use type hints where applicable
- Docstrings for functions

### Testing

**Frontend Testing:**

```bash
# Add testing libraries
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom

# Run tests
npm test
```

**Backend Testing:**

```bash
# Install pytest
pip install pytest pytest-flask

# Run tests
pytest backend/tests/
```

### Adding New Pages

1. Create component: `src/pages/NewPage.jsx`
2. Add route in `src/GPPApp.jsx`:

```jsx
<Route path="/new-page" element={<NewPage />} />
```

3. Add navbar link in `src/components/Navbar.jsx`

### Adding New API Endpoints

1. Edit `backend/eda_flask.py` or `backend/app.py`
2. Add route handler:

```python
@app.route('/new-endpoint', methods=['GET'])
def new_endpoint():
    # Logic here
    return jsonify({"data": ...})
```

3. Update CORS if needed
4. Call from frontend using `fetch()` or `axios`

---

## 🚀 Deployment

### Frontend Deployment

**Build:**

```bash
npm run build
```

**Deploy to:**
- **Vercel**: `vercel deploy`
- **Netlify**: Drag `dist/` folder
- **Firebase Hosting**: `firebase deploy`
- **Static hosting**: Upload `dist/` contents

**Environment Variables:**

Set in hosting platform:
```
VITE_EDA_BASE=https://your-backend-url.com:5001
VITE_SENSOR_API=https://your-backend-url.com:5004
```

### Backend Deployment

**Options:**

1. **Heroku**:
   - Add `Procfile`: `web: gunicorn -k eventlet -w 1 backend.app:app`
   - Deploy with Git

2. **AWS EC2**:
   - Install Python, dependencies
   - Run with `gunicorn` or `waitress`
   - Configure security groups for ports

3. **Docker**:

```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ ./backend/
COPY data_analysis/ ./data_analysis/
CMD ["python", "backend/app.py"]
```

**Important:** Radar hardware must be connected to deployment machine (local/on-premise server recommended).

---

## 🐛 Troubleshooting

### Common Issues

**1. "Module not found" errors**

```bash
# Frontend
npm install

# Backend
pip install -r requirements.txt
```

**2. CORS errors in browser**

- Check `CORS(app)` is enabled in Flask
- Verify frontend is requesting correct URL
- Check browser console for details

**3. Firebase auth not working**

- Verify `firebaseConfig` in `src/firebase.js`
- Check Firebase console for auth enablement
- Clear browser cache

**4. Charts not rendering**

- Check Chart.js version compatibility
- Verify data format matches chart expectations
- Check browser console for errors

**5. Backend not connecting to radar**

- Check COM ports in Device Manager
- Update `USER_PORT` and `DATA_PORT` in `vst.py`
- Verify sensor is powered on
- Try unplugging/replugging USB

**6. CSV files not found**

- Update absolute paths in `eda_flask.py`
- Ensure directories exist
- Check write permissions

**7. Model files not found**

- Train models first: `python train_hr_model.py`
- Verify paths in `predict_with_model.py`
- Check `data_analysis/` directory

### Debug Tips

- **Frontend**: Use React DevTools, check Network tab
- **Backend**: Check terminal logs, add `print()` statements
- **Data**: Inspect CSV files directly, check for empty/corrupt data
- **Models**: Load models in Python REPL to verify
- **Radar**: Use TI's GUI tool to test sensor independently

---

## 📞 Support

**Issues:** Open an issue on GitHub

**Documentation:** See main project README

**Email:** support@respirationhealth.com

---

## 📄 License

MIT License - See main project LICENSE file

---

<div align="center">

**Built with ❤️ using React, Flask, and mmWave technology**

[⬆ Back to Top](#gpp-project---vital-signs-monitoring-web-application)

</div>
