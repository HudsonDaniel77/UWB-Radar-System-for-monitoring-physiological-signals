import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function Signup() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    document.title = "Radarix | Create Account";
  }, []);

  const handleSignup = async (e) => {
    e.preventDefault();
    setErrorMsg("");

    if (!email || !password) {
      setErrorMsg("Please fill out all fields.");
      return;
    }
    if (password.length < 6) {
      setErrorMsg("Password must be at least 6 characters.");
      return;
    }
    if (password !== confirm) {
      setErrorMsg("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch("http://localhost:5003/add-user", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();
      setLoading(false);

      if (data.success) {
        navigate("/login");
      } else {
        setErrorMsg(data.message || "Could not create account.");
      }
    } catch (err) {
      console.error(err);
      setLoading(false);
      setErrorMsg("Connection error. Make sure backend is running.");
    }
  };

  return (
    <div className="w-screen min-h-screen bg-black text-gray-200 overflow-hidden">
      <div className="pt-24 flex justify-center px-4">
        <div className="bg-[#0f0f0f] p-8 rounded-2xl shadow-xl w-full max-w-md border border-gray-800">

          <h2 className="text-3xl font-bold mb-6 text-center">Create Account</h2>

          {errorMsg && (
            <p className="text-red-400 text-center mb-4">{errorMsg}</p>
          )}

          <form onSubmit={handleSignup} className="space-y-4">

            <div>
              <label className="block mb-1 text-sm font-medium">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2 rounded-lg bg-[#111111] border border-gray-700"
              />
            </div>

            <div>
              <label className="block mb-1 text-sm font-medium">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-2 rounded-lg bg-[#111111] border border-gray-700"
              />
            </div>

            <div>
              <label className="block mb-1 text-sm font-medium">Confirm Password</label>
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                className="w-full px-4 py-2 rounded-lg bg-[#111111] border border-gray-700"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 rounded-lg font-semibold bg-[#2a2a2a] border border-gray-700"
            >
              {loading ? "Creating account..." : "Sign Up"}
            </button>

          </form>

          <p className="mt-4 text-center text-sm text-gray-400">
            Already have an account?{" "}
            <button
              onClick={() => navigate("/login")}
              className="text-gray-200 hover:text-white"
            >
              Log in
            </button>
          </p>

        </div>
      </div>
    </div>
  );
}
