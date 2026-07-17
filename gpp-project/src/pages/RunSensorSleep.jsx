// src/pages/RunSensorSleep.jsx — Sleep Detection + Pattern Dashboard (combined)
import React, { useState, useEffect, useMemo } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line, Bar, Pie, Doughnut } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const API_BASE =
  (import.meta && import.meta.env && import.meta.env.VITE_API_BASE) ||
  "http://localhost:5002";

// ── helpers ────────────────────────────────────────────────────────
function severityColor(sev) {
  if (!sev) return "text-gray-400";
  const s = sev.toLowerCase();
  if (s === "normal" || s === "none") return "text-green-400";
  if (s === "mild") return "text-yellow-400";
  if (s === "moderate") return "text-orange-400";
  if (s === "severe") return "text-red-400";
  return "text-gray-300";
}

function fmtDuration(seconds) {
  if (!seconds || seconds <= 0) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function fmtClock(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function downsampleTriplet(timestamps, rr, hr, maxPoints = 1800) {
  if (!Array.isArray(timestamps) || timestamps.length <= maxPoints) {
    return { timestamps, rr, hr };
  }
  const step = Math.ceil(timestamps.length / maxPoints);
  const ts = [];
  const rrOut = [];
  const hrOut = [];
  for (let i = 0; i < timestamps.length; i += step) {
    ts.push(timestamps[i]);
    rrOut.push(rr[i]);
    hrOut.push(hr[i]);
  }
  const last = timestamps.length - 1;
  if (ts[ts.length - 1] !== timestamps[last]) {
    ts.push(timestamps[last]);
    rrOut.push(rr[last]);
    hrOut.push(hr[last]);
  }
  return { timestamps: ts, rr: rrOut, hr: hrOut };
}

function pctBar(pct, color) {
  return (
    <div className="w-full bg-gray-800 rounded-full h-3 mt-1">
      <div
        className={`h-3 rounded-full ${color}`}
        style={{ width: `${Math.min(pct, 100)}%` }}
      />
    </div>
  );
}

function smoothSeries(values, windowSize = 11) {
  if (!Array.isArray(values) || values.length < 3 || windowSize <= 1) return values;
  const out = new Array(values.length);
  const half = Math.floor(windowSize / 2);
  for (let i = 0; i < values.length; i++) {
    let sum = 0;
    let n = 0;
    const lo = Math.max(0, i - half);
    const hi = Math.min(values.length - 1, i + half);
    for (let j = lo; j <= hi; j++) {
      const v = values[j];
      if (v != null && Number.isFinite(v)) {
        sum += v;
        n += 1;
      }
    }
    out[i] = n > 0 ? sum / n : values[i] ?? null;
  }
  return out;
}

function smoothStages(stageNames) {
  if (!Array.isArray(stageNames) || stageNames.length < 3) return stageNames;
  const out = [...stageNames];

  // Pass 1: remove single-epoch spikes
  for (let i = 1; i < out.length - 1; i++) {
    if (out[i - 1] === out[i + 1] && out[i] !== out[i - 1]) {
      out[i] = out[i - 1];
    }
  }

  // Pass 2: remove two-epoch spikes
  for (let i = 1; i < out.length - 2; i++) {
    if (out[i - 1] === out[i + 2] && out[i] !== out[i - 1] && out[i + 1] !== out[i - 1]) {
      out[i] = out[i - 1];
      out[i + 1] = out[i - 1];
    }
  }

  return out;
}

const STAGE_MAP = { Wake: 4, REM: 3, Light: 2, Deep: 1 };
const STAGE_LABELS = ["Deep", "Light", "REM", "Wake"];
const STAGE_COLORS = {
  Wake: "#ef4444",
  REM: "#a78bfa",
  Light: "#60a5fa",
  Deep: "#34d399",
};

// ── Reusable UI atoms ──────────────────────────────────────────────
function ErrorPopup({ message, onClose, title = "Message" }) {
  if (!message) return null;
  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm">
      <div className="bg-[#0f0f0f] border border-gray-700 rounded-2xl p-6 max-w-md w-[90%] text-gray-200 shadow-2xl shadow-black/70">
        <h2 className="text-2xl font-bold mb-4 text-red-400 text-center">{title}</h2>
        <p
          className="mb-6 leading-relaxed whitespace-pre-wrap text-gray-200"
          style={{ maxHeight: "300px", overflowY: "auto", textAlign: "left", wordBreak: "break-word" }}
        >
          {message}
        </p>
        <div className="flex justify-center">
          <button
            onClick={onClose}
            className="px-6 py-2 border border-gray-600 rounded-lg text-gray-200 transition outline-none ring-0 focus:ring-0 hover:bg-[#1a1a1a] hover:border-gray-400 hover:text-white"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function Card({ title, children, className = "" }) {
  return (
    <div className={`bg-[#0f0f0f] border border-gray-700 rounded-xl p-5 shadow-lg ${className}`}>
      {title && <h3 className="text-lg font-semibold text-gray-200 mb-3">{title}</h3>}
      {children}
    </div>
  );
}

function Stat({ label, value, sub, colorClass = "text-white" }) {
  return (
    <div className="text-center">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold ${colorClass}`}>{value ?? "—"}</p>
      {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
//  MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════
function RunSensorSleep() {
  useEffect(() => {
    document.title = "Radarix | Sleep Detection";
  }, []);

  // ── Sensor / popup state ─────────────────────────────────────────
  const [popupMessage, setPopupMessage] = useState("");
  const [popupTitle, setPopupTitle] = useState("");
  const [config, setConfig] = useState(null);
  const [collecting, setCollecting] = useState(false);   // Step 1: sensor
  const [analyzing, setAnalyzing] = useState(false);     // Step 2: pipeline
  const [sessionCsv, setSessionCsv] = useState(null);    // path returned by /collect
  const [waveformData, setWaveformData] = useState(null);
  const [statsText, setStatsText] = useState("");
  const [duration, setDuration] = useState(120);         // Collection duration in seconds
  const [collectAbort, setCollectAbort] = useState(null); // AbortController for stopping collection
  const [uploadFile, setUploadFile] = useState(null);    // File upload state
  const [uploadedSessionPath, setUploadedSessionPath] = useState(""); // Uploaded session path

  // ── Dashboard state ──────────────────────────────────────────────
  const [loading, setLoading] = useState(true);
  const [dashError, setDashError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState([]);
  const [vitals, setVitals] = useState(null);
  const [sleepStructure, setSleepStructure] = useState(null);
  const [stageEpochs, setStageEpochs] = useState([]);
  const [motionTimeline, setMotionTimeline] = useState([]);
  const [motionStats, setMotionStats] = useState(null);

  const stageDistribution = useMemo(() => {
    const base = { Wake: 0, Light: 0, Deep: 0, REM: 0 };
    const pcts = sleepStructure?.pct_per_stage || {};
    for (const stage of Object.keys(base)) {
      const v = Number(pcts[stage]);
      base[stage] = Number.isFinite(v) ? v : 0;
    }
    return base;
  }, [sleepStructure]);

  const userEmail = localStorage.getItem("loggedUser");

  // ── Fetch latest session on mount ────────────────────────────────
  useEffect(() => {
    fetchFullSession();
  }, []);

  // ── Auto-analyze when new session data is collected ───────────────
  useEffect(() => {
    if (sessionCsv && !analyzing) {
      setAnalyzing(true);
      fetch(`${API_BASE}/api/sleep/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionCsvPath: sessionCsv,
          userEmail: userEmail,
          disableUserFilter: true,
        }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.success) {
            setPopupTitle("Analysis Complete");
            setPopupMessage(
              "Sleep analysis complete. Your results are below."
            );
            // Refresh the dashboard with new results
            setTimeout(() => fetchFullSession(), 500);
          } else {
            setPopupTitle("Analysis Error");
            setPopupMessage(data.error || "Failed to analyze sleep data.");
          }
        })
        .catch(() => {
          setPopupTitle("Analysis Error");
          setPopupMessage("Could not connect to analyze endpoint.");
        })
        .finally(() => setAnalyzing(false));
    }
  }, [sessionCsv]);

  const fetchFullSession = (forcedSessionPath = "") => {
    setLoading(true);
    setDashError(null);
    const sessionPath = forcedSessionPath || uploadedSessionPath || sessionCsv || "";
    const cacheBuster = `_t=${Date.now()}`;
    const url = sessionPath
      ? `${API_BASE}/api/sleep/full-session?sessionCsvPath=${encodeURIComponent(sessionPath)}&${cacheBuster}`
      : `${API_BASE}/api/sleep/full-session?${cacheBuster}`;
    fetch(url, { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          setSummary(data.summary || {});
          setEvents(data.events || []);
          setVitals(data.vitals || null);
          setSleepStructure(data.sleep_structure || null);
          setStageEpochs(data.stage_epochs || []);
          setMotionTimeline(data.motion_timeline || []);
          setMotionStats(data.motion_stats || null);
        } else {
          setDashError(data.error || "No sleep data found. Run an analysis first.");
        }
      })
      .catch(() =>
        setDashError("Could not connect to the backend. Make sure the server is running on port 5002.")
      )
      .finally(() => setLoading(false));
  };

  // ── Step 1: Start sensor data collection ────────────────────────
  const handleStartCollection = () => {
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

    setCollecting(true);
    setSessionCsv(null);
    setWaveformData(null);
    setStatsText("");
    setPopupTitle("Collecting Data...");
    setPopupMessage(
      `Starting UWB radar sensor data collection (${duration} seconds)...\n\n` +
      "Live waveforms will appear as data comes in.\n" +
      "Please remain still near the sensor."
    );

    // Create AbortController for stop functionality
    const controller = new AbortController();
    setCollectAbort(controller);

    fetch(`${API_BASE}/api/sleep/collect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ userEmail, configuration: config, duration: duration }),
      signal: controller.signal,
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          setSessionCsv(data.session_csv || null);
          setWaveformData(data.waveform || null);
          setStatsText(data.stats_text || "");
          setPopupTitle("Sensor Data Collected");
          setPopupMessage(
            (data.stats_text ? data.stats_text + "\n\n" : "") +
            "Data collection complete. Analysis is running..."
          );
        } else {
          setPopupTitle("Sensor Error!");
          setPopupMessage(data.error || "Unknown error occurred during data collection.");
        }
      })
      .catch((err) => {
        if (err.name === "AbortError") {
          setPopupTitle("Recording Stopped");
          setPopupMessage("Data collection was stopped by user.");
        } else {
          setPopupTitle("Connection Error");
          setPopupMessage("Could not connect to the backend server.\nMake sure it is running on port 5002.");
        }
      })
      .finally(() => {
        setCollecting(false);
        setCollectAbort(null);
      });
  };

  // ── Stop sensor data collection ──────────────────────────────────
  const handleStopCollection = () => {
    if (collectAbort) {
      collectAbort.abort();
      setCollectAbort(null);
      setCollecting(false);
    }
  };

  // ── Upload CSV/XLSX and auto-analyze ──────────────────────────────
  const handleUploadSession = () => {
    if (!uploadFile) {
      setPopupTitle("Upload Required");
      setPopupMessage("Please choose a CSV or Excel file first.");
      return;
    }

    const fd = new FormData();
    fd.append("file", uploadFile);

    setPopupTitle("Uploading...");
    setPopupMessage("Uploading session file for sleep analysis...");
    setAnalyzing(true);

    fetch(`${API_BASE}/api/sleep/upload-session`, {
      method: "POST",
      body: fd,
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success && data.session_csv_path) {
          setUploadedSessionPath(data.session_csv_path);
          setPopupTitle("Upload Complete — Starting Analysis");
          setPopupMessage(
            "File uploaded successfully. Launching analysis pipeline...\n\n" +
            "1. Sleep event detection\n" +
            "2. Motion & posture analysis\n" +
            "3. Sleep stage classification\n\n" +
            "This may take a few minutes."
          );
          
          // Auto-trigger analysis after successful upload
          const userEmail = localStorage.getItem("loggedUser") || "";
          setTimeout(() => {
            fetch(`${API_BASE}/api/sleep/analyze`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                userEmail,
                sessionCsvPath: data.session_csv_path,
                disableUserFilter: true,
              }),
            })
              .then((res) => res.json())
              .then((analysisData) => {
                if (analysisData.success) {
                  setPopupTitle("Analysis Complete");
                  setPopupMessage(
                    "Sleep analysis finished successfully!\n\n" +
                    "Insights are displayed below."
                  );
                  setTimeout(() => {
                    setPopupMessage("");
                    fetchFullSession(data.session_csv_path);
                  }, 2000);
                } else {
                  setPopupTitle("Analysis Error");
                  setPopupMessage(
                    analysisData.error || "Analysis failed. Please try again."
                  );
                }
              })
              .catch(() => {
                setPopupTitle("Connection Error");
                setPopupMessage(
                  "Could not connect to backend. Make sure it is running."
                );
              })
              .finally(() => setAnalyzing(false));
          }, 500);
        } else {
          setPopupTitle("Upload Error");
          setPopupMessage(data.error || "File upload failed.");
          setAnalyzing(false);
        }
      })
      .catch(() => {
        setPopupTitle("Connection Error");
        setPopupMessage("Could not upload file. Check backend connection.");
        setAnalyzing(false);
      });
  };

  // ── Chart data (memoised) ────────────────────────────────────────
  const vitalsChartData = useMemo(() => {
    if (!vitals || !vitals.timestamps || vitals.timestamps.length < 2) return null;

    const raw = vitals.timestamps;
    const rrRaw = smoothSeries((vitals.rr_bpm || []).map((v) => (v != null && Number.isFinite(v) ? Number(v) : null)));
    const hrRaw = smoothSeries((vitals.hr_bpm || []).map((v) => (v != null && Number.isFinite(v) ? Number(v) : null)));

    const sampled = downsampleTriplet(raw, rrRaw, hrRaw, 1800);
    const labels = sampled.timestamps.map((t, i) => (typeof t === "number" ? fmtClock(t) : `E${i + 1}`));
    const rrData = sampled.rr.map((v) => v ?? null);
    const hrData = sampled.hr.map((v) => v ?? null);

    const hasRR = rrData.some((v) => v !== null);
    const hasHR = hrData.some((v) => v !== null);
    if (!hasRR && !hasHR) return null;

    const datasets = [];
    if (hasRR) datasets.push({
      label: "Respiration Rate (bpm)",
      data: rrData,
      borderColor: "#60a5fa",
      backgroundColor: "rgba(96,165,250,0.08)",
      fill: true, tension: 0.2, pointRadius: 0, borderWidth: 2, yAxisID: "y",
    });
    if (hasHR) datasets.push({
      label: "Heart Rate (bpm)",
      data: hrData,
      borderColor: "#f87171",
      backgroundColor: "rgba(248,113,113,0.08)",
      fill: true, tension: 0.2, pointRadius: 0, borderWidth: 2, yAxisID: hasRR ? "y1" : "y",
    });
    return { labels, datasets };
  }, [vitals]);

  const vitalsChartOptions = {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { labels: { color: "#d1d5db" } }, title: { display: false } },
    scales: {
      x: { ticks: { color: "#6b7280", maxTicksLimit: 8 }, grid: { color: "rgba(107,114,128,0.15)" } },
      y: { type: "linear", position: "left", title: { display: true, text: "RR (bpm)", color: "#60a5fa" }, ticks: { color: "#60a5fa" }, grid: { color: "rgba(107,114,128,0.15)" } },
      y1: { type: "linear", position: "right", title: { display: true, text: "HR (bpm)", color: "#f87171" }, ticks: { color: "#f87171" }, grid: { drawOnChartArea: false } },
    },
  };

  // ── Live vitals chart from waveformData (during recording) ────────
  const liveVitalsChartData = useMemo(() => {
    if (!waveformData?.timestamps || (waveformData.timestamps.length < 2)) return null;

    const timestamps = waveformData.timestamps || [];
    const hrVals = waveformData.hr_vals || [];
    const rrVals = waveformData.rr_vals || [];

    if (hrVals.length === 0 && rrVals.length === 0) return null;

    // Downsample to at most 100 points for live chart efficiency
    const step = Math.max(1, Math.floor(timestamps.length / 100));
    const idx = Array.from({ length: Math.ceil(timestamps.length / step) }, (_, k) => k * step);

    const labels = idx.map((i) => `${Math.round(timestamps[i])}s`);
    const rrData = idx.map((i) => (rrVals[i] ?? null));
    const hrData = idx.map((i) => (hrVals[i] ?? null));

    const hasRR = rrData.some((v) => v !== null);
    const hasHR = hrData.some((v) => v !== null);
    if (!hasRR && !hasHR) return null;

    const datasets = [];
    if (hasRR) datasets.push({
      label: "Respiration Rate (bpm)",
      data: rrData,
      borderColor: "#60a5fa",
      backgroundColor: "rgba(96,165,250,0.08)",
      fill: true, tension: 0.25, pointRadius: 0, borderWidth: 2, yAxisID: "y",
    });
    if (hasHR) datasets.push({
      label: "Heart Rate (bpm)",
      data: hrData,
      borderColor: "#f87171",
      backgroundColor: "rgba(248,113,113,0.08)",
      fill: true, tension: 0.25, pointRadius: 0, borderWidth: 2, yAxisID: hasRR ? "y1" : "y",
    });
    return { labels, datasets };
  }, [waveformData]);

  const hypnogramData = useMemo(() => {
    if (!stageEpochs || stageEpochs.length === 0) return null;
    const labels = stageEpochs.map((e, i) => {
      const t = Number(e?.timestamp_start);
      if (Number.isFinite(t)) return fmtClock(t);
      return e.time_label || `E${i + 1}`;
    });
    const rawStageNames = stageEpochs.map((e) => e.stage || e.predicted_stage || "Light");
    const smoothedStageNames = smoothStages(rawStageNames);
    const values = smoothedStageNames.map((s) => STAGE_MAP[s] ?? 0);
    return {
      labels,
      datasets: [{
        label: "Sleep Stage",
        data: values,
        borderColor: "#60a5fa",
        backgroundColor: "rgba(96,165,250,0.08)",
        stepped: true,
        fill: true,
        pointRadius: 0,
        borderWidth: 2,
        tension: 0,
      }],
    };
  }, [stageEpochs]);

  const hypnogramOptions = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => STAGE_LABELS[(ctx.raw || 1) - 1] || "—" } } },
    scales: {
      x: { ticks: { color: "#6b7280", maxTicksLimit: 15 }, grid: { color: "rgba(107,114,128,0.15)" } },
      y: { min: 0.5, max: 4.5, ticks: { stepSize: 1, color: "#d1d5db", callback: (v) => STAGE_LABELS[v - 1] || "" }, grid: { color: "rgba(107,114,128,0.15)" } },
    },
  };

  const eventPieData = useMemo(() => {
    const counts = summary?.event_counts || {};
    if (Object.keys(counts).length === 0) return null;
    const labels = Object.keys(counts);
    const data = Object.values(counts);
    const palette = ["#34d399", "#f87171", "#fbbf24", "#a78bfa", "#60a5fa", "#fb923c"];
    return { labels, datasets: [{ data, backgroundColor: palette.slice(0, labels.length), borderWidth: 0 }] };
  }, [summary]);

  const stageDonutData = useMemo(() => {
    const labels = Object.keys(stageDistribution);
    const data = labels.map((k) => stageDistribution[k] || 0);
    const colors = labels.map((l) => STAGE_COLORS[l] || "#6b7280");
    return { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] };
  }, [stageDistribution]);

  const vitalsDurationSec = useMemo(() => {
    if (!vitals?.timestamps || vitals.timestamps.length < 2) return 0;
    const start = Number(vitals.timestamps[0]);
    const end = Number(vitals.timestamps[vitals.timestamps.length - 1]);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return 0;
    return end - start;
  }, [vitals]);

  const postureDonutData = useMemo(() => {
    const dist = motionStats?.posture_distribution_pct || {};
    if (Object.keys(dist).length === 0) return null;
    const labels = Object.keys(dist);
    const data = Object.values(dist);
    const palette = ["#60a5fa", "#34d399", "#fbbf24", "#a78bfa", "#f87171", "#fb923c"];
    return { labels, datasets: [{ data, backgroundColor: palette.slice(0, labels.length), borderWidth: 0 }] };
  }, [motionStats]);

  const pieOpts = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: "bottom", labels: { color: "#d1d5db", padding: 12 } } },
  };

  const hasDashboard = !loading && !dashError;

  // ═════════════════════════════════════════════════════════════════
  //  RENDER
  // ═════════════════════════════════════════════════════════════════
  return (
    <div className="flex flex-col items-center justify-start w-screen min-h-screen bg-black px-4 md:px-10 lg:px-16 pt-20 pb-16 text-gray-200">

      {/* ── Header ──────────────────────────────────────────────── */}
      <h1 className="text-5xl md:text-6xl font-extrabold mb-4">Sleep Detection</h1>
      <h2 className="text-2xl md:text-3xl font-semibold mb-6 text-center">
        Start and View Real-Time Sleep Monitoring Data
      </h2>
      <p className="text-lg md:text-xl max-w-3xl text-center mb-10">
        The sensor will collect live radar data (~30 seconds) and then automatically analyze it for sleep patterns, breathing events, and motion.
      </p>

      {/* ── Configuration Section ───────────────────────────────── */}
      <div className="w-full max-w-xl bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 mt-4 shadow-lg">
        <label className="block text-lg font-semibold mb-4 text-center">
          Choose the position of the Person
        </label>
        <div className="flex flex-col gap-4 mb-6">
          <label className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer border ${config === 0 ? "border-gray-400 bg-[#1d1d1d]" : "border-gray-700 bg-[#131313] hover:border-gray-500"}`}>
            <input type="radio" name="sleep-configuration" value="0" checked={config === 0} onChange={() => setConfig(0)} className="w-4 h-4" />
            <span className="text-gray-200">Front</span>
          </label>
          <label className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer border ${config === 1 ? "border-gray-400 bg-[#1d1d1d]" : "border-gray-700 bg-[#131313] hover:border-gray-500"}`}>
            <input type="radio" name="sleep-configuration" value="1" checked={config === 1} onChange={() => setConfig(1)} className="w-4 h-4" />
            <span className="text-gray-200">Back</span>
          </label>
        </div>

        {/* Duration Control */}
        <label className="block text-lg font-semibold mb-2 text-center">Recording Duration (2 min to 8 hrs)</label>
        <div className="flex items-center gap-4 mb-4">
          <input
            type="range"
            min="120"
            max="28800"
            step="60"
            value={duration}
            onChange={(e) => setDuration(parseInt(e.target.value))}
            disabled={collecting}
            className="flex-1 h-2 bg-gray-700 rounded-lg cursor-pointer disabled:opacity-50"
          />
          <input
            type="number"
            min="120"
            max="28800"
            step="60"
            value={duration}
            onChange={(e) => setDuration(Math.max(120, Math.min(28800, parseInt(e.target.value) || 120)))}
            disabled={collecting}
            className="w-20 px-2 py-1 bg-[#1a1a1a] border border-gray-600 rounded text-gray-200 text-center disabled:opacity-50"
          />
          <span className="text-sm text-gray-400 w-12">sec</span>
        </div>
      </div>

      {/* ── Upload CSV/XLSX Section ─────────────────────────────── */}
      <div className="w-full max-w-xl bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 mt-4 shadow-lg">
        <label className="block text-lg font-semibold mb-4 text-center">
          Or Upload Existing Sleep Session
        </label>
        <div className="flex flex-col gap-3">
          <input
            type="file"
            accept=".csv,.xlsx,.xls"
            onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
            className="w-full text-sm text-gray-300 file:mr-4 file:py-2 file:px-4 file:border file:border-gray-600 file:rounded-lg file:bg-transparent file:text-gray-200 hover:file:border-gray-400"
          />
          <button
            onClick={handleUploadSession}
            disabled={analyzing || !uploadFile}
            className="px-6 py-3 border border-blue-600 text-blue-400 rounded-lg transition hover:bg-blue-600/10 hover:border-blue-400 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {analyzing ? "Uploading & Analyzing..." : "Upload & Analyze Sleep File"}
          </button>
        </div>
        {uploadedSessionPath && (
          <p className="text-sm text-green-400 mt-3 text-center break-all">
            ✓ Loaded: {uploadedSessionPath.split('\\').pop()}
          </p>
        )}
      </div>

      {/* ── Action buttons ──────────────────────────────────────── */}
      <div className="flex flex-wrap gap-4 mt-6 justify-center">
        {/* Start/Stop buttons */}
        {!collecting ? (
          <button
            onClick={handleStartCollection}
            disabled={analyzing}
            className="px-6 py-3 border border-green-600 text-green-400 rounded-lg transition hover:bg-green-600/10 hover:border-green-400 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Start Recording
          </button>
        ) : (
          <button
            onClick={handleStopCollection}
            className="px-6 py-3 border border-red-600 text-red-400 rounded-lg transition hover:bg-red-600/10 hover:border-red-400"
          >
            Stop Recording
          </button>
        )}
        <button
          onClick={fetchFullSession}
          disabled={loading || collecting || analyzing}
          className="px-6 py-3 border border-gray-600 text-gray-200 rounded-lg transition hover:bg-[#1a1a1a] hover:border-gray-400 hover:text-white disabled:opacity-50"
        >
          Refresh Data
        </button>
      </div>

      {/* ═══════════════════════════════════════════════════════════════ */}
      {/* COLLECTION STATUS */}
      {/* ═══════════════════════════════════════════════════════════════ */}
      {(collecting || statsText) && (
        <div className="w-full max-w-5xl mt-10 mb-10">
          {collecting && (
            <div className="bg-[#0f0f0f] border border-green-700 rounded-xl p-6 shadow-lg text-center">
              <p className="text-lg text-green-400 animate-pulse font-semibold">🔴 Recording in progress...</p>
              <p className="text-sm text-gray-400 mt-2">Collecting sensor data. Please remain still.</p>
            </div>
          )}
          {statsText && !collecting && (
            <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
              <h3 className="text-lg font-semibold text-gray-200 mb-3 text-center">Collection Complete</h3>
              <p className="text-sm text-gray-400 whitespace-pre-wrap text-center">{statsText}</p>
            </div>
          )}
        </div>
      )}

      {/* ── Divider ─────────────────────────────────────────────── */}
      <div className="w-full max-w-7xl border-t border-gray-800 my-12" />

      {/* ── Dashboard Section ───────────────────────────────────── */}
      <h2 className="text-3xl md:text-4xl font-bold mb-2">Sleep Pattern Analysis</h2>
      <p className="text-lg text-gray-400 max-w-2xl text-center mb-8">
        Breathing events, heart rate, sleep stages, motion and posture.
      </p>

      {/* Loading */}
      {loading && (
        <p className="text-gray-500 text-lg animate-pulse">Loading sleep data...</p>
      )}

      {/* Error */}
      {!loading && dashError && (
        <Card className="max-w-xl w-full text-center">
          <p className="text-gray-400 mb-4">{dashError}</p>
          <p className="text-sm text-gray-600">
            Run the analysis first or make sure the backend server is online.
          </p>
        </Card>
      )}

      {/* ── Dashboard content ──────────────────────────────────── */}
      {hasDashboard && (
        <div className="w-full max-w-7xl space-y-8">

          {/* Row 1: Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card><Stat label="Severity" value={summary?.severity || "—"} colorClass={severityColor(summary?.severity)} /></Card>
            <Card><Stat label="Duration" value={fmtDuration(summary?.total_duration_sec)} sub={`${summary?.total_epochs || 0} epochs`} /></Card>
            <Card>
              <Stat
                label="Sleep Efficiency"
                value={sleepStructure?.sleep_efficiency_pct != null ? `${sleepStructure.sleep_efficiency_pct.toFixed(1)}%` : "—"}
                sub={sleepStructure?.efficiency_rating || ""}
                colorClass={sleepStructure?.sleep_efficiency_pct >= 85 ? "text-green-400" : sleepStructure?.sleep_efficiency_pct >= 70 ? "text-yellow-400" : "text-red-400"}
              />
            </Card>
            <Card>
              <Stat
                label="Apnea / Hour"
                value={summary?.apnea_events_per_hour != null ? summary.apnea_events_per_hour.toFixed(1) : "—"}
                sub="AHI"
                colorClass={(summary?.apnea_events_per_hour || 0) < 5 ? "text-green-400" : (summary?.apnea_events_per_hour || 0) < 15 ? "text-yellow-400" : "text-red-400"}
              />
            </Card>
          </div>

          {/* Row 2: Sleep structure bar */}
          {sleepStructure && sleepStructure.pct_per_stage && (
            <Card title="Sleep Stage Distribution">
              <div className="space-y-3">
                {Object.entries(stageDistribution).map(([stage, pct]) => (
                  <div key={stage}>
                    <div className="flex justify-between text-sm text-gray-300 mb-1">
                      <span className="flex items-center gap-2">
                        <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: STAGE_COLORS[stage] || "#6b7280" }} />
                        {stage}
                      </span>
                      <span>{pct?.toFixed(1) ?? 0}%</span>
                    </div>
                    {pctBar(pct, stage === "Deep" ? "bg-emerald-400" : stage === "Light" ? "bg-blue-400" : stage === "REM" ? "bg-violet-400" : "bg-red-400")}
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-6 mt-4 text-sm text-gray-400">
                <span>Onset latency: <span className="text-gray-200">{fmtDuration(sleepStructure.sleep_onset_latency_sec)}</span></span>
                <span>REM episodes: <span className="text-gray-200">{sleepStructure.rem_episodes ?? "—"}</span></span>
                <span>Total: <span className="text-gray-200">{sleepStructure.total_duration_min ? `${sleepStructure.total_duration_min.toFixed(0)} min` : "—"}</span></span>
              </div>
            </Card>
          )}

          {/* Row 3: Vitals */}
          {vitalsChartData && (
            <Card title="Vital Signs Over Time">
              <div className="h-72 md:h-80">
                <Line data={vitalsChartData} options={vitalsChartOptions} />
              </div>
              <p className="text-xs text-gray-400 mt-2">
                Full session timeline: 00:00 to {fmtClock(vitalsDurationSec)} ({fmtDuration(vitalsDurationSec || summary?.total_duration_sec || 0)})
              </p>
            </Card>
          )}

          {/* Row 4: Hypnogram */}
          {hypnogramData && (
            <Card title="Sleep Hypnogram">
              <div className="flex gap-4 mb-3">
                {Object.entries(STAGE_COLORS).map(([s, c]) => (
                  <span key={s} className="flex items-center gap-1 text-xs text-gray-400">
                    <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: c }} />
                    {s}
                  </span>
                ))}
              </div>
              <div className="h-48 md:h-56">
                <Line data={hypnogramData} options={hypnogramOptions} />
              </div>
              <p className="text-xs text-gray-400 mt-2">
                Full hypnogram timeline shown for {fmtDuration(summary?.total_duration_sec || vitalsDurationSec || 0)}
              </p>
            </Card>
          )}

          {/* Row 5: Pie / Doughnut charts */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {eventPieData && (
              <Card title="Sleep Event Types"><div className="h-56"><Pie data={eventPieData} options={pieOpts} /></div></Card>
            )}
            {stageDonutData && (
              <Card title="Stage Breakdown"><div className="h-56"><Doughnut data={stageDonutData} options={pieOpts} /></div></Card>
            )}
            {postureDonutData && (
              <Card title="Body State Distribution"><div className="h-56"><Doughnut data={postureDonutData} options={pieOpts} /></div></Card>
            )}
          </div>

          {/* Row 6: Event count details */}
          {summary?.event_counts && Object.keys(summary.event_counts).length > 0 && (
            <Card title="Breathing Event Breakdown">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Object.entries(summary.event_counts).map(([name, count]) => (
                  <div key={name} className="bg-[#131313] border border-gray-800 rounded-lg p-3 text-center">
                    <p className="text-xs text-gray-500 uppercase">{name.replace(/_/g, " ")}</p>
                    <p className="text-xl font-bold text-gray-200">{count}</p>
                    {summary.event_time_sec?.[name] != null && (
                      <p className="text-xs text-gray-600">{fmtDuration(summary.event_time_sec[name])}</p>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Row 7: Motion timeline */}
          {motionTimeline.length > 0 && (
            <Card title="Motion &amp; Body State Timeline">
              <div className="overflow-x-auto max-h-72 overflow-y-auto">
                <table className="w-full text-sm text-left text-gray-300">
                  <thead className="text-xs uppercase text-gray-500 border-b border-gray-700 sticky top-0 bg-[#0f0f0f]">
                    <tr>
                      <th className="py-2 px-3">Epoch</th>
                      <th className="py-2 px-3">Time Range</th>
                      <th className="py-2 px-3">Body State</th>
                      <th className="py-2 px-3">Motion Type</th>
                      <th className="py-2 px-3">Sleep Event</th>
                    </tr>
                  </thead>
                  <tbody>
                    {motionTimeline.map((row, i) => (
                      <tr key={i} className="border-b border-gray-800 hover:bg-[#1a1a1a]">
                        <td className="py-1.5 px-3">{row.epoch_index ?? i + 1}</td>
                        <td className="py-1.5 px-3">
                          {row.timestamp_start != null ? `${row.timestamp_start.toFixed(1)}s – ${row.timestamp_end?.toFixed(1)}s` : "—"}
                        </td>
                        <td className="py-1.5 px-3">{row.posture_label || "—"}</td>
                        <td className="py-1.5 px-3">{row.motion_type || "—"}</td>
                        <td className="py-1.5 px-3">{row.associated_sleep_event || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {motionStats?.motion_epoch_counts && (
                <div className="flex flex-wrap gap-4 mt-3 text-sm text-gray-400">
                  {Object.entries(motionStats.motion_epoch_counts).map(([k, v]) => (
                    <span key={k}>{k.replace(/_/g, " ")}: <span className="text-gray-200 font-semibold">{v}</span></span>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* Row 8: Sleep events table */}
          {events.length > 0 && (
            <Card title="Sleep Events Detail">
              <div className="overflow-x-auto max-h-72 overflow-y-auto">
                <table className="w-full text-sm text-left text-gray-300">
                  <thead className="text-xs uppercase text-gray-500 border-b border-gray-700 sticky top-0 bg-[#0f0f0f]">
                    <tr>
                      <th className="py-2 px-3">Epoch</th>
                      <th className="py-2 px-3">Event</th>
                      <th className="py-2 px-3">RR (bpm)</th>
                      <th className="py-2 px-3">HR (bpm)</th>
                      <th className="py-2 px-3">Duration (s)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((e, i) => (
                      <tr key={i} className="border-b border-gray-800 hover:bg-[#1a1a1a]">
                        <td className="py-1.5 px-3">{e.epoch_index ?? i}</td>
                        <td className="py-1.5 px-3">
                          <span className={(e.event_type || "").toLowerCase() === "normal" ? "text-green-400" : "text-yellow-400"}>
                            {e.event_type || "—"}
                          </span>
                        </td>
                        <td className="py-1.5 px-3">{e.RR_mean?.toFixed(1) ?? "—"}</td>
                        <td className="py-1.5 px-3">{e.HR_mean?.toFixed(1) ?? "—"}</td>
                        <td className="py-1.5 px-3">
                          {e.timestamp_start != null && e.timestamp_end != null
                            ? (e.timestamp_end - e.timestamp_start).toFixed(1)
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* ── Video Tutorial ──────────────────────────────────────── */}
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

      {/* Popup */}
      <ErrorPopup message={popupMessage} title={popupTitle} onClose={() => setPopupMessage("")} />

      {/* Footer */}
      <div className="w-full max-w-7xl mt-12 mb-8 text-center text-gray-400">
        <small>Radarix, 2025</small>
      </div>
    </div>
  );
}

export default RunSensorSleep;
