// src/pages/Statistics.jsx
import React, { useEffect, useState } from "react";
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
import { Bar, Line, Pie, Scatter } from "react-chartjs-2";

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

// === CONFIG: change if your Flask server runs elsewhere ===
// Use environment variable VITE_EDA_BASE if set, otherwise fallback to localhost.
const EDA_BACKEND_BASE = (import.meta && import.meta.env && import.meta.env.VITE_EDA_BASE) || "http://127.0.0.1:5001";

// ===== Utilities =====
function computeStats(values) {
  const clean = (values || []).filter((v) => typeof v === "number" && !isNaN(v));
  if (clean.length === 0) return { mean: 0, median: 0, min: 0, max: 0, std: 0, count: 0 };

  const mean = clean.reduce((a, b) => a + b, 0) / clean.length;
  const sorted = [...clean].sort((a, b) => a - b);
  const mid = Math.floor(clean.length / 2);
  const median = clean.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  const min = sorted[0];
  const max = sorted[sorted.length - 1];
  const variance = clean.map((v) => (v - mean) ** 2).reduce((a, b) => a + b, 0) / clean.length;
  const std = Math.sqrt(variance);
  return { mean, median, min, max, std, count: clean.length };
}

function histogramToBarData(bins, counts, label) {
  if (!bins || !counts || bins.length < 2) return null;
  const mids = [];
  for (let i = 0; i < bins.length - 1; i++) {
    const a = bins[i];
    const b = bins[i + 1];
    const mid = (Number(a) + Number(b)) / 2;
    mids.push(mid.toFixed(2));
  }
  return {
    labels: mids,
    datasets: [
      {
        label,
        data: counts,
        backgroundColor: "rgba(96,165,250,0.85)",
      },
    ],
  };
}

function computeHistogramFromArray(values, bins = 20) {
  const clean = (values || []).filter((v) => typeof v === "number" && !isNaN(v));
  if (clean.length === 0) return { bins: [], counts: [] };
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const binWidth = (max - min) / bins || 1;
  const edges = [];
  for (let i = 0; i <= bins; i++) edges.push(min + i * binWidth);
  const counts = new Array(bins).fill(0);
  for (const v of clean) {
    let idx = Math.floor(((v - min) / (max - min || 1)) * bins);
    if (idx === bins) idx = bins - 1;
    if (idx < 0) idx = 0;
    counts[idx] += 1;
  }
  return { bins: edges, counts };
}

// Defensive Boxplot component that won't crash when stats missing
function Boxplot({ stats, title }) {
  if (!stats || Object.keys(stats).length === 0) {
    return (
      <div className="bg-[#0b0b0b] border border-gray-700 rounded-xl p-4 shadow-md">
        <div className="text-gray-400">{title}</div>
        <div className="mt-2 text-gray-500">No data</div>
      </div>
    );
  }

  const padding = 12;
  const width = 360;
  const height = 140;
  const left = padding;
  const right = width - padding;

  const min = Number(stats.min ?? 0);
  const max = Number(stats.max ?? 1);
  const q1 = Number(stats.q1 ?? min);
  const q3 = Number(stats.q3 ?? max);
  const median = Number(stats.median ?? (q1 + q3) / 2);
  const range = max - min || 1;

  const x = (v) => left + ((v - min) / range) * (right - left);

  return (
    <div className="bg-[#0b0b0b] border border-gray-700 rounded-xl p-6 shadow-md">
      <div className="text-gray-200 font-semibold text-lg">{title}</div>

      <svg width={width} height={height} className="mt-4">
        <line x1={x(stats.lower_whisker ?? min)} y1={height/2}
              x2={x(stats.upper_whisker ?? max)} y2={height/2}
              stroke="#9CA3AF" strokeWidth="2" />

        <line x1={x(stats.lower_whisker ?? min)} y1={height/2-8}
              x2={x(stats.lower_whisker ?? min)} y2={height/2+8}
              stroke="#9CA3AF" strokeWidth="2" />

        <line x1={x(stats.upper_whisker ?? max)} y1={height/2-8}
              x2={x(stats.upper_whisker ?? max)} y2={height/2+8}
              stroke="#9CA3AF" strokeWidth="2" />

        <rect x={x(q1)} y={height/2-14}
              width={Math.max(2, x(q3) - x(q1))} height={28}
              fill="#111827" stroke="#60A5FA" strokeWidth="2" rx="4" />

        <line x1={x(median)} y1={height/2-16}
              x2={x(median)} y2={height/2+16}
              stroke="#FBBF24" strokeWidth="2.5" />

        {(stats.outliers || []).map((o, idx) => (
          <circle key={idx}
                  cx={x(Number(o))}
                  cy={height/2+26}
                  r="3"
                  fill="#EF4444" />
        ))}
      </svg>

      {/* Each stat in its own line */}
      <div
        className="mt-4 text-gray-100 font-semibold space-y-1"
        style={{ fontSize: "1rem" }}
      >
        <div>min: {min.toFixed(3)}</div>
        <div>q1: {q1.toFixed(3)}</div>
        <div>median: {median.toFixed(3)}</div>
        <div>q3: {q3.toFixed(3)}</div>
        <div>max: {max.toFixed(3)}</div>
      </div>
    </div>
  );
}


// ===== Main component =====
export default function Statistics() {
  useEffect(() => {
    document.title = "Radarix | Statistics";
  }, []);

  const [rows, setRows] = useState([]); // run-level records from /eda/runs
  const [loading, setLoading] = useState(true);
  const [overviewStats, setOverviewStats] = useState(null);
  const [anomalyStats, setAnomalyStats] = useState({ ok: 0, not_ok: 0 });


  // chart states
  const [barData, setBarData] = useState(null);
  const [lineData, setLineData] = useState(null);
  const [pieData, setPieData] = useState(null);
  const [scatterHRvsSQI, setScatterHRvsSQI] = useState(null);
  const [scatterHRvsRangeSD, setScatterHRvsRangeSD] = useState(null);
  const [mergedCorr, setMergedCorr] = useState(null);
  const [anomalies, setAnomalies] = useState([]);

  // histograms and boxplots
  const [histHeart, setHistHeart] = useState(null);
  const [histResp, setHistResp] = useState(null);
  const [histRange, setHistRange] = useState(null);
  const [histRangeSD, setHistRangeSD] = useState(null);
  const [histSQI, setHistSQI] = useState(null);

  const [boxHeart, setBoxHeart] = useState(null);
  const [boxResp, setBoxResp] = useState(null);
  const [boxRangeSD, setBoxRangeSD] = useState(null);

  const [scatterHRvsRR, setScatterHRvsRR] = useState(null);
  const [scatterHRvsRange, setScatterHRvsRange] = useState(null);
  const [scatterFinalVsClean, setScatterFinalVsClean] = useState(null);
  const [hypothesisResults, setHypothesisResults] = useState(null);
  const [calibrationData, setCalibrationData] = useState(null);
const [hrSQIGroups, setHRSQIGroups] = useState(null);
const [hrStressMatrix, setHRStressMatrix] = useState(null);



  useEffect(() => {
    // load everything
    fetchRuns();
    fetchOverview();
    fetchMergedCorrelation();
    fetchAnomalies();
    fetchHypothesisTests();


    // histograms and boxplots (backend chooses sample vs run)
    fetchHistogram("Heart_clean", setHistHeart);
    fetchHistogram("Resp_clean", setHistResp);
    fetchHistogram("Range_clean", setHistRange);

    fetchBoxplot("Heart_clean", setBoxHeart);
    fetchBoxplot("Resp_clean", setBoxResp);
    fetchBoxplot("Range_clean", setBoxRangeSD);
    fetchCalibrationData();
fetchHRSQIGroups();
fetchHRStressMatrix();

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ===== Fetch helpers with graceful handling =====
  async function fetchCalibrationData() {
  const res = await fetch(`${EDA_BACKEND_BASE}/eda/hypothesis/calibration_data`);
  setCalibrationData(await res.json());
}

async function fetchHRSQIGroups() {
  const res = await fetch(`${EDA_BACKEND_BASE}/eda/hypothesis/hr_sqi_groups`);
  setHRSQIGroups(await res.json());
}

async function fetchHRStressMatrix() {
  const res = await fetch(`${EDA_BACKEND_BASE}/eda/hypothesis/hr_stress_matrix`);
  setHRStressMatrix(await res.json());
}
  async function safeFetchJson(url) {
    try {
      const res = await fetch(url);
      if (!res.ok) {
        // return null for non-OK so callers can handle missing
        return null;
      }
      const json = await res.json();
      return json;
    } catch (err) {
      console.error("Fetch error:", url, err);
      return null;
    }
  }

  async function fetchRuns() {
    setLoading(true);
    try {
      const json = await safeFetchJson(`${EDA_BACKEND_BASE}/eda/runs`);
      if (!json) {
        setRows([]);
        setLoading(false);
        return;
      }
      // json should be an array of run objects
      const parsed = (json || []).map((r) => {
        // parse numeric fields defensively
        const copy = { ...r };
        const numFields = ["Avg_HR_clean", "Avg_RR_clean", "Avg_Range", "Range_SD", "SQI", "Final_Accurate_HR", "Run", "Rows"];
        numFields.forEach((f) => {
          if (copy[f] !== undefined && copy[f] !== null && copy[f] !== "") {
            copy[f] = Number(copy[f]);
            if (isNaN(copy[f])) copy[f] = null;
          } else {
            copy[f] = null;
          }
        });
        return copy;
      });

      setRows(parsed);
      prepareCharts(parsed);
      prepareRunLevelHistograms(parsed);
      prepareRunLevelBoxplots(parsed);
      prepareExtraScatters(parsed);
    } catch (err) {
      console.error("Error fetching runs", err);
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  async function fetchOverview() {
    const json = await safeFetchJson(`${EDA_BACKEND_BASE}/eda/overview`);
    if (!json) {
      setOverviewStats(null);
      return;
    }
    setOverviewStats(json);
  }

  async function fetchMergedCorrelation() {
    const json = await safeFetchJson(`${EDA_BACKEND_BASE}/eda/correlation_merged`);
    if (!json) {
      setMergedCorr(null);
      return;
    }
    setMergedCorr(json);
  }


async function fetchAnomalies() {
  const res = await fetch(`${EDA_BACKEND_BASE}/eda/anomalies`);
  const json = await res.json();

  // backend already returns { ok, not_ok }
  setAnomalyStats({
    ok: json.ok ?? 0,
    not_ok: json.not_ok ?? 0,
  });
}



  async function fetchHistogram(feature, setter) {
    const json = await safeFetchJson(`${EDA_BACKEND_BASE}/eda/histogram?feature=${encodeURIComponent(feature)}&bins=30`);
    if (!json || !json.bins || json.bins.length < 2) {
      setter(null);
      return;
    }
    setter(json);
  }

  async function fetchBoxplot(feature, setter) {
    const json = await safeFetchJson(`${EDA_BACKEND_BASE}/eda/boxplot?feature=${encodeURIComponent(feature)}`);
    if (!json || Object.keys(json).length === 0) {
      setter(null);
      return;
    }
    setter(json);
  }

async function fetchHypothesisTests() {
  try {
    const res = await fetch(`${EDA_BACKEND_BASE}/eda/hypothesis_tests`);
    const json = await res.json();

    // If error, store null
    if (json.error) {
      console.error("Hypothesis test error:", json.error);
      setHypothesisResults(null);
      return;
    }

    setHypothesisResults(json);  // Store the hypothesis results
  } catch (err) {
    console.error("Failed to fetch hypothesis tests:", err);
    setHypothesisResults(null);
  }
}


  // ===== Prepare charts from run-level rows =====
  function prepareCharts(data) {
    const hr = data.map((d) => d.Avg_HR_clean).filter((v) => typeof v === "number" && !isNaN(v));
    const rr = data.map((d) => d.Avg_RR_clean).filter((v) => typeof v === "number" && !isNaN(v));
    const range = data.map((d) => d.Avg_Range).filter((v) => typeof v === "number" && !isNaN(v));
    const rangeSD = data.map((d) => d.Range_SD).filter((v) => typeof v === "number" && !isNaN(v));
    const sqi = data.map((d) => d.SQI).filter((v) => typeof v === "number" && !isNaN(v));
    const finalHR = data.map((d) => d.Final_Accurate_HR).filter((v) => typeof v === "number" && !isNaN(v));

    const statsOverview = {
      Avg_HR_clean: computeStats(hr),
      Avg_RR_clean: computeStats(rr),
      Avg_Range: computeStats(range),
      Range_SD: computeStats(rangeSD),
      SQI: computeStats(sqi),
      Final_Accurate_HR: computeStats(finalHR),
      Runs: data.length,
    };
    setOverviewStats((prev) => ({ ...(prev || {}), ...statsOverview }));

    const labels = data.map((d) => (d.Run ? `Run ${d.Run}` : (d.Timestamp || "").toString()));

    // bar chart (avg vs final)
    setBarData({
      labels,
      datasets: [
        {
          label: "Avg HR (clean)",
          data: data.map((d) => (typeof d.Avg_HR_clean === "number" ? d.Avg_HR_clean : null)),
          backgroundColor: "rgba(59,130,246,0.9)",
        },
        {
          label: "Final Accurate HR",
          data: data.map((d) => (typeof d.Final_Accurate_HR === "number" ? d.Final_Accurate_HR : null)),
          backgroundColor: "rgba(239,68,68,0.9)",
        },
      ],
    });

    // line chart with two y axes (simple)
    setLineData({
      labels,
      datasets: [
        {
          label: "Avg HR (clean)",
          data: data.map((d) => (typeof d.Avg_HR_clean === "number" ? d.Avg_HR_clean : null)),
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59,130,246,0.07)",
          tension: 0.3,
          fill: true,
          yAxisID: "y",
        },
        {
          label: "Avg RR (clean)",
          data: data.map((d) => (typeof d.Avg_RR_clean === "number" ? d.Avg_RR_clean : null)),
          borderColor: "#fb7185",
          backgroundColor: "rgba(251,113,133,0.07)",
          tension: 0.3,
          fill: true,
          yAxisID: "y1",
        },
      ],
    });

    // pie for SQI buckets (defensive)
    const high = sqi.filter((v) => v >= 200).length;
    const medium = sqi.filter((v) => v >= 50 && v < 200).length;
    const low = sqi.filter((v) => v < 50).length;
    setPieData({
      labels: ["High SQI", "Medium SQI", "Low SQI"],
      datasets: [
        {
          data: [high, medium, low],
          backgroundColor: ["#10b981", "#f59e0b", "#ef4444"],
        },
      ],
    });

    // scatters
    setScatterHRvsSQI({
      datasets: [
        {
          label: "HR vs SQI",
          data: data.map((d) => ({ x: d.SQI, y: d.Avg_HR_clean, run: d.Run })),
          backgroundColor: "#3b82f6",
          pointRadius: 4,
        },
      ],
    });

    setScatterHRvsRangeSD({
      datasets: [
        {
          label: "HR vs Range_SD",
          data: data.map((d) => ({ x: d.Range_SD, y: d.Avg_HR_clean, run: d.Run })),
          backgroundColor: "#f97316",
          pointRadius: 4,
        },
      ],
    });
  }

  function prepareRunLevelHistograms(data) {
    const rangeSD = data.map((d) => d.Range_SD).filter((v) => typeof v === "number" && !isNaN(v));
    const sqi = data.map((d) => d.SQI).filter((v) => typeof v === "number" && !isNaN(v));
    setHistRangeSD(computeHistogramFromArray(rangeSD, 20));
    setHistSQI(computeHistogramFromArray(sqi, 20));
  }

  function prepareRunLevelBoxplots(data) {
    const vals = data.map((d) => d.Range_SD).filter((v) => typeof v === "number" && !isNaN(v));
    if (vals.length === 0) {
      setBoxRangeSD(null);
      return;
    }
    const arr = vals.slice().sort((a, b) => a - b);
    const q1 = quantile(arr, 0.25);
    const q3 = quantile(arr, 0.75);
    const median = quantile(arr, 0.5);
    const iqr = q3 - q1;
    const lw = q1 - 1.5 * iqr;
    const uw = q3 + 1.5 * iqr;
    const nonOut = arr.filter((v) => v >= lw && v <= uw);
    const lower_whisker = nonOut.length ? nonOut[0] : arr[0];
    const upper_whisker = nonOut.length ? nonOut[nonOut.length - 1] : arr[arr.length - 1];
    const outliers = arr.filter((v) => v < lw || v > uw);
    setBoxRangeSD({ q1, q3, median, iqr, lower_whisker, upper_whisker, min: arr[0], max: arr[arr.length - 1], outliers });
  }

  function prepareExtraScatters(data) {
    setScatterHRvsRR({
      datasets: [
        {
          label: "Avg HR vs Avg RR",
          data: data.map((d) => ({ x: d.Avg_RR_clean, y: d.Avg_HR_clean, run: d.Run })),
          backgroundColor: "#34D399",
          pointRadius: 4,
        },
      ],
    });

    setScatterHRvsRange({
      datasets: [
        {
          label: "Avg HR vs Avg Range",
          data: data.map((d) => ({ x: d.Avg_Range, y: d.Avg_HR_clean, run: d.Run })),
          backgroundColor: "#60A5FA",
          pointRadius: 4,
        },
      ],
    });

    setScatterFinalVsClean({
      datasets: [
        {
          label: "Final Accurate HR vs Avg Clean HR",
          data: data.map((d) => ({ x: d.Avg_HR_clean, y: d.Final_Accurate_HR, run: d.Run })),
          backgroundColor: "#F472B6",
          pointRadius: 4,
        },
      ],
    });
  }

  function quantile(sortedArr, q) {
    const pos = (sortedArr.length - 1) * q;
    const base = Math.floor(pos);
    const rest = pos - base;
    if (sortedArr[base + 1] !== undefined) {
      return sortedArr[base] + rest * (sortedArr[base + 1] - sortedArr[base]);
    } else {
      return sortedArr[base];
    }
  }

  if (loading) {
    return (
      <div className="w-screen min-h-screen bg-black flex items-center justify-center">
        <div className="text-gray-200 text-xl">Loading statistics...</div>
      </div>
    );
  }

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: { labels: { color: "white", font: { weight: "600" } } },
      title: { display: false },
      tooltip: { mode: "nearest" },
    },
    scales: {
      x: { ticks: { color: "rgb(200,200,200)" }, grid: { color: "#1f2937" } },
      y: { ticks: { color: "rgb(200,200,200)" }, grid: { color: "#1f2937" } },
      y1: { position: "right", ticks: { color: "rgb(200,200,200)" } },
    },
  };

  function renderCorrelationHeatmap(obj) {
    if (!obj || !obj.columns || !obj.matrix || obj.columns.length === 0) {
      return <div className="text-gray-400">No correlation data available.</div>;
    }
    const cols = obj.columns;
    const matrix = obj.matrix;
    const colorFor = (val) => {
      if (val === null || val === undefined || isNaN(val)) return "#1f2937";
      const v = Math.max(-1, Math.min(1, val));
      const green = Math.round(((v + 1) / 2) * 200);
      const red = Math.round(((1 - v) / 2) * 200);
      const blue = 60;
      return `rgb(${red}, ${green}, ${blue})`;
    };
    return (
      <div className="overflow-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr>
              <th className="px-2 py-1 text-left text-sm text-gray-300"> </th>
              {cols.map((c) => <th key={c} className="px-2 py-1 text-sm text-gray-300">{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {cols.map((r, i) => (
              <tr key={r}>
                <td className="px-2 py-1 text-sm text-gray-200 font-medium">{r}</td>
                {cols.map((c, j) => {
                  const val = (matrix[i] && matrix[i][j] !== undefined) ? matrix[i][j] : null;
                  const bg = val !== null ? colorFor(val) : "#111827";
                  const display = (val === null || val === undefined || isNaN(val)) ? "-" : (Math.round(val * 1000) / 1000).toFixed(3);
                  return (
                    <td key={`${i}-${j}`} className="px-2 py-1 text-sm text-white" style={{ background: bg, textAlign: "center", minWidth: 80 }}>
                      {display}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center w-screen min-h-screen bg-black px-6 md:px-12 lg:px-20 pt-20 text-gray-200">
      <h1 className="text-5xl md:text-6xl font-extrabold mb-2">Statistics</h1>
      <p className="text-lg md:text-xl max-w-3xl text-center mb-8 text-gray-300">
        Exploratory Data Analysis of radar-derived vitals.
      </p>

      {/* Top summary row */}
<div className="w-full max-w-7xl grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">

  {/* -------------------- OVERVIEW -------------------- */}
  <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
    <h3 className="text-lg font-semibold text-gray-200">Overview</h3>

    <p className="mt-2 text-sm text-gray-300">
      Runs: <span className="font-medium text-gray-100">
        {overviewStats?.runs ?? overviewStats?.runs_count ?? "-"}
      </span>
    </p>

    <p className="mt-1 text-sm text-gray-300">
      Avg HR: <span className="font-medium text-gray-100">
        {overviewStats?.avg_hr ? overviewStats.avg_hr.toFixed(2) : "-"}
      </span>
    </p>

    <p className="mt-1 text-sm text-gray-300">
      Avg RR: <span className="font-medium text-gray-100">
        {overviewStats?.avg_rr ? overviewStats.avg_rr.toFixed(2) : "-"}
      </span>
    </p>

    <p className="mt-1 text-sm text-gray-300">
      Avg Range: <span className="font-medium text-gray-100">
        {overviewStats?.avg_range ? overviewStats.avg_range.toFixed(3) : "-"} m
      </span>
    </p>
  </div>

  {/* -------------------- SIGNAL QUALITY -------------------- */}
  <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
    <h3 className="text-lg font-semibold text-gray-200">Signal Quality</h3>

    <p className="mt-2 text-sm text-gray-300">
      SQI Mean: <span className="font-medium text-gray-100">
        {overviewStats?.sqi_mean ? overviewStats.sqi_mean.toFixed(2) : "-"}
      </span>
    </p>

    <p className="mt-1 text-sm text-gray-300">
      SQI Standard Deviation: <span className="font-medium text-gray-100">
        {overviewStats?.sqi_std ? overviewStats.sqi_std.toFixed(2) : "-"}
      </span>
    </p>

    <p className="mt-1 text-sm text-gray-300">
      Good SQI (&gt;200): <span className="font-medium text-gray-100">
        {overviewStats?.good_sqi ?? 0}
      </span>
    </p>
  </div>

  {/* -------------------- FINAL CALIBRATED HR -------------------- */}
  <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
    <h3 className="text-lg font-semibold text-gray-200">Final HR (calibrated)</h3>

    <p className="mt-2 text-sm text-gray-300">
      Mean: <span className="font-medium text-gray-100">
        {overviewStats?.final_hr_mean ? overviewStats.final_hr_mean.toFixed(2) : "-"}
      </span>
    </p>

    <p className="mt-1 text-sm text-gray-300">
      Standard Deviation: <span className="font-medium text-gray-100">
        {overviewStats?.final_hr_std ? overviewStats.final_hr_std.toFixed(2) : "-"}
      </span>
    </p>

    <p className="mt-1 text-sm text-gray-300">
      Min / Max: <span className="font-medium text-gray-100">
        {overviewStats?.final_hr_min?.toFixed
          ? overviewStats.final_hr_min.toFixed(2)
          : "-"}{" "}
        /{" "}
        {overviewStats?.final_hr_max?.toFixed
          ? overviewStats.final_hr_max.toFixed(2)
          : "-"}
      </span>
    </p>
  </div>

</div>

      {/* Charts grid */}
      <div className="w-full max-w-7xl grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
          <h3 className="text-lg font-semibold text-gray-200 mb-2">Avg HR & Final HR per Run</h3>
          {barData && barData.labels && barData.labels.length > 0 ? <Bar data={barData} options={chartOptions} /> : <div className="text-gray-400">No run-level HR data to show.</div>}
        </div>

        <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
          <h3 className="text-lg font-semibold text-gray-200 mb-2">HR & RR Trends</h3>
          {lineData && lineData.labels && lineData.labels.length > 0 ? <Line data={lineData} options={chartOptions} /> : <div className="text-gray-400">No trend data.</div>}
        </div>

        <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
  <h3 className="text-lg font-semibold text-gray-200 mb-3">Signal Quality Buckets</h3>

  <div className="relative h-[260px]">
    {pieData && pieData.datasets?.[0]?.data?.some((v) => v > 0) ? (
      <Pie
        data={pieData}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              labels: { color: "white", font: { weight: 600 } },
            },
          },
        }}
      />
    ) : (
      <div className="text-gray-400">No SQI data.</div>
    )}
  </div>
</div>



        <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
  <h3 className="text-lg font-semibold text-gray-200 mb-3">HR vs SQI (scatter)</h3>

  <div className="relative h-[260px]">
    {scatterHRvsSQI && scatterHRvsSQI.datasets?.[0]?.data?.length > 0 ? (
      <Scatter
        data={scatterHRvsSQI}
        options={{
          ...chartOptions,
          maintainAspectRatio: false,
        }}
      />
    ) : (
      <div className="text-gray-400">No scatter data.</div>
    )}
  </div>
</div>



        <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg lg:col-span-2">
  <h3 className="text-lg font-semibold text-gray-200 mb-2">HR vs Movement (Range SD)</h3>

  <div className="relative h-[260px]"> 
    {scatterHRvsRangeSD && scatterHRvsRangeSD.datasets?.[0]?.data?.length > 0 ? (
      <Scatter
        data={scatterHRvsRangeSD}
        options={{
          ...chartOptions,
          maintainAspectRatio: false,
        }}
      />
    ) : (
      <div className="text-gray-400">No scatter data.</div>
    )}
  </div>
</div>

      </div>

      {/* Histograms */}
      <div className="w-full max-w-7xl mt-10">
        <h2 className="text-2xl font-semibold mb-4">Distributions (Histograms)</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="bg-[#0b0b0b] border border-gray-700 rounded-xl p-4 shadow-md">
            <h4 className="text-md text-gray-100 font-semibold mb-2">Heart Rate (samples)</h4>
            {histHeart && histogramToBarData(histHeart.bins, histHeart.counts, "Heart (samples)") ? (
              <Bar data={histogramToBarData(histHeart.bins, histHeart.counts, "Heart (samples)")} options={chartOptions} />
            ) : (
              <div className="text-gray-400">No sample-level heart data available.</div>
            )}
          </div>

          <div className="bg-[#0b0b0b] border border-gray-700 rounded-xl p-4 shadow-md">
            <h4 className="text-md text-gray-100 font-semibold mb-2">Respiration Rate (samples)</h4>
            {histResp && histogramToBarData(histResp.bins, histResp.counts, "Resp (samples)") ? (
              <Bar data={histogramToBarData(histResp.bins, histResp.counts, "Resp (samples)")} options={chartOptions} />
            ) : (
              <div className="text-gray-400">No sample-level respiration data available.</div>
            )}
          </div>

          <div className="bg-[#0b0b0b] border border-gray-700 rounded-xl p-4 shadow-md">
            <h4 className="text-md text-gray-100 font-semibold mb-2">Range / Distance (samples)</h4>
            {histRange && histogramToBarData(histRange.bins, histRange.counts, "Range (samples)") ? (
              <Bar data={histogramToBarData(histRange.bins, histRange.counts, "Range (samples)")} options={chartOptions} />
            ) : (
              <div className="text-gray-400">No sample-level range data available.</div>
            )}
          </div>

          <div className="bg-[#0b0b0b] border border-gray-700 rounded-xl p-4 shadow-md">
            <h4 className="text-md text-gray-100 font-semibold mb-2">Movement (Range_SD) — per run</h4>
            {histRangeSD && histogramToBarData(histRangeSD.bins, histRangeSD.counts, "Range_SD (runs)") ? (
              <Bar data={histogramToBarData(histRangeSD.bins, histRangeSD.counts, "Range_SD (runs)")} options={chartOptions} />
            ) : (
              <div className="text-gray-400">No run-level Range_SD data.</div>
            )}
          </div>

          <div className="bg-[#0b0b0b] border border-gray-700 rounded-xl p-4 shadow-md">
            <h4 className="text-md text-gray-100 font-semibold mb-2">Signal Quality Index (SQI) — per run</h4>
            {histSQI && histogramToBarData(histSQI.bins, histSQI.counts, "SQI (runs)") ? (
              <Bar data={histogramToBarData(histSQI.bins, histSQI.counts, "SQI (runs)")} options={chartOptions} />
            ) : (
              <div className="text-gray-400">No SQI data available.</div>
            )}
          </div>
        </div>
      </div>

      {/* Scatter plots */}
      <div className="w-full max-w-7xl mt-10">
        <h2 className="text-2xl font-semibold mb-4">Relationship Analysis (Scatter plots)</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-[#0b0b0b] border border-gray-700 rounded-xl p-4 shadow-md">
            <h4 className="text-md text-gray-100 font-semibold mb-2">Avg RR vs Avg HR (per run)</h4>
            {scatterHRvsRR ? <Scatter data={scatterHRvsRR} options={chartOptions} /> : <div className="text-gray-400">No data</div>}
          </div>

          <div className="bg-[#0b0b0b] border border-gray-700 rounded-xl p-4 shadow-md">
            <h4 className="text-md text-gray-100 font-semibold mb-2">Avg Range vs Avg HR (per run)</h4>
            {scatterHRvsRange ? <Scatter data={scatterHRvsRange} options={chartOptions} /> : <div className="text-gray-400">No data</div>}
          </div>

          <div className="bg-[#0b0b0b] border border-gray-700 rounded-xl p-4 shadow-md">
            <h4 className="text-md text-gray-100 font-semibold mb-2">Avg Clean HR vs Final Accurate HR (calibration)</h4>
            {scatterFinalVsClean ? <Scatter data={scatterFinalVsClean} options={chartOptions} /> : <div className="text-gray-400">No data</div>}
            <p className="text-xs text-gray-400 mt-2">This shows how calibration shifted the sensor HR toward the final accurate values.</p>
          </div>
        </div>
      </div>

      {/* Boxplots */}
      <div className="w-full max-w-7xl mt-10">
        <h2 className="text-2xl font-semibold mb-4">Boxplots & Outliers</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Boxplot stats={boxHeart} title="Heart Rate (samples) — boxplot" />
          <Boxplot 
            stats={{ 
              ...boxResp, 
              outliers: []   // <--- remove outliers
            }} 
            title="Respiration Rate (samples) — boxplot" 
          />
          <Boxplot stats={boxRangeSD} title="Range SD (runs) — boxplot" />
        </div>
      </div>

      {/* Correlation heatmap (merged) */}
      <div className="w-full max-w-7xl mt-10">
        <h2 className="text-2xl font-semibold mb-4">Merged Correlation (Cleaned Samples + Final Statistics)</h2>
        <div className="bg-[#0b0b0b] border border-gray-700 rounded-xl p-4 shadow-md">
          <p className="text-sm text-gray-400 mb-2">Correlation computed by merging cleaned sample-level data with run-level Final Statistics by nearest Timestamp.</p>
          {renderCorrelationHeatmap(mergedCorr)}
        </div>
      </div>

      {/* Run summaries */}
      <div className="w-full max-w-7xl mt-10">
        <h2 className="text-2xl font-semibold mb-4">Run Summaries (last 3 runs)</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {rows.slice(-3).map((r) => (
            <div key={r.Run ?? r.id} className="bg-[#0b0b0b] border border-gray-700 rounded-xl p-4 shadow-md">
              <h4 className="text-md text-gray-100 font-semibold mb-2">Run {r.Run ?? "-"} — <span className="text-sm text-gray-400">{r.Timestamp}</span></h4>
              <p className="text-sm text-gray-300"><strong>Avg HR:</strong> {r.Avg_HR_clean == null ? "-" : Number(r.Avg_HR_clean).toFixed(2)} bpm</p>
              <p className="text-sm text-gray-300"><strong>Final HR:</strong> {r.Final_Accurate_HR == null ? "-" : Number(r.Final_Accurate_HR).toFixed(2)} bpm</p>
              <p className="text-sm text-gray-300"><strong>Avg RR:</strong> {r.Avg_RR_clean == null ? "-" : Number(r.Avg_RR_clean).toFixed(2)} bpm</p>
              <p className="text-sm text-gray-300"><strong>Avg Range:</strong> {r.Avg_Range == null ? "-" : Number(r.Avg_Range).toFixed(3)} m</p>
              <p className="text-sm text-gray-300"><strong>Range SD:</strong> {r.Range_SD == null ? "-" : Number(r.Range_SD).toFixed(4)}</p>
              <p className="text-sm text-gray-300"><strong>SQI:</strong> {r.SQI == null ? "-" : Number(r.SQI).toFixed(2)}</p>
            </div>
          ))}
        </div>
      </div>
      {/* Anomalies Summary */}
      <div className="w-full max-w-7xl mt-10">
        <h2 className="text-2xl font-semibold mb-4">Detected Anomalies (From Final Statistics) </h2>

        <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
          <p className="text-sm text-gray-300">
            Number of runs that are OK : <span className="font-medium text-green-400">{anomalyStats?.ok ?? 0}</span>
          </p>

          <p className="mt-2 text-sm text-gray-300">
            Number of runs that are Not OK : <span className="font-medium text-red-400">{anomalyStats?.not_ok ?? 0}</span>
          </p>
        </div>
      </div>
      {/* Hypothesis Testing Results */}
<div className="w-full max-w-7xl mt-12">
  <h2 className="text-3xl font-bold mb-6 text-white">Hypothesis Testing Results</h2>

  {!hypothesisResults ? (
    <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
      <p className="text-gray-400 text-center">No hypothesis data available.</p>
    </div>
  ) : (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

      {/* Calibration Shift Test */}
      <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
        <h3 className="text-xl font-semibold text-blue-400 mb-4">
          Calibration Shift Test
        </h3>

        <div className="space-y-2 text-gray-200 text-sm">
          <p><strong className="text-gray-400">Interpretation:</strong><br /> 
            {hypothesisResults.CalibrationShift.interpretation}
          </p>

          <p><strong className="text-gray-400">Mean Difference:</strong> 
            {" "}{hypothesisResults.CalibrationShift.mean_difference.toFixed(3)}
          </p>

          <p><strong className="text-gray-400">Method:</strong> 
            {" "}{hypothesisResults.CalibrationShift.method}
          </p>

          <p><strong className="text-gray-400">P-value:</strong> 
            {" "}{hypothesisResults.CalibrationShift.p_value}
          </p>
        </div>
      </div>

      {/* HR vs SQI */}
      <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
        <h3 className="text-xl font-semibold text-green-400 mb-4">
          HR vs SQI Test
        </h3>

        <div className="space-y-2 text-gray-200 text-sm">
          <p><strong className="text-gray-400">Interpretation:</strong><br />
            {hypothesisResults.HR_vs_SQI.interpretation}
          </p>

          <p><strong className="text-gray-400">High SQI Mean:</strong> 
            {" "}{hypothesisResults.HR_vs_SQI.mean_High_SQI.toFixed(3)}
          </p>

          <p><strong className="text-gray-400">Low SQI Mean:</strong>  
            {" "}{hypothesisResults.HR_vs_SQI.mean_Low_SQI.toFixed(3)}
          </p>

          <p><strong className="text-gray-400">Method:</strong> 
            {" "}{hypothesisResults.HR_vs_SQI.method}
          </p>

          <p><strong className="text-gray-400">P-value:</strong> 
            {" "}{hypothesisResults.HR_vs_SQI.p_value}
          </p>
        </div>
      </div>

      {/* HR Class vs Stress Class */}
      <div className="bg-[#0f0f0f] border border-gray-700 rounded-xl p-6 shadow-lg">
        <h3 className="text-xl font-semibold text-red-400 mb-4">
          HR Class vs Stress Class
        </h3>

        <div className="space-y-2 text-gray-200 text-sm">
          <p><strong className="text-gray-400">Interpretation:</strong><br />
            {hypothesisResults.Association_HR_Stress.interpretation}
          </p>

          <p><strong className="text-gray-400">P-value:</strong> 
            {" "}{hypothesisResults.Association_HR_Stress.p_value}
          </p>

          <p><strong className="text-gray-400">Degrees of Freedom:</strong> 
            {" "}{hypothesisResults.Association_HR_Stress.degrees_of_freedom}
          </p>
        </div>
      </div>

    </div>
  )}
</div>
{/* Hypothesis Visualizations */}
<div className="w-full max-w-7xl mt-12 space-y-12">

  {/* ============ FIRST ROW (2 GRAPHS SIDE BY SIDE) ============ */}
  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

    {/* Clean vs Final HR Scatter */}
    <div className="bg-[#0f0f0f] p-6 rounded-xl border border-gray-700">
      <h3 className="text-lg mb-3 text-gray-200">Clean HR vs Final HR</h3>

      <div className="h-[230px]">
        {calibrationData && calibrationData.clean?.length > 0 ? (
          <Scatter
            data={{
              datasets: [{
                label: "Runs",
                data: calibrationData.clean.map((v, i) => ({ x: v, y: calibrationData.final[i] })),
                backgroundColor: "#60A5FA",
                pointRadius: 3,
              }],
            }}
            options={{
              ...chartOptions,
              maintainAspectRatio: false
            }}
          />
        ) : (
          <div className="text-gray-400">No data</div>
        )}
      </div>
    </div>

    {/* Difference Bar */}
    <div className="bg-[#0f0f0f] p-6 rounded-xl border border-gray-700">
      <h3 className="text-lg mb-3 text-gray-200">Calibration Difference (Final – Clean)</h3>

      <div className="h-[230px]">
        {calibrationData && calibrationData.clean?.length > 0 ? (
          <Bar
            data={{
              labels: calibrationData.clean.map((_, i) => `Run ${i + 1}`),
              datasets: [{
                label: "Shift",
                data: calibrationData.clean.map((v, i) => calibrationData.final[i] - v),
                backgroundColor: "#FBBF24",
              }],
            }}
            options={{
              ...chartOptions,
              maintainAspectRatio: false
            }}
          />
        ) : (
          <div className="text-gray-400">No data</div>
        )}
      </div>
    </div>

  </div>

  {/* ============ SECOND ROW (HR vs SQI) ============ */}
  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

    {/* HR Distribution for High vs Low SQI */}
    <div className="bg-[#0f0f0f] p-6 rounded-xl border border-gray-700">
      <h3 className="text-lg mb-3 text-gray-200">HR Distribution (High SQI vs Low SQI)</h3>

      <div className="h-[230px]">
        {hrSQIGroups ? (
          <Bar
            data={{
              labels: ["High SQI", "Low SQI"],
              datasets: [{
                label: "Mean HR",
                data: [
                  computeStats(hrSQIGroups.high).mean,
                  computeStats(hrSQIGroups.low).mean
                ],
                backgroundColor: ["#10B981", "#EF4444"],
              }],
            }}
            options={{
              ...chartOptions,
              maintainAspectRatio: false
            }}
          />
        ) : (
          <div className="text-gray-400">No data</div>
        )}
      </div>
    </div>

    {/* Heatmap for HR Class vs Stress Class */}
    <div className="bg-[#0f0f0f] p-6 rounded-xl border border-gray-700">
      <h3 className="text-lg mb-3 text-gray-200">HR Class vs Stress Class Heatmap</h3>

      <div className="overflow-auto max-h-[230px]">
        {hrStressMatrix ? (
          <table className="border-collapse text-sm w-full">
            <thead>
              <tr>
                <th className="text-gray-300 p-2"></th>
                {hrStressMatrix.labels.map((c) => (
                  <th key={c} className="text-gray-300 p-2">{c}</th>
                ))}
              </tr>
            </thead>

            <tbody>
              {hrStressMatrix.index.map((row, i) => (
                <tr key={row}>
                  <td className="text-gray-200 p-2 font-medium">{row}</td>

                  {hrStressMatrix.matrix[i].map((val, j) => {
                    const intensity = Math.min(1, val / Math.max(...hrStressMatrix.matrix.flat()));
                    const color = `rgba(${255 - intensity * 255}, ${50 + intensity * 150}, ${50}, 0.85)`;

                    return (
                      <td key={j}
                          className="p-2 text-center text-white font-semibold"
                          style={{ backgroundColor: color }}>
                        {val}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-gray-400">No data</div>
        )}
      </div>

    </div>

  </div>

</div>


      <div className="w-full max-w-7xl mt-8 mb-12 text-center text-gray-400">
        <small>Radarix, 2025</small>
      </div>
    </div>
  );
}