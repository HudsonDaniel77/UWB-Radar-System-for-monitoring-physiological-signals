import { Link, useNavigate, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";

function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [loggedIn, setLoggedIn] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // Re-check login state on EVERY page change
  useEffect(() => {
    setLoggedIn(localStorage.getItem("logged_in") === "true");
  }, [location.pathname]);

  const handleLogout = () => {
    localStorage.removeItem("logged_in");
    setLoggedIn(false);
    navigate("/");
  };

  const handleDropdownClick = (path) => {
    navigate(path);
    setDropdownOpen(false);
  };

  return (
    <nav className="bg-black/90 shadow-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
        <div className="text-3xl md:text-3xl font-extrabold text-white">Radarix</div>
        <div className="space-x-6 flex items-center">
          <Link to="/home" className="text-gray-300 hover:text-white font-semibold">Home</Link>
          <Link to="/about" className="text-gray-300 hover:text-white font-semibold">About</Link>
          
          {/* Run Sensor Dropdown */}
          <div className="relative group">
            <button className="text-gray-300 font-semibold flex items-center gap-1 py-2 focus:outline-none ring-0 focus:ring-0 focus:border-transparent border-0" style={{ outline: 'none', boxShadow: 'none' }}>
              Run Sensor
              <svg className="w-4 h-4 transition-transform group-hover:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
              </svg>
            </button>
            
            {/* Dropdown menu */}
            <div className="absolute left-0 mt-0 w-48 bg-[#0f0f0f] border border-gray-700 rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200">
              <button
                onClick={() => handleDropdownClick("/run-sensor")}
                className="block w-full text-left px-4 py-3 text-gray-300 hover:text-white hover:bg-[#1a1a1a] rounded-t-lg focus:outline-none ring-0 focus:ring-0 focus:border-transparent border-0"
                style={{ outline: 'none', boxShadow: 'none' }}
              >
                Health Check
              </button>
              <button
                onClick={() => handleDropdownClick("/run-sensor-behindwall")}
                className="block w-full text-left px-4 py-3 text-gray-300 hover:text-white hover:bg-[#1a1a1a] focus:outline-none ring-0 focus:ring-0 focus:border-transparent border-0"
                style={{ outline: 'none', boxShadow: 'none' }}
              >
                Behind Wall Detection
              </button>
              <button
                onClick={() => handleDropdownClick("/run-sensor-sleep")}
                className="block w-full text-left px-4 py-3 text-gray-300 hover:text-white hover:bg-[#1a1a1a] rounded-b-lg focus:outline-none ring-0 focus:ring-0 focus:border-transparent border-0"
                style={{ outline: 'none', boxShadow: 'none' }}
              >
                Sleep Detection
              </button>
            </div>
          </div>

          <Link to="/statistics" className="text-gray-300 hover:text-white font-semibold">Statistics</Link>

          {/* LOGIN / LOGOUT */}
          {!loggedIn ? (
            <Link
              to="/"
              className="text-gray-300 hover:text-white font-semibold"
            >
              Login
            </Link>
          ) : (
            <span
              onClick={handleLogout}
              className="cursor-pointer text-gray-300 hover:text-white font-semibold"
            >
              Logout
            </span>
          )}
        </div>
      </div>
    </nav>
  );
}

export default Navbar;
