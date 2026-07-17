import React, { useState, useEffect } from "react";
import WaveformDisplay from "../components/WaveformDisplay";

function ErrorPopup({ message, onClose, title = "Message" }) {
  if (!message) return null;

  return (
    <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50 backdrop-blur-sm">
      <div className="bg-white border border-gray-300 rounded-2xl p-6 max-w-md w-[90%] text-gray-800 shadow-2xl">

        <h2 className="text-2xl font-bold mb-4 text-red-400 text-center">
          {title}
        </h2>

        <p 
          className="mb-6 leading-relaxed whitespace-pre-wrap text-gray-800"
          style={{
            maxHeight: "300px",
            overflowY: "auto",
            textAlign: "left",
            wordBreak: "break-word"
          }}
        >
          {message}
        </p>


        <div className="flex justify-center">
          <button
            onClick={onClose}
            className="px-6 py-2 border border-gray-300 rounded-lg text-gray-800 transition outline-none ring-0 
                       focus:ring-0 hover:bg-gray-100 hover:border-gray-400"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
}

function RunSensor() {
  useEffect(() => {
    document.title = "Radarix | Run Sensor";
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:43',message:'Component mounted, checking backend health',data:{timestamp:Date.now()},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'D'})}).catch(()=>{});
    // #endregion
    
    // Health check on mount
    fetch("http://localhost:5000/", { method: "GET" })
      .then((res) => {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:48',message:'Health check response',data:{status:res.status,ok:res.ok},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'D'})}).catch(()=>{});
        // #endregion
        return res.json();
      })
      .then((data) => {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:52',message:'Health check success',data:{status:data.status},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'D'})}).catch(()=>{});
        // #endregion
      })
      .catch((error) => {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:56',message:'Health check failed',data:{errorName:error.name,errorMessage:error.message},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'D'})}).catch(()=>{});
        // #endregion
      });
  }, []);

  const [popupMessage, setPopupMessage] = useState("");
  const [popupTitle, setPopupTitle] = useState("");

  const [config, setConfig] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [showWaveforms, setShowWaveforms] = useState(false);

  // ML RESULTS
  const [predictedHR, setPredictedHR] = useState(null);
  const [hrClass, setHrClass] = useState(null);
  const [rrClass, setRrClass] = useState(null);
  const [stressClass, setStressClass] = useState(null);

  const userEmail = localStorage.getItem("loggedUser");

const handleRunSensor = () => {
  // #region agent log
  console.log('[DEBUG] handleRunSensor called', {userEmail, config});
  fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:84',message:'handleRunSensor called',data:{userEmail:userEmail,config:config},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'A'})}).catch((e)=>console.error('Log error:',e));
  // #endregion

  if (!userEmail) {
    // #region agent log
    console.log('[DEBUG] No userEmail, returning early');
    fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:89',message:'Early return: no userEmail',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    setPopupTitle("Login Required");
    setPopupMessage("Please log in again. User email not found.");
    return;
  }

  if (config === null) {
    // #region agent log
    console.log('[DEBUG] No config, returning early');
    fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:95',message:'Early return: no config',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    setPopupTitle("Configuration Missing");
    setPopupMessage("Please select Front or Back configuration before running the sensor.");
    return;
  }

  // 🔥 Show processing popup IMMEDIATELY
  setPopupTitle("Processing...");
  setPopupMessage("Starting sensor...\nCollecting data...\nCleaning...\nCalibrating...\nExtracting Features...\nAnalysing Data...");

  // #region agent log
  const backendUrl = "http://localhost:5000/run-sensor";
  console.log('[DEBUG] About to fetch', backendUrl);
  fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:107',message:'Before fetch call',data:{url:backendUrl,method:'POST',userEmail:userEmail,config:config},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'A'})}).catch((e)=>console.error('Log error:',e));
  // #endregion

  fetch(backendUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      userEmail: userEmail,
      configuration: config
    })
  })
    .then((res) => {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:86',message:'Fetch response received',data:{status:res.status,statusText:res.statusText,ok:res.ok,url:res.url},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      return res.json();
    })
    .then((data) => {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:87',message:'Response data parsed',data:{success:data.success,hasError:!!data.error,hasMlResults:!!data.ml_results},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      if (data.success) {

        // ---- SHOW SUMMARY POPUP ----
        setPopupTitle("Vital Signs Summary");
        setPopupMessage(data.stats_text);

        // ---- SHOW ML RESULTS ON SCREEN ----
        if (data.ml_results) {
          const r = data.ml_results;

          setPredictedHR(r.Predicted_HR);
          setHrClass(r.HR_Class);
          setRrClass(r.RR_Class);
          setStressClass(r.Stress_Class);
          
          // Activate waveform display after successful sensor run
          setShowWaveforms(true);
        }

      } else {
        setPopupTitle("Sensor Error!");
        setPopupMessage(data.error || "Unknown error occurred while running sensor.");
      }
    })
    .catch((error) => {
      // #region agent log
      console.error('[DEBUG] Fetch error:', error);
      fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:149',message:'Fetch error caught',data:{errorName:error.name,errorMessage:error.message,errorStack:error.stack?.substring(0,200),url:backendUrl},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'C'})}).catch((e)=>console.error('Log error:',e));
      // #endregion
      setPopupTitle("Connection Error!");
      setPopupMessage(`Cannot connect to backend server at ${backendUrl}.\n\nError: ${error.message}\n\nPlease ensure the backend server is running on port 5000.\n\nStart it with: python gpp-project/backend/api/pipeline.py`);
    });
};



  // COLOR FUNCTION ------------------------
const getColorClass = (label) => {
  if (!label) return "text-gray-500";

  const value = label.toLowerCase();

  if (["normal", "relaxed"].includes(value))
    return "text-green-600";

  if (["low", "moderate"].includes(value))
    return "text-yellow-600";

  if (["high", "stressed"].includes(value))
    return "text-red-600";

  return "text-gray-500";
};

  //----------------------------------------

  // ---------------------------------------------
  // PIPELINE: Upload → Cleaning → Calibration → ML
  // ---------------------------------------------
  const handleUploadCsv = async () => {
    if (!selectedFile) {
      setPopupTitle("No File Selected");
      setPopupMessage("Please upload a CSV file first.");
      return;
    }

    try {
      // Upload file
      setPopupTitle("Uploading...");
      setPopupMessage("Uploading CSV file...");
      
      const formData = new FormData();
      formData.append("file", selectedFile);

      // #region agent log
      const uploadUrl = "http://localhost:5000/upload";
      fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:155',message:'Before upload fetch',data:{url:uploadUrl},timestamp:Date.now(),sessionId:'debug-session',runId:'post-fix',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      const uploadRes = await fetch(uploadUrl, {
        method: "POST",
        body: formData
      });

      const uploadData = await uploadRes.json();
      if (!uploadData.message) {
        setPopupTitle("Upload Error");
        setPopupMessage(uploadData.error || "Failed to upload CSV file.");
        return;
      }

      // Run pipeline
      setPopupTitle("Processing...");
      setPopupMessage("Cleaning...\nCalibrating...\nExtracting Features...\nAnalysing Data...");

      // #region agent log
      const pipelineUrl = "http://localhost:5000/run_pipeline";
      fetch('http://127.0.0.1:7242/ingest/75ea5f5b-2fac-40b5-9816-a081dabd7fca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'RunSensor.jsx:171',message:'Before pipeline fetch',data:{url:pipelineUrl},timestamp:Date.now(),sessionId:'debug-session',runId:'post-fix',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      const pipeRes = await fetch(pipelineUrl, { method: "POST" });
      const pipeData = await pipeRes.json();

      if (pipeData.ml_results) {
        const r = pipeData.ml_results;

        // Store all ML results
        setPredictedHR(r.Predicted_HR);
        setHrClass(r.HR_Class);
        setRrClass(r.RR_Class);
        setStressClass(r.Stress_Class);

        // Activate waveform display after successful processing
        setShowWaveforms(true);

        setPopupTitle("Success!");
        setPopupMessage("Uploaded & Processed Successfully!\nFinal results displayed below.");

      } else {
        setPopupTitle("Pipeline Error");
        setPopupMessage(pipeData.error || "Pipeline failed.");
      }

    } catch (error) {
      setPopupTitle("Server Error");
      setPopupMessage("Backend not reachable. Please run Flask backend.");
    }
  };

  // UI START --------------------------------------------------
  return (
    <div className="flex flex-col items-center justify-start w-screen min-h-screen bg-white px-6 md:px-12 lg:px-20 pt-20 text-gray-800">

      <h1 className="text-5xl md:text-6xl font-extrabold mb-4">Run Sensor</h1>

      <h2 className="text-2xl md:text-3xl font-semibold mb-6 text-center">
        Start and View Real-Time Sensor Data
      </h2>

      <p className="text-lg md:text-xl max-w-20xl text-center mb-10">
        Use this page to initiate the UWB radar sensor and process physiological signals instantly.
      </p>

      {/* Configuration Section */}
      <div className="w-full max-w-xl bg-white border border-gray-300 rounded-xl p-6 mt-4 shadow-lg">
        <label className="block text-lg font-semibold mb-4 text-center">
          Choose the Person Configuration
        </label>

        <div className="flex flex-col gap-4">
          <label
            className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer border 
              ${config === 0 ? "border-gray-400 bg-gray-100" : "border-gray-300 bg-gray-50 hover:border-gray-400"}`}
          >
            <input
              type="radio"
              name="configuration"
              value="0"
              checked={config === 0}
              onChange={() => setConfig(0)}
              className="w-4 h-4"
            />
            <span className="text-gray-800">Front Configuration</span>
          </label>

          <label
            className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer border 
              ${config === 1 ? "border-gray-400 bg-gray-100" : "border-gray-300 bg-gray-50 hover:border-gray-400"}`}
          >
            <input
              type="radio"
              name="configuration"
              value="1"
              checked={config === 1}
              onChange={() => setConfig(1)}
              className="w-4 h-4"
            />
            <span className="text-gray-800">Back Configuration</span>
          </label>
        </div>
      </div>

      {/* Run Sensor Button */}
      <button
        onClick={handleRunSensor}
        className="mt-4 px-6 py-3 border border-gray-300 text-gray-800 rounded-lg transition hover:bg-gray-100 hover:border-gray-400"
      >
        Run the Sensor
      </button>
      

{/* ---------------- CLEAN SENTENCE OUTPUT ---------------- */}
{predictedHR && (
  <div className="w-full max-w-3xl mt-10 text-center">

    {/* Heart Rate sentence */}
    <p className="text-2xl text-gray-800 mb-6">
      Your estimated heart rate is{" "}
      <span className="text-gray-900 font-bold">{predictedHR} bpm</span>.
    </p>

    {/* HR Class sentence */}
    <p className="text-xl text-gray-600 mb-3">
      Your heart rate category is{" "}
      <span className={`font-bold ${getColorClass(hrClass)}`}>
        {hrClass}
      </span>.
    </p>

    {/* RR Class sentence */}
    <p className="text-xl text-gray-600 mb-3">
      Your breathing rate is classified as{" "}
      <span className={`font-bold ${getColorClass(rrClass)}`}>
        {rrClass}
      </span>.
    </p>

    {/* Real-time Waveform Display */}
    <WaveformDisplay isActive={showWaveforms} userEmail={userEmail} />
  </div>
)}


      {/* Popup */}
      <ErrorPopup
        message={popupMessage}
        title={popupTitle}
        onClose={() => setPopupMessage("")}
      />

      {/* Video Tutorial */}
      <h3 className="text-3xl font-bold mt-16 mb-6 text-center">
        Steps to Setup the Sensor
      </h3>

      <div className="w-full max-w-3xl aspect-video rounded-xl overflow-hidden shadow-xl border border-gray-300">
        <iframe
          className="w-full h-full"
          src="https://www.youtube.com/embed/5CVs4GR3-nc"
          title="Sensor Setup Tutorial"
          frameBorder="0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        ></iframe>
      </div>

      <br />
      <div className="w-full max-w-7xl mt-8 mb-12 text-center text-gray-600">
        <small>Radarix, 2025</small>
      </div>
    </div>
  );
}

export default RunSensor;
