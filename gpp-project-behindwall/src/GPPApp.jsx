import { Routes, Route, useLocation } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import About from "./pages/About";
import RunSensor from "./pages/RunSensor";
import Statistics from "./pages/Statistics";
import Login from "./pages/Login";
import Signup from "./pages/Signup";

import ProtectedRoute from "./components/ProtectedRoute";

function GPPApp() {
  const location = useLocation();
  const hideLayout = false;

  return (
    <div className="font-sans bg-gray-50 min-h-screen">
      {!hideLayout && <Navbar />}

      <Routes>
        {/* Public pages */}
        <Route path="/login" element={<Login />} />
        <Route path="/home" element={<Home />} />
        <Route path="/about" element={<About />} />

        {/* Protected pages (only these two!) */}
        <Route
          path="/run-sensor"
          element={
            <ProtectedRoute>
              <RunSensor />
            </ProtectedRoute>
          }
        />

        <Route
          path="/statistics"
          element={
            <ProtectedRoute>
              <Statistics />
            </ProtectedRoute>
          }
        />

        {/* Redirect "/" to login */}
        <Route path="/" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
      </Routes>
    </div>
  );
}

export default GPPApp;
