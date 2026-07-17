import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

function Home() {
  const navigate = useNavigate();
  const heroRef = useRef(null);

  useEffect(() => {
    document.title = "Radarix | Home";

    // Parallax effect
    const handleMouseMove = (e) => {
      const x = (e.clientX / window.innerWidth - 0.5) * 20;
      const y = (e.clientY / window.innerHeight - 0.5) * 20;
      if (heroRef.current) {
        heroRef.current.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  return (
    <div className="relative w-screen min-h-screen bg-white text-gray-800 px-6 md:px-12 lg:px-20 pt-32 overflow-hidden">

      {/* -------- Animated Radar Waves -------- */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-30">
        <div className="absolute h-64 w-64 rounded-full border border-gray-300 animate-ping"></div>
        <div className="absolute h-96 w-96 rounded-full border border-gray-400 animate-ping delay-300"></div>
        <div className="absolute h-40 w-40 rounded-full border border-gray-200"></div>
      </div>

      {/* -------- HERO SECTION -------- */}
      <section
        ref={heroRef}
        className="relative flex flex-col items-center text-center w-full mb-20 transition-transform duration-300"
      >

        {/* Glow Behind Title */}
        <div className="absolute top-1/2 -translate-y-1/2 h-40 w-40 md:h-56 md:w-56 bg-[rgba(255,255,255,0.06)]
                        blur-3xl rounded-full"></div>

        <h1 className="relative text-6xl md:text-7xl font-extrabold tracking-tight mb-6 drop-shadow-[0_0_35px_rgba(255,255,255,0.15)]">
          Radarix
        </h1>

        <h2 className="text-2xl md:text-3xl text-gray-600 max-w-3xl leading-relaxed mb-8">
          The Future of Non-Contact Health Monitoring
        </h2>

        <p className="text-lg md:text-xl text-gray-600 max-w-2xl">
          Experience precision tracking of heart rate and respiration using next-generation UWB radar — 
          no wearables, no wires, pure clarity.
        </p>
      </section>

      {/* -------- FEATURE GRID -------- */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-10 w-full mb-28">

        <div className="bg-white p-8 rounded-2xl border border-gray-300 shadow-xl hover:shadow-gray-200/40 hover:-translate-y-1 transition-all">
          <div className="text-4xl mb-4">📡</div>
          <h3 className="text-xl font-semibold mb-2">UWB Radar Precision</h3>
          <p className="text-gray-600">Capture micro-movements caused by heartbeat and breathing — fully non-contact.</p>
        </div>

        <div className="bg-white p-8 rounded-2xl border border-gray-300 shadow-xl hover:shadow-gray-200/40 hover:-translate-y-1 transition-all">
          <div className="text-4xl mb-4">🎛️</div>
          <h3 className="text-xl font-semibold mb-2">Signal Processing Engine</h3>
          <p className="text-gray-600">Noise-filtered extraction of physiological signals using DSP techniques.</p>
        </div>

        <div className="bg-white p-8 rounded-2xl border border-gray-300 shadow-xl hover:shadow-gray-200/40 hover:-translate-y-1 transition-all">
          <div className="text-4xl mb-4">📈</div>
          <h3 className="text-xl font-semibold mb-2">Real-Time Insights</h3>
          <p className="text-gray-600">Monitor heart rate, respiration, and movement patterns with live visualization.</p>
        </div>

      </section>

      {/* -------- CTA SECTION -------- */}
      <section className="flex flex-col items-center w-full mb-24">
        <h2 className="text-3xl md:text-4xl font-semibold mb-4">
          A New Standard in Health Technology
        </h2>

        <p className="text-gray-600 text-lg max-w-2xl text-center mb-8">
          Designed for homes, hospitals, and research labs — Radarix brings next-generation sensing to real-world environments.
        </p>

        <button
          onClick={() => navigate("/about")}
          className="px-8 py-3 rounded-lg border border-gray-300 text-gray-800 bg-white hover:bg-gray-100 hover:border-gray-400 transition"
        >
          Learn More
        </button>
      </section>
    <div className="w-full max-w-7xl mt-8 mb-12 text-center text-gray-600">
        <small>Radarix, 2025</small>
      </div>
    </div>
  );
}

export default Home;
