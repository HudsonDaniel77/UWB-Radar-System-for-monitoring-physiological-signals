# RespirationHealth - mmWave Radar Vital Signs Monitoring System

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![React](https://img.shields.io/badge/React-18.3.1-blue)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green)

**Advanced contactless vital signs monitoring using Texas Instruments mmWave radar technology**

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Hardware Requirements](#hardware-requirements)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Projects](#projects)
- [Data Analysis & Machine Learning](#data-analysis--machine-learning)
- [Usage](#usage)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## 🎯 Overview

**RespirationHealth** is a comprehensive health monitoring platform that leverages Texas Instruments mmWave radar technology to measure vital signs (heart rate, respiration rate, and distance) without physical contact. The system provides real-time monitoring, advanced data analytics, and machine learning-powered calibration for accurate health tracking.

### Key Capabilities

- **Contactless Monitoring**: Non-invasive vital signs detection using mmWave radar
- **Multi-Mode Operation**: Normal front-facing, behind-wall detection, and sleep monitoring
- **Real-Time Visualization**: Live charts and waveforms during data collection
- **Machine Learning Integration**: XGBoost-based models for calibration and prediction
- **User Management**: Firebase authentication with user-specific data tracking
- **Comprehensive Analytics**: Statistical analysis, EDA, and hypothesis testing
- **Web Dashboard**: Modern React-based interface for monitoring and analysis

---

## ✨ Features

### Core Features

- ✅ **Real-time vital signs monitoring** (Heart Rate, Respiration Rate, Range)
- ✅ **Multiple detection modes** (Front-facing, Behind-wall, Sleep monitoring)
- ✅ **Live data visualization** with interactive charts
- ✅ **Machine learning calibration** using XGBoost regression
- ✅ **Multi-class health status classification** (HR, RR, Stress levels)
- ✅ **User authentication** with Firebase
- ✅ **Historical data analysis** with comprehensive statistics
- ✅ **CSV data export** for further analysis
- ✅ **Signal quality indicators** (SQI) for reliability assessment
- ✅ **Automated data cleaning** and preprocessing
- ✅ **Hypothesis testing** for statistical validation
- ✅ **Configuration profiles** for different monitoring scenarios

### Advanced Features

- **Adaptive Calibration**: Learns from smartwatch and finger pulse oximeter data
- **Change Detection**: Alerts for significant vital sign variations
- **Session Management**: Tracks multiple monitoring sessions per user
- **Data Aggregation**: Run-level statistics and sample-level tracking
- **Waveform Analysis**: FFT-based frequency domain analysis
- **Range Profiling**: Distance-based vital signs correlation
- **Multi-user Support**: Individual user data segregation

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React + Vite)                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • Authentication (Firebase)                              │  │
│  │  • Real-time Charts (Chart.js)                           │  │
│  │  • Statistics Dashboard                                   │  │
│  │  • Sensor Control Interface                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Backend Services (Flask)                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • Sensor Control API (Port 5004)                        │  │
│  │  • EDA & Statistics API (Port 5001)                      │  │
│  │  • User Management API                                   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Data Processing Pipeline                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  1. Radar Data Collection (vst.py)                       │  │
│  │  2. Data Cleaning (cleaning_data.py)                     │  │
│  │  3. Calibration (calibration.py)                         │  │
│  │  4. ML Prediction (XGBoost models)                       │  │
│  │  5. Statistical Analysis (hypotheses_tests.py)           │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Hardware (TI mmWave Radar)                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • IWR6843/AWR6843 mmWave Sensor                         │  │
│  │  • User UART (COM5 @ 115200)                             │  │
│  │  • Data UART (COM6 @ 921600)                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Hardware Requirements

### Required Hardware

- **TI mmWave Radar Sensor**: IWR6843 or AWR6843 evaluation module
- **USB Connection**: For UART communication (dual COM ports)
- **PC/Laptop**: Windows OS with Python 3.8+ installed
- **Optional**: Smartwatch or finger pulse oximeter for calibration

### Sensor Configuration

- **User Port**: COM5 @ 115200 baud (configuration commands)
- **Data Port**: COM6 @ 921600 baud (radar data stream)
- **Profile**: Vital Signs 20fps configuration

---

## 📁 Project Structure

```
RespirationHealth/
│
├── gpp-project/                    # Main application (front-facing mode)
│   ├── src/                        # React frontend
│   │   ├── pages/                  # Application pages
│   │   │   ├── Home.jsx
│   │   │   ├── RunSensor.jsx       # Sensor control interface
│   │   │   ├── Statistics.jsx      # Analytics dashboard
│   │   │   ├── Login.jsx
│   │   │   └── Signup.jsx
│   │   ├── components/             # Reusable components
│   │   ├── firebase.js             # Firebase configuration
│   │   └── GPPApp.jsx              # Main app component
│   │
│   ├── backend/                    # Flask backend services
│   │   ├── app.py                  # Main sensor control API
│   │   ├── vst.py                  # Vital signs tracker script
│   │   ├── eda_flask.py            # Statistics & EDA API
│   │   ├── add_user_api.py         # User management
│   │   └── users.csv               # User database
│   │
│   ├── data_analysis/              # ML & analytics
│   │   ├── cleaning_data.py        # Data preprocessing
│   │   ├── calibration.py          # ML calibration
│   │   ├── train_hr_model.py       # Heart rate model training
│   │   ├── train_hr_classifier.py  # HR classification
│   │   ├── hypotheses_tests.py     # Statistical tests
│   │   ├── predict_with_model.py   # Inference script
│   │   ├── hr_model.joblib         # Trained regression model
│   │   ├── vitals_classifier.joblib # Multi-class classifier
│   │   └── *.json                  # Model metrics & configs
│   │
│   ├── vital_signs_data/           # Collected data storage
│   └── package.json                # Frontend dependencies
│
├── gpp-project-behindwall/         # Behind-wall detection variant
│   ├── src/                        # React frontend (similar structure)
│   ├── backend/                    # Flask backend (adapted for wall penetration)
│   └── data_analysis/              # ML models for behind-wall data
│
├── vital_signs_tracker.py          # Standalone data collection script
├── radar_data.csv                  # Sample radar data
├── package.json                    # Root dependencies
└── README.md                       # This file
```

---

## 🚀 Installation

### Prerequisites

- **Python 3.8+** with pip
- **Node.js 16+** with npm
- **Git** (for version control)
- **TI mmWave Radar** connected and drivers installed

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/RespirationHealth.git
cd RespirationHealth
```

### Step 2: Install Root Dependencies (Optional)

```bash
npm install
```

This installs utilities for data parsing (PapaParse, XLSX, Recharts).

### Step 3: Setup Main Project

```bash
cd gpp-project

# Install frontend dependencies
npm install

# Install backend dependencies
pip install flask flask-cors pandas numpy scipy scikit-learn xgboost joblib matplotlib pyserial
```

### Step 4: Setup Behind-Wall Project (Optional)

```bash
cd ../gpp-project-behindwall

# Install frontend dependencies
npm install

# Install backend dependencies (if different)
pip install -r requirements.txt
```

### Step 5: Configure Firebase

1. Create a Firebase project at [console.firebase.google.com](https://console.firebase.google.com)
2. Enable **Authentication** (Email/Password)
3. Create a **Firestore Database**
4. Copy your Firebase config and update `gpp-project/src/firebase.js`

---

## 🎬 Quick Start

### Running the Main Application

**Terminal 1: Start Flask Backend**

```bash
cd gpp-project/backend
python app.py          # Sensor control API (port 5004)
```

**Terminal 2: Start EDA API**

```bash
cd gpp-project/backend
python eda_flask.py    # Statistics API (port 5001)
```

**Terminal 3: Start React Frontend**

```bash
cd gpp-project
npm run dev            # Vite dev server (port 5173)
```

**Access the Application**: Open [http://localhost:5173](http://localhost:5173)

### Standalone Data Collection

For direct radar data collection without the web interface:

```bash
python vital_signs_tracker.py
```

This will:
- Connect to the radar sensor
- Configure with default profile
- Collect 10 seconds of data
- Save to `vital_signs_<timestamp>.csv`
- Display live plots

---

## 📦 Projects

### 1. gpp-project (Main Application)

Full-featured web application for front-facing vital signs monitoring.

**Features:**
- Real-time sensor data collection
- Live visualization
- User authentication
- Historical data analysis
- Machine learning calibration

**See:** [gpp-project/README.md](gpp-project/README.md)

### 2. gpp-project-behindwall (Behind-Wall Detection)

Specialized variant for monitoring through walls (e.g., sleep monitoring).

**Features:**
- Enhanced signal processing for wall penetration
- Adapted ML models for attenuated signals
- Sleep tracking optimizations

**See:** [gpp-project-behindwall/README.md](gpp-project-behindwall/README.md)

---

## 🤖 Data Analysis & Machine Learning

### Pipeline Overview

1. **Data Collection** (`vst.py`): Raw radar data with waveforms
2. **Cleaning** (`cleaning_data.py`): Outlier removal, interpolation
3. **Calibration** (`calibration.py`): Offset learning, feature engineering
4. **Model Training**: XGBoost regression and classification
5. **Prediction** (`predict_with_model.py`): Real-time inference
6. **Analysis** (`hypotheses_tests.py`): Statistical validation

### Machine Learning Models

#### Regression Models

- **Heart Rate Predictor** (`hr_model.joblib`)
  - Algorithm: XGBoost Regressor
  - Features: 10 engineered features (HR_clean, RR_clean, Range, SDs, P2P, Slope, SQI)
  - Metrics: MAE, RMSE, R²

#### Classification Models

- **HR Class Classifier** (`hr_class_model.joblib`): Normal/Elevated/Low
- **RR Class Classifier** (`rr_class_model.joblib`): Normal/Fast/Slow
- **Stress Classifier** (`stress_class_model.joblib`): Low/Moderate/High
- **Combined Vitals Classifier** (`vitals_classifier.joblib`): Multi-output

### Feature Engineering

```python
Key Features:
- Avg_HR_clean, Avg_RR_clean, Avg_Range
- Range_SD, HR_SD, RR_SD (variability)
- HR_P2P, RR_P2P (peak-to-peak amplitude)
- Range_Slope (movement trend)
- SQI (signal quality index)
```

### Training Your Own Models

```bash
cd gpp-project/data_analysis

# Train heart rate regression model
python train_hr_model.py

# Train HR classifier
python train_hr_classifier.py

# View metrics
cat hr_model_metrics.json
```

---

## 📖 Usage

### Web Interface Usage

1. **Sign Up/Login**: Create an account or log in with existing credentials
2. **Run Sensor**: 
   - Navigate to "Run Sensor" page
   - Select configuration (0: Front, 1: Side)
   - Click "Start Monitoring"
   - View real-time charts
3. **View Statistics**:
   - Navigate to "Statistics" page
   - Select user and date range
   - Explore charts: histograms, time series, scatter plots, correlation matrices

### Programmatic Usage

```python
from gpp-project.backend import vst
import sys

# Collect data for user with configuration 1
user_email = "user@example.com"
config = 1
sys.argv = ["vst.py", user_email, str(config)]

# This will run data collection and save to CSV
vst.main()
```

### API Usage

**Start Sensor Collection**

```bash
curl -X POST http://localhost:5004/run-sensor \
  -H "Content-Type: application/json" \
  -d '{
    "userEmail": "user@example.com",
    "configuration": 0
  }'
```

**Fetch Statistics**

```bash
curl http://localhost:5001/run-stats?mode=normal&user_email=user@example.com
```

---

## ⚙️ Configuration

### Radar Configuration

Edit COM ports and paths in `gpp-project/backend/vst.py`:

```python
USER_PORT = 'COM5'         # Configuration UART
DATA_PORT = 'COM6'         # Data UART
USER_BAUD = 115200
DATA_BAUD = 921600
CFG_FILE = r"C:\ti\...\xwr68xx_profile_VitalSigns_20fps_Front.cfg"
```

### Backend Configuration

**File Paths** (`eda_flask.py`):

```python
NORMAL_SAMPLE_CSV = r"...\cleaned_vital_signs_new_tryingsomething.csv"
NORMAL_RUN_CSV = r"...\final_run_stats_new_tryingsomething.csv"
WALL_SAMPLE_CSV = r"...\cleaned_vital_signs_new.csv"
WALL_RUN_CSV = r"...\final_run_stats_new.csv"
```

### Frontend Configuration

**Backend URLs** (`Statistics.jsx`):

```javascript
const EDA_BACKEND_BASE = import.meta.env.VITE_EDA_BASE || "http://127.0.0.1:5001";
```

Create `.env` file:

```
VITE_EDA_BASE=http://localhost:5001
```

---

## 📡 API Documentation

### Sensor Control API (Port 5004)

#### POST /run-sensor

Start radar data collection.

**Request:**
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
  "output": "Data collection completed..."
}
```

### Statistics API (Port 5001)

#### GET /run-stats

Fetch run-level statistics.

**Parameters:**
- `mode`: "normal" | "wall"
- `user_email`: Filter by user (optional)

**Response:**
```json
{
  "data": [
    {
      "Run": 1,
      "User": "user@example.com",
      "Timestamp": "12-02-2026 14:30",
      "Final_Accurate_HR": 72.5,
      "Final_Accurate_RR": 16.2,
      ...
    }
  ]
}
```

#### GET /sample-stats

Fetch sample-level statistics.

#### GET /histogram

Get histogram data for a specific variable.

#### GET /correlation

Get correlation matrix between variables.

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/YourFeature`
3. **Commit changes**: `git commit -m 'Add YourFeature'`
4. **Push to branch**: `git push origin feature/YourFeature`
5. **Open a Pull Request**

### Development Guidelines

- Follow PEP 8 for Python code
- Use ESLint config for JavaScript/React
- Add unit tests for new features
- Update documentation for API changes
- Test with actual radar hardware before submitting

---

## 🐛 Troubleshooting

### Common Issues

**1. COM Port Not Found**

```
Error: could not open port 'COM5': FileNotFoundError
```

**Solution:** Check Device Manager for correct COM port numbers. Update `USER_PORT` and `DATA_PORT` in `vst.py`.

**2. No Data Received**

**Solution:** 
- Verify sensor is powered on
- Check USB connection
- Ensure sensor is running (green LED)
- Try resetting sensor

**3. Import Errors (Python)**

```
ModuleNotFoundError: No module named 'flask'
```

**Solution:** Install missing packages:
```bash
pip install flask flask-cors pandas numpy
```

**4. Firebase Authentication Failure**

**Solution:** 
- Check Firebase config in `firebase.js`
- Verify Firebase Authentication is enabled
- Check network connectivity

**5. ML Model Not Found**

```
FileNotFoundError: hr_model.joblib not found
```

**Solution:** Train models first:
```bash
cd gpp-project/data_analysis
python train_hr_model.py
```

### Debugging Tips

- Check Flask logs in terminal for API errors
- Use browser DevTools Network tab for frontend issues
- Verify CSV file paths exist and are writable
- Ensure adequate disk space for data collection

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 👥 Authors

- **Project Team** - Grand Project, SSN College

---

## 🙏 Acknowledgments

- **Texas Instruments** for mmWave radar SDK and hardware
- **TI mmWave Industrial Toolbox** for configuration profiles
- **Firebase** for authentication infrastructure
- **Chart.js** for visualization components
- **Scikit-learn & XGBoost** for ML frameworks

---

## 📞 Support

For issues, questions, or contributions:

- **GitHub Issues**: [Create an issue](https://github.com/yourusername/RespirationHealth/issues)
- **Email**: support@respirationhealth.com
- **Documentation**: [Wiki](https://github.com/yourusername/RespirationHealth/wiki)

---

<div align="center">

**Made with ❤️ for contactless health monitoring**

[🌟 Star this repo](https://github.com/yourusername/RespirationHealth) | [🐛 Report Bug](https://github.com/yourusername/RespirationHealth/issues) | [✨ Request Feature](https://github.com/yourusername/RespirationHealth/issues)

</div>