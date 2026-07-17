import { useEffect } from "react";

function About() {

  useEffect(() => {
    document.title = "Radarix | About";
  }, []);

  return (
    <div className="w-screen min-h-screen bg-black text-gray-200 px-6 md:px-12 lg:px-20 py-12">
      
      <h1 className="text-5xl md:text-6xl font-extrabold mb-2 text-center">
        About Radarix
      </h1>

      <main className="w-full flex-1 space-y-16">

        {/* ---------------- PROBLEM STATEMENT ---------------- */}
        <section>
          <h2 className="text-2xl font-semibold mb-3">Problem Statement</h2>

          <p className="text-gray-300 leading-relaxed">
            Continuous monitoring of vital signs such as heart rate, respiration rate,
            and body micro-movements is essential in healthcare, elderly care, and
            fitness applications. However, traditional contact-based monitoring systems—
            such as ECG electrodes, chest belts, and wrist-based wearables—suffer from
            major limitations. They require physical contact, cause discomfort during
            long-term use, are sensitive to motion artifacts, and rely heavily on user
            compliance.
            <br /><br />
            Radarix introduces a non-contact vital sign detection system using Ultra-Wideband (UWB)
            radar, which captures micro-movements from cardiac and respiratory activity.
            These radar signals are processed to extract heart rate, respiration rate,
            distance, motion levels, and anomalies, without requiring sensors on the body.
          </p>
        </section>


        {/* ---------------- DATASET 1 ---------------- */}
        <section>
          <h2 className="text-2xl font-semibold mb-3">Dataset Description</h2>

          {/* Dataset 1 */}
          <h3 className="text-xl font-semibold text-gray-100 mb-4">
            Dataset 1 — cleaned_vital_signs.csv (Sample-Level)
          </h3>

          <p className="text-gray-300 leading-relaxed mb-4">
            High-frequency sample-level measurements captured for every radar frame.
            Each row represents one radar sample and is used for waveform analysis,
            HR/RR accuracy study, and noise detection.
          </p>

          {/* TABLE 1 */}
          <div className="overflow-x-auto">
            <table className="w-full border border-gray-800 rounded-xl overflow-hidden">
              <thead className="bg-[#0f0f0f]/80">
                <tr>
                  <th className="px-4 py-3 border-b border-gray-700 text-left">Column</th>
                  <th className="px-4 py-3 border-b border-gray-700 text-left">Description</th>
                </tr>
              </thead>
              <tbody className="bg-[#0f0f0f]/40">
                {[
                  ["Timestamp", "Exact timestamp of the radar sample"],
                  ["User", "User email or identifier"],
                  ["SessionTime", "Seconds since measurement started"],
                  ["HeartRate_raw", "Raw HR estimate"],
                  ["RespirationRate_raw", "Raw RR estimate"],
                  ["Range_raw", "Raw radar-estimated distance"],
                  ["HeartWaveform", "Micro vibration amplitude from heartbeat"],
                  ["BreathWaveform", "Chest movement waveform from breathing"],
                  ["HeartRate_FFT", "Heart rate from FFT analysis"],
                  ["BreathRate_FFT", "Respiration rate from FFT analysis"],
                  ["ConfigurationFile", "Radar configuration index"],
                  ["Heart_clean", "Filtered HR after noise removal"],
                  ["Resp_clean", "Filtered RR"],
                  ["Range_clean", "Smoothed distance measurement"]
                ].map(([col, desc]) => (
                  <tr key={col} className="border-b border-gray-800">
                    <td className="px-4 py-3 font-medium">{col}</td>
                    <td className="px-4 py-3 text-gray-300">{desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>


        {/* ---------------- DATASET 2 ---------------- */}
        <section className="mt-16">
          <h3 className="text-xl font-semibold text-gray-100 mb-4">
            Dataset 2 — final_run_stats.csv (Run-Level)
          </h3>

          <p className="text-gray-300 leading-relaxed mb-4">
            Contains aggregated stats for each radar run (7–10 seconds). Used for
            accuracy analysis, calibration studies, and visualizations.
          </p>

          {/* TABLE 2 */}
          <div className="overflow-x-auto">
            <table className="w-full border border-gray-800 rounded-xl overflow-hidden">
              <thead className="bg-[#0f0f0f]/80">
                <tr>
                  <th className="px-4 py-3 border-b border-gray-700 text-left">Column</th>
                  <th className="px-4 py-3 border-b border-gray-700 text-left">Description</th>
                </tr>
              </thead>
              <tbody className="bg-[#0f0f0f]/40">
                {[
                  ["Timestamp", "Start time of the run"],
                  ["Rows", "Number of samples in the run"],
                  ["Avg_HR_clean", "Mean cleaned heart rate"],
                  ["Avg_RR_clean", "Mean cleaned respiration rate"],
                  ["Avg_Range", "Mean radar distance"],
                  ["Range_SD", "Movement score (SD of distance)"],
                  ["HR_SD", "Heart rate variability"],
                  ["RR_SD", "Respiration variability"],
                  ["HR_P2P", "Heart rate peak-to-peak value"],
                  ["RR_P2P", "Respiration rate peak-to-peak value"],
                  ["Range_Slope", "Distance change rate"],
                  ["SQI", "Signal Quality Index"],
                  ["Final_Accurate_HR", "Corrected/calibrated HR"],
                  ["Run", "Run ID / index"]
                ].map(([col, desc]) => (
                  <tr key={col} className="border-b border-gray-800">
                    <td className="px-4 py-3 font-medium">{col}</td>
                    <td className="px-4 py-3 text-gray-300">{desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

        </section>

      </main>
      <div className="w-full max-w-7xl mt-8 mb-12 text-center text-gray-400">
        <small>Radarix, 2025</small>
      </div>
    </div>
  );
}

export default About;
