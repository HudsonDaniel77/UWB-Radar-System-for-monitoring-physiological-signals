import React, { useState, useEffect } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

function ErrorPopup({ message, onClose, title = "Message" }) {
  if (!message) return null;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm">
      <div className="bg-[#0f0f0f] border border-gray-700 rounded-2xl p-6 max-w-md w-[90%] text-gray-200 shadow-2xl shadow-black/70">

        <h2 className="text-2xl font-bold mb-4 text-red-400 text-center">
          {title}
        </h2>

        <p 
          className="mb-6 leading-relaxed whitespace-pre-wrap text-gray-200"
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
            className="px-6 py-2 border border-gray-600 rounded-lg text-gray-200 transition outline-none ring-0 
                       focus:ring-0 hover:bg-[#1a1a1a] hover:border-gray-400 hover:text-white"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
}

function RunSensorBehindWall() {
  useEffect(() => {
    document.title = "Radarix | Behind Wall Detection";
  }, []);

  const [popupMessage, setPopupMessage] = useState("");
  const [popupTitle, setPopupTitle] = useState("");

  const [config, setConfig] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);

  // ML RESULTS
  const [predictedHR, setPredictedHR] = useState(null);
  const [hrClass, setHrClass] = useState(null);
  const [rrClass, setRrClass] = useState(null);
  const [stressClass, setStressClass] = useState(null);

  // WAVEFORM DATA
  const [waveform, setWaveform] = useState(null);

  const userEmail = localStorage.getItem("loggedUser");

  const handleRunSensor = () => {
    setPredictedHR(null);
    setHrClass(null);
    setRrClass(null);
    setStressClass(null);
    setWaveform(null);

    if (!userEmail) {
      setPopupTitle("Login Required");
      setPopupMessage("Please log in again. User email not found.");
      return;
    }

    if (config === null) {
      setPopupTitle("Configuration Missing");
      setPopupMessage("Please select Front or Back configuration before running the sensor.");
      return;
    }

    // Show processing popup IMMEDIATELY
    setPopupTitle("Processing...");
    setPopupMessage("Starting behind-wall sensor...\nCollecting data...\nCleaning...\nCalibrating...\nExtracting Features...\nAnalysing Data...");

    fetch("http://localhost:5002/bw/run-sensor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        userEmail: userEmail,
        configuration: config
      })
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          // ---- SHOW SUMMARY POPUP ----
          setPopupTitle("Vital Signs Summary");
          setPopupMessage(data.stats_text);

          // ---- STORE WAVEFORM DATA ----
          if (data.waveform && Object.keys(data.waveform).length > 0) {
            setWaveform(data.waveform);
          }

          // ---- SHOW ML RESULTS ON SCREEN ----
          if (data.ml_results) {
            console.log("SOURCE: RUN_SENSOR_BEHINDWALL", data.ml_results);
            const r = data.ml_results;

            setPredictedHR(r.Predicted_HR);
            setHrClass(r.HR_Class);
            setRrClass(r.RR_Class);
            setStressClass(r.Stress_Class);
          }
        } else {
          setPopupTitle("Sensor Error!");
          setPopupMessage(data.error || "Unknown error occurred while running behind-wall sensor.");
        }
      })
      .catch(() => {
        setPopupTitle("Connection Error!");
        setPopupMessage("Cannot connect to backend.\nMake sure the pipeline server is running on port 5002.");
      });
  };

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

      const uploadRes = await fetch("http://localhost:5002/bw/upload", {
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

      const pipeRes = await fetch("http://localhost:5002/bw/run_pipeline", { method: "POST" });
      const pipeData = await pipeRes.json();

      if (pipeData.ml_results) {
        console.log("SOURCE: RUN_PIPELINE_BEHINDWALL", pipeData.ml_results);

        const r = pipeData.ml_results;

        setPredictedHR(r.Predicted_HR);
        setHrClass(r.HR_Class);
        setRrClass(r.RR_Class);
        setStressClass(r.Stress_Class);

        setPopupTitle("Success!");
        setPopupMessage("Uploaded & Processed Successfully!\nFinal results displayed below.");
      } else {
        setPopupTitle("Pipeline Error");
        setPopupMessage(pipeData.error || "Pipeline failed.");
      }

    } catch (error) {
      setPopupTitle("Server Error");
      setPopupMessage("Backend not reachable. Please run the Flask backend on port 5002.");
    }
  };

  // COLOR FUNCTION
  const getColorClass = (label) => {
    if (!label) return "text-gray-300";
    const value = label.toLowerCase();
    if (["normal", "relaxed"].includes(value)) return "text-green-400";
    if (["low", "moderate"].includes(value)) return "text-yellow-400";
    if (["high", "stressed"].includes(value)) return "text-red-400";
    return "text-gray-300";
  };

  // UI
  return (
    <div className="flex flex-col items-center justify-start w-screen min-h-screen bg-black px-6 md:px-12 lg:px-20 pt-20 text-gray-200">

      <h1 className="text-5xl md:text-6xl font-extrabold mb-4">Detect Vital Signs with an Obstacle</h1>

      <h2 className="text-2xl md:text-3xl font-semibold mb-6 text-center">
        Start and View Real-Time Behind-Wall Sensor Data
      </h2>

      <p className="text-lg md:text-xl max-w-20xl text-center mb-10">
        Use this page to initiate the UWB radar sensor for behind-wall vital sign detection and process physiological signals with waveform analysis.
      </p>

      {/* Configuration Section */}
      <div className="w-full max-w-xl bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 mt-4 shadow-lg">
        <label className="block text-lg font-semibold mb-4 text-center">
          Choose the position of the Person 
        </label>

        <div className="flex flex-col gap-4">
          <label
            className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer border 
              ${config === 0 ? "border-gray-400 bg-[#1d1d1d]" : "border-gray-700 bg-[#131313] hover:border-gray-500"}`}
          >
            <input
              type="radio"
              name="bw-configuration"
              value="0"
              checked={config === 0}
              onChange={() => setConfig(0)}
              className="w-4 h-4"
            />
            <span className="text-gray-200">Front</span>
          </label>

          <label
            className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer border 
              ${config === 1 ? "border-gray-400 bg-[#1d1d1d]" : "border-gray-700 bg-[#131313] hover:border-gray-500"}`}
          >
            <input
              type="radio"
              name="bw-configuration"
              value="1"
              checked={config === 1}
              onChange={() => setConfig(1)}
              className="w-4 h-4"
            />
            <span className="text-gray-200">Back</span>
          </label>
        </div>
      </div>

      {/* Run Sensor Button */}
      <button
        onClick={handleRunSensor}
        className="mt-4 px-6 py-3 border border-gray-600 text-gray-200 rounded-lg transition hover:bg-[#1a1a1a] hover:border-gray-400 hover:text-white"
      >
        Run the Sensor
      </button>

      {/* CLEAN SENTENCE OUTPUT */}
      {predictedHR !== null && predictedHR !== undefined && (
        <div className="w-full max-w-3xl mt-10 text-center">

          {/* Heart Rate sentence */}
          <p className="text-2xl text-gray-200 mb-6">
            Your estimated heart rate is{" "}
            <span className="text-white font-bold">{predictedHR} bpm</span>.
          </p>

          {/* HR Class sentence */}
          <p className="text-xl text-gray-300 mb-3">
            Your heart rate category is{" "}
            <span className={`font-bold ${getColorClass(hrClass)}`}>
              {hrClass}
            </span>.
          </p>

          {/* RR Class sentence */}
          <p className="text-xl text-gray-300 mb-3">
            Your breathing rate is classified as{" "}
            <span className={`font-bold ${getColorClass(rrClass)}`}>
              {rrClass}
            </span>.
          </p>
        </div>
      )}

{/* ================= WAVEFORM GRAPHS ================= */}
{waveform && (
  <div className="w-full max-w-5xl mt-10">
    <h3 className="text-2xl font-bold mb-2 text-center">Vital Signs Waveforms</h3>
    <p className="text-sm text-gray-400 mb-6 text-center">
      HR: {waveform.hr_text || "--"} BPM &nbsp;&nbsp;|&nbsp;&nbsp; RR: {waveform.rr_text || "--"} BPM
    </p>

    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Heart Motion */}
      {waveform.heart && waveform.heart.length > 0 && (
        <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-4 shadow-lg">
          <h4 className="text-md font-semibold text-red-400 mb-2 text-center">Heart Motion</h4>
          <div className="h-[200px]">
            <Line
              data={{
                labels: waveform.heart.map((_, i) => i),
                datasets: [{
                  data: waveform.heart,
                  borderColor: "#ef4444",
                  backgroundColor: "rgba(239,68,68,0.08)",
                  borderWidth: 1.5,
                  pointRadius: 0,
                  tension: 0.3,
                  fill: true,
                }],
              }}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                  x: { display: false },
                  y: { ticks: { color: "#9ca3af" }, grid: { color: "#1f2937" } },
                },
                animation: false,
              }}
            />
          </div>
        </div>
      )}

      {/* Respiration Motion */}
      {waveform.respiration && waveform.respiration.length > 0 && (
        <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-4 shadow-lg">
          <h4 className="text-md font-semibold text-cyan-400 mb-2 text-center">Respiration Motion</h4>
          <div className="h-[200px]">
            <Line
              data={{
                labels: waveform.respiration.map((_, i) => i),
                datasets: [{
                  data: waveform.respiration,
                  borderColor: "#22d3ee",
                  backgroundColor: "rgba(34,211,238,0.08)",
                  borderWidth: 1.5,
                  pointRadius: 0,
                  tension: 0.3,
                  fill: true,
                }],
              }}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                  x: { display: false },
                  y: { ticks: { color: "#9ca3af" }, grid: { color: "#1f2937" } },
                },
                animation: false,
              }}
            />
          </div>
        </div>
      )}

      {/* Chest Displacement */}
      {waveform.chest && waveform.chest.length > 0 && (
        <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-4 shadow-lg">
          <h4 className="text-md font-semibold text-green-400 mb-2 text-center">Chest Displacement</h4>
          <div className="h-[200px]">
            <Line
              data={{
                labels: waveform.chest.map((_, i) => i),
                datasets: [{
                  data: waveform.chest,
                  borderColor: "#4ade80",
                  backgroundColor: "rgba(74,222,128,0.08)",
                  borderWidth: 1.5,
                  pointRadius: 0,
                  tension: 0.3,
                  fill: true,
                }],
              }}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                  x: { display: false },
                  y: { ticks: { color: "#9ca3af" }, grid: { color: "#1f2937" } },
                },
                animation: false,
              }}
            />
          </div>
        </div>
      )}

      {/* Combined Signal */}
      {waveform.combined && waveform.combined.length > 0 && (
        <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-4 shadow-lg">
          <h4 className="text-md font-semibold text-purple-400 mb-2 text-center">Combined Chest Signal</h4>
          <div className="h-[200px]">
            <Line
              data={{
                labels: waveform.combined.map((_, i) => i),
                datasets: [{
                  data: waveform.combined,
                  borderColor: "#c084fc",
                  backgroundColor: "rgba(192,132,252,0.08)",
                  borderWidth: 1.5,
                  pointRadius: 0,
                  tension: 0.3,
                  fill: true,
                }],
              }}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                  x: { display: false },
                  y: { ticks: { color: "#9ca3af" }, grid: { color: "#1f2937" } },
                },
                animation: false,
              }}
            />
          </div>
        </div>
      )}
    </div>
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

      <div className="w-full max-w-3xl aspect-video rounded-xl overflow-hidden shadow-xl border border-gray-700">
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
      <div className="w-full max-w-7xl mt-8 mb-12 text-center text-gray-400">
        <small>Radarix, 2025</small>
      </div>
    </div>
  );
}

export default RunSensorBehindWall;
