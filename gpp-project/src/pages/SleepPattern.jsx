// src/pages/SleepPattern.jsx
import React, { useEffect, useState, useMemo } from "react";
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
  if (!seconds || seconds <= 0) return "0 min";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m} min`;
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
  for (let i = 1; i < out.length - 1; i++) {
    if (out[i - 1] === out[i + 1] && out[i] !== out[i - 1]) {
      out[i] = out[i - 1];
    }
  }
  for (let i = 1; i < out.length - 2; i++) {
    if (out[i - 1] === out[i + 2] && out[i] !== out[i - 1] && out[i + 1] !== out[i - 1]) {
      out[i] = out[i - 1];
      out[i + 1] = out[i - 1];
    }
  }
  return out;
}

// Stage numeric mapping for hypnogram
const STAGE_MAP = { Wake: 4, REM: 3, Light: 2, Deep: 1 };
const STAGE_LABELS = ["Deep", "Light", "REM", "Wake"];
const STAGE_COLORS = {
  Wake: "#ef4444",
  REM: "#a78bfa",
  Light: "#60a5fa",
  Deep: "#34d399",
};

// ── ErrorPopup (shared) ────────────────────────────────────────────
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
            wordBreak: "break-word",
          }}
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

// ── Card component ─────────────────────────────────────────────────
function Card({ title, children, className = "" }) {
  return (
    <div
      className={`bg-[#0f0f0f] border border-gray-700 rounded-xl p-5 shadow-lg ${className}`}
    >
      {title && (
        <h3 className="text-lg font-semibold text-gray-200 mb-3">{title}</h3>
      )}
      {children}
    </div>
  );
}

// ── Stat badge ─────────────────────────────────────────────────────
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
//  SLEEP PATTERN PAGE
// ═══════════════════════════════════════════════════════════════════
function SleepPattern() {
  useEffect(() => {
    document.title = "Radarix | Sleep Pattern Analysis";
  }, []);

  // ── state ────────────────────────────────────────────────────────
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);

  const [popupMessage, setPopupMessage] = useState("");
  const [popupTitle, setPopupTitle] = useState("");
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadedSessionPath, setUploadedSessionPath] = useState("");

  // Full session data
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

  // ── fetch latest session on mount ────────────────────────────────
  useEffect(() => {
    fetchFullSession();
  }, []);

  const fetchFullSession = (forcedSessionPath = "") => {
    setLoading(true);
    setError(null);
    const resolvedSessionPath = forcedSessionPath || uploadedSessionPath;
    const cacheBuster = `_t=${Date.now()}`;
    const url = resolvedSessionPath
      ? `${API_BASE}/api/sleep/full-session?sessionCsvPath=${encodeURIComponent(resolvedSessionPath)}&${cacheBuster}`
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
          setError(
            data.error || "No sleep data found. Run an analysis first."
          );
        }
      })
      .catch(() =>
        setError(
          "Could not connect to the backend. Make sure the server is running on port 5002."
        )
      )
      .finally(() => setLoading(false));
  };

  // ── Run full analysis ─────────────────────────────────────────────
  const handleRunAnalysis = () => {
    const userEmail = localStorage.getItem("loggedUser") || "";
    setAnalyzing(true);
    setPopupTitle("Analyzing...");
    setPopupMessage(
      "Running full sleep analysis pipeline...\n\n" +
        "1. Sleep event detection\n" +
        "2. Motion & posture analysis\n" +
        "3. Sleep stage classification\n\n" +
        "This may take up to a few minutes."
    );

    fetch(`${API_BASE}/api/sleep/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        userEmail,
        sessionCsvPath: uploadedSessionPath || undefined,
        disableUserFilter: true,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          setPopupTitle("Analysis Complete");
          setPopupMessage(
            "Sleep analysis pipeline finished successfully.\n\nRefreshing dashboard..."
          );
          // Refresh dashboard data after a short pause
          setTimeout(() => {
            setPopupMessage("");
            fetchFullSession(uploadedSessionPath);
          }, 1500);
        } else {
          setPopupTitle("Analysis Error");
          setPopupMessage(data.error || "Analysis failed. Please try again.");
        }
      })
      .catch(() => {
        setPopupTitle("Connection Error");
        setPopupMessage(
          "Could not connect to the backend. Make sure it is running."
        );
      })
      .finally(() => setAnalyzing(false));
  };

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

  // ── chart data ───────────────────────────────────────────────────
  const vitalsChartData = useMemo(() => {
    if (!vitals || !vitals.timestamps || vitals.timestamps.length === 0)
      return null;

    const rrRaw = smoothSeries((vitals.rr_bpm || []).map((v) =>
      v != null && Number.isFinite(v) ? Number(v) : null
    ));
    const hrRaw = smoothSeries((vitals.hr_bpm || []).map((v) =>
      v != null && Number.isFinite(v) ? Number(v) : null
    ));

    const sampled = downsampleTriplet(vitals.timestamps, rrRaw, hrRaw, 1800);

    const labels = sampled.timestamps.map((t, i) =>
      typeof t === "number" ? fmtClock(t) : `E${i + 1}`
    );
    const rrData = sampled.rr.map((v) => v ?? null);
    const hrData = sampled.hr.map((v) => v ?? null);

    const hasRR = rrData.some((v) => v !== null);
    const hasHR = hrData.some((v) => v !== null);
    if (!hasRR && !hasHR) return null;

    const datasets = [];
    if (hasRR) {
      datasets.push({
        label: "Respiration Rate (bpm)",
        data: rrData,
        borderColor: "#60a5fa",
        backgroundColor: "rgba(96,165,250,0.1)",
        fill: true,
        tension: 0.2,
        pointRadius: 0,
        borderWidth: 2,
        yAxisID: "y",
      });
    }
    if (hasHR) {
      datasets.push({
        label: "Heart Rate (bpm)",
        data: hrData,
        borderColor: "#f87171",
        backgroundColor: "rgba(248,113,113,0.1)",
        fill: true,
        tension: 0.2,
        pointRadius: 0,
        borderWidth: 2,
        yAxisID: hasRR ? "y1" : "y",
      });
    }

    return {
      labels,
      datasets,
    };
  }, [vitals]);

  const vitalsChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: "#d1d5db" } },
      title: { display: false },
    },
    scales: {
      x: {
        ticks: { color: "#6b7280", maxTicksLimit: 8 },
        grid: { color: "rgba(107,114,128,0.15)" },
      },
      y: {
        type: "linear",
        position: "left",
        title: { display: true, text: "RR (bpm)", color: "#60a5fa" },
        ticks: { color: "#60a5fa" },
        grid: { color: "rgba(107,114,128,0.15)" },
      },
      y1: {
        type: "linear",
        position: "right",
        title: { display: true, text: "HR (bpm)", color: "#f87171" },
        ticks: { color: "#f87171" },
        grid: { drawOnChartArea: false },
      },
    },
  };

  // Hypnogram chart
  const hypnogramData = useMemo(() => {
    if (!stageEpochs || stageEpochs.length === 0) return null;
    const labels = stageEpochs.map((e, i) => {
      const t = Number(e?.timestamp_start);
      if (Number.isFinite(t)) return fmtClock(t);
      return e.time_label || `E${i + 1}`;
    });
    const rawStageNames = stageEpochs.map(
      (e) => e.stage || e.predicted_stage || "Light"
    );
    const smoothedStageNames = smoothStages(rawStageNames);
    const values = smoothedStageNames.map((s) => STAGE_MAP[s] ?? 0);
    return {
      labels,
      datasets: [
        {
          label: "Sleep Stage",
          data: values,
          borderColor: "#60a5fa",
          backgroundColor: "rgba(96,165,250,0.08)",
          stepped: true,
          fill: true,
          pointRadius: 0,
          borderWidth: 2,
          tension: 0,
        },
      ],
    };
  }, [stageEpochs]);

  const hypnogramOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => STAGE_LABELS[(ctx.raw || 1) - 1] || "—",
        },
      },
    },
    scales: {
      x: {
        ticks: { color: "#6b7280", maxTicksLimit: 15 },
        grid: { color: "rgba(107,114,128,0.15)" },
      },
      y: {
        min: 0.5,
        max: 4.5,
        ticks: {
          stepSize: 1,
          color: "#d1d5db",
          callback: (v) => STAGE_LABELS[v - 1] || "",
        },
        grid: { color: "rgba(107,114,128,0.15)" },
      },
    },
  };

  // Event distribution pie
  const eventPieData = useMemo(() => {
    const counts = summary?.event_counts || {};
    if (Object.keys(counts).length === 0) return null;
    const labels = Object.keys(counts);
    const data = Object.values(counts);
    const palette = [
      "#34d399",
      "#f87171",
      "#fbbf24",
      "#a78bfa",
      "#60a5fa",
      "#fb923c",
    ];
    return {
      labels,
      datasets: [
        {
          data,
          backgroundColor: palette.slice(0, labels.length),
          borderWidth: 0,
        },
      ],
    };
  }, [summary]);

  // Stage distribution doughnut
  const stageDonutData = useMemo(() => {
    const labels = Object.keys(stageDistribution);
    const data = labels.map((k) => stageDistribution[k] || 0);
    const colors = labels.map((l) => STAGE_COLORS[l] || "#6b7280");
    return {
      labels,
      datasets: [
        {
          data,
          backgroundColor: colors,
          borderWidth: 0,
        },
      ],
    };
  }, [stageDistribution]);

  const vitalsDurationSec = useMemo(() => {
    if (!vitals?.timestamps || vitals.timestamps.length < 2) return 0;
    const start = Number(vitals.timestamps[0]);
    const end = Number(vitals.timestamps[vitals.timestamps.length - 1]);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start)
      return 0;
    return end - start;
  }, [vitals]);

  // Posture distribution doughnut
  const postureDonutData = useMemo(() => {
    const dist = motionStats?.posture_distribution_pct || {};
    if (Object.keys(dist).length === 0) return null;
    const labels = Object.keys(dist);
    const data = Object.values(dist);
    const palette = [
      "#60a5fa",
      "#34d399",
      "#fbbf24",
      "#a78bfa",
      "#f87171",
      "#fb923c",
    ];
    return {
      labels,
      datasets: [
        {
          data,
          backgroundColor: palette.slice(0, labels.length),
          borderWidth: 0,
        },
      ],
    };
  }, [motionStats]);

  const pieOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: "bottom", labels: { color: "#d1d5db", padding: 12 } },
    },
  };

  // ── RENDER ───────────────────────────────────────────────────────
  return (
    <div className="flex flex-col items-center w-screen min-h-screen bg-black px-4 md:px-10 lg:px-16 pt-20 pb-16 text-gray-200">
      {/* Header */}
      <h1 className="text-5xl md:text-6xl font-extrabold mb-2">
        Sleep Pattern Analysis
      </h1>
      <p className="text-lg text-gray-400 max-w-2xl text-center mb-8">
        Comprehensive overview of your sleep quality — breathing events, heart
        rate, sleep stages, motion and posture.
      </p>

      {/* Action bar */}
      <div className="flex flex-col md:flex-row gap-4 mb-10 w-full max-w-5xl items-center justify-center">
        <input
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
          className="w-full md:w-auto text-sm text-gray-300 file:mr-4 file:py-2 file:px-4 file:border file:border-gray-600 file:rounded-lg file:bg-transparent file:text-gray-200 hover:file:border-gray-400"
        />
        <button
          onClick={handleUploadSession}
          disabled={analyzing}
          className="px-6 py-3 border border-gray-600 text-gray-200 rounded-lg transition hover:bg-[#1a1a1a] hover:border-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {analyzing ? "Uploading & Analyzing..." : "Upload & Analyze Sleep File"}
        </button>
        <button
          onClick={handleRunAnalysis}
          disabled={analyzing || !uploadedSessionPath}
          className="px-6 py-3 border border-gray-600 text-gray-200 rounded-lg transition hover:bg-[#1a1a1a] hover:border-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {analyzing ? "Running Analysis..." : "Run Manual Analysis"}
        </button>
        <button
          onClick={fetchFullSession}
          disabled={loading}
          className="px-6 py-3 border border-gray-600 text-gray-200 rounded-lg transition hover:bg-[#1a1a1a] hover:border-gray-400 hover:text-white disabled:opacity-50"
        >
          Refresh Data
        </button>
      </div>
      {uploadedSessionPath && (
        <p className="text-sm text-green-400 mb-6 text-center break-all">
          ✓ Loaded dataset: {uploadedSessionPath}
        </p>
      )}

      {/* Loading / Error states */}
      {loading && (
        <p className="text-gray-500 text-lg animate-pulse">
          Loading sleep data...
        </p>
      )}

      {!loading && error && (
        <Card className="max-w-xl w-full text-center">
          <p className="text-gray-400 mb-4">{error}</p>
          <p className="text-sm text-gray-600">
            Run the analysis first or make sure the backend server is online.
          </p>
        </Card>
      )}

      {/* ── Dashboard content ──────────────────────────────────── */}
      {!loading && !error && (
        <div className="w-full max-w-7xl space-y-8">
          {/* ── Row 1: Summary cards ─────────────────────────────── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <Stat
                label="Severity"
                value={summary?.severity || "—"}
                colorClass={severityColor(summary?.severity)}
              />
            </Card>
            <Card>
              <Stat
                label="Duration"
                value={fmtDuration(summary?.total_duration_sec)}
                sub={`${summary?.total_epochs || 0} epochs`}
              />
            </Card>
            <Card>
              <Stat
                label="Sleep Efficiency"
                value={
                  sleepStructure?.sleep_efficiency_pct != null
                    ? `${sleepStructure.sleep_efficiency_pct.toFixed(1)}%`
                    : "—"
                }
                sub={sleepStructure?.efficiency_rating || ""}
                colorClass={
                  sleepStructure?.sleep_efficiency_pct >= 85
                    ? "text-green-400"
                    : sleepStructure?.sleep_efficiency_pct >= 70
                    ? "text-yellow-400"
                    : "text-red-400"
                }
              />
            </Card>
            <Card>
              <Stat
                label="Apnea / Hour"
                value={
                  summary?.apnea_events_per_hour != null
                    ? summary.apnea_events_per_hour.toFixed(1)
                    : "—"
                }
                sub="AHI"
                colorClass={
                  (summary?.apnea_events_per_hour || 0) < 5
                    ? "text-green-400"
                    : (summary?.apnea_events_per_hour || 0) < 15
                    ? "text-yellow-400"
                    : "text-red-400"
                }
              />
            </Card>
          </div>

          {/* ── Row 2: Sleep structure summary bar ────────────────── */}
          {sleepStructure && sleepStructure.pct_per_stage && (
            <Card title="Sleep Stage Distribution">
              <div className="space-y-3">
                {Object.entries(stageDistribution).map(
                  ([stage, pct]) => (
                    <div key={stage}>
                      <div className="flex justify-between text-sm text-gray-300 mb-1">
                        <span className="flex items-center gap-2">
                          <span
                            className="inline-block w-3 h-3 rounded-sm"
                            style={{
                              backgroundColor:
                                STAGE_COLORS[stage] || "#6b7280",
                            }}
                          />
                          {stage}
                        </span>
                        <span>{pct?.toFixed(1) ?? 0}%</span>
                      </div>
                      {pctBar(
                        pct,
                        stage === "Deep"
                          ? "bg-emerald-400"
                          : stage === "Light"
                          ? "bg-blue-400"
                          : stage === "REM"
                          ? "bg-violet-400"
                          : "bg-red-400"
                      )}
                    </div>
                  )
                )}
              </div>
              <div className="flex flex-wrap gap-6 mt-4 text-sm text-gray-400">
                <span>
                  Onset latency:{" "}
                  <span className="text-gray-200">
                    {fmtDuration(sleepStructure.sleep_onset_latency_sec)}
                  </span>
                </span>
                <span>
                  REM episodes:{" "}
                  <span className="text-gray-200">
                    {sleepStructure.rem_episodes ?? "—"}
                  </span>
                </span>
                <span>
                  Total:{" "}
                  <span className="text-gray-200">
                    {sleepStructure.total_duration_min
                      ? `${sleepStructure.total_duration_min.toFixed(0)} min`
                      : "—"}
                  </span>
                </span>
              </div>
            </Card>
          )}

          {/* ── Row 3: Vital signs line chart ─────────────────────── */}
          {vitalsChartData && (
            <Card title="Vital Signs Over Time">
              <div className="h-72 md:h-80">
                <Line
                  data={vitalsChartData}
                  options={vitalsChartOptions}
                />
              </div>
              <p className="text-xs text-gray-400 mt-2">
                Full session timeline: 00:00 to {fmtClock(vitalsDurationSec)} ({fmtDuration(vitalsDurationSec || summary?.total_duration_sec || 0)})
              </p>
            </Card>
          )}

          {/* ── Row 4: Hypnogram ──────────────────────────────────── */}
          {hypnogramData && (
            <Card title="Sleep Hypnogram">
              <div className="flex gap-4 mb-3">
                {Object.entries(STAGE_COLORS).map(([s, c]) => (
                  <span
                    key={s}
                    className="flex items-center gap-1 text-xs text-gray-400"
                  >
                    <span
                      className="inline-block w-3 h-3 rounded-sm"
                      style={{ backgroundColor: c }}
                    />
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

          {/* ── Row 5: Charts row (pie charts) ────────────────────── */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {eventPieData && (
              <Card title="Sleep Event Types">
                <div className="h-56">
                  <Pie data={eventPieData} options={pieOpts} />
                </div>
              </Card>
            )}
            {stageDonutData && (
              <Card title="Stage Breakdown">
                <div className="h-56">
                  <Doughnut data={stageDonutData} options={pieOpts} />
                </div>
              </Card>
            )}
            {postureDonutData && (
              <Card title="Posture Distribution">
                <div className="h-56">
                  <Doughnut data={postureDonutData} options={pieOpts} />
                </div>
              </Card>
            )}
          </div>

          {/* ── Row 6: Event count details ─────────────────────────── */}
          {summary?.event_counts &&
            Object.keys(summary.event_counts).length > 0 && (
              <Card title="Breathing Event Breakdown">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(summary.event_counts).map(
                    ([name, count]) => (
                      <div
                        key={name}
                        className="bg-[#131313] border border-gray-800 rounded-lg p-3 text-center"
                      >
                        <p className="text-xs text-gray-500 uppercase">
                          {name.replace(/_/g, " ")}
                        </p>
                        <p className="text-xl font-bold text-gray-200">
                          {count}
                        </p>
                        {summary.event_time_sec?.[name] != null && (
                          <p className="text-xs text-gray-600">
                            {fmtDuration(summary.event_time_sec[name])}
                          </p>
                        )}
                      </div>
                    )
                  )}
                </div>
              </Card>
            )}

          {/* ── Row 7: Motion timeline table ───────────────────────── */}
          {motionTimeline.length > 0 && (
            <Card title="Motion &amp; Posture Timeline">
              <div className="overflow-x-auto max-h-72 overflow-y-auto">
                <table className="w-full text-sm text-left text-gray-300">
                  <thead className="text-xs uppercase text-gray-500 border-b border-gray-700 sticky top-0 bg-[#0f0f0f]">
                    <tr>
                      <th className="py-2 px-3">Epoch</th>
                      <th className="py-2 px-3">Time</th>
                      <th className="py-2 px-3">Posture</th>
                      <th className="py-2 px-3">Motion Level</th>
                      <th className="py-2 px-3">Activity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {motionTimeline.map((row, i) => (
                      <tr
                        key={i}
                        className="border-b border-gray-800 hover:bg-[#1a1a1a]"
                      >
                        <td className="py-1.5 px-3">{row.epoch ?? i + 1}</td>
                        <td className="py-1.5 px-3">
                          {row.time_label || "—"}
                        </td>
                        <td className="py-1.5 px-3">
                          {row.posture || row.predicted_posture || "—"}
                        </td>
                        <td className="py-1.5 px-3">
                          {row.motion_level || row.predicted_motion || "—"}
                        </td>
                        <td className="py-1.5 px-3">
                          {row.activity || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Motion stats summary */}
              {motionStats?.motion_epoch_counts && (
                <div className="flex flex-wrap gap-4 mt-3 text-sm text-gray-400">
                  {Object.entries(motionStats.motion_epoch_counts).map(
                    ([k, v]) => (
                      <span key={k}>
                        {k.replace(/_/g, " ")}:{" "}
                        <span className="text-gray-200 font-semibold">
                          {v}
                        </span>
                      </span>
                    )
                  )}
                </div>
              )}
            </Card>
          )}

          {/* ── Row 8: Raw sleep events table ──────────────────────── */}
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
                      <tr
                        key={i}
                        className="border-b border-gray-800 hover:bg-[#1a1a1a]"
                      >
                        <td className="py-1.5 px-3">{e.epoch_index ?? i}</td>
                        <td className="py-1.5 px-3">
                          <span
                            className={
                              (e.event_type || "").toLowerCase() === "normal"
                                ? "text-green-400"
                                : "text-yellow-400"
                            }
                          >
                            {e.event_type || "—"}
                          </span>
                        </td>
                        <td className="py-1.5 px-3">
                          {e.RR_mean?.toFixed(1) ?? "—"}
                        </td>
                        <td className="py-1.5 px-3">
                          {e.HR_mean?.toFixed(1) ?? "—"}
                        </td>
                        <td className="py-1.5 px-3">
                          {e.duration_sec?.toFixed(1) ?? "—"}
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

      {/* Popup */}
      <ErrorPopup
        message={popupMessage}
        title={popupTitle}
        onClose={() => setPopupMessage("")}
      />

      {/* Footer */}
      <div className="w-full max-w-7xl mt-12 mb-8 text-center text-gray-500">
        <small>Radarix Sleep Pattern Dashboard, 2025</small>
      </div>
    </div>
  );
}

export default SleepPattern;
