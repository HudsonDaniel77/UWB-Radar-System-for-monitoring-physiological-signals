import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    document.title = "Radarix";
  }, []);

  // Load CSV and check credentials
  const validateUser = async (email, password) => {
  const response = await fetch("http://localhost:5003/get-users");
  const data = await response.text();

  const rows = data.trim().split("\n");
  const users = rows.slice(1).map((row) => {
    const [csvEmail, csvPass] = row.split(",");
    return { email: csvEmail.trim(), password: csvPass.trim() };
  });

  return users.find(
    (u) => u.email.toLowerCase() === email.toLowerCase() && u.password === password
  );
};


  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg("");

    try {
      const user = await validateUser(email, password);

      if (!user) {
        setErrorMsg("Invalid email or password.");
        return;
      }

      // Save logged in user
      localStorage.setItem("loggedUser", email);
      localStorage.setItem("logged_in", "true");

      navigate("/home");
    } catch (error) {
      console.error(error);
      setErrorMsg("Login failed. Try again.");
    }
  };

  return (
    <div className="w-screen min-h-screen bg-black text-gray-200 overflow-hidden">
      <div className="pt-24 flex justify-center">
        <div className="bg-[#0f0f0f] p-10 rounded-2xl shadow-xl shadow-black/60 w-[90%] max-w-md border border-gray-800">
          
          <h2 className="text-3xl font-bold mb-6 text-center">Login</h2>

          {errorMsg && (
            <p className="text-red-400 text-center mb-4">{errorMsg}</p>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block mb-1 text-sm font-medium">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2 rounded-lg bg-[#111111] border border-gray-700 text-gray-200
                           focus:outline-none focus:ring-0 focus:border-gray-500"
              />
            </div>

            <div>
              <label className="block mb-1 text-sm font-medium">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-2 rounded-lg bg-[#111111] border border-gray-700 text-gray-200
                           focus:outline-none focus:ring-0 focus:border-gray-500"
              />
            </div>

            <button
              type="submit"
              className="w-full py-2 rounded-lg font-semibold bg-[#2a2a2a] border border-gray-700 text-gray-200
                         hover:bg-[#333333] hover:border-gray-500 hover:text-white transition"
            >
              Login
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-gray-400">
            Don’t have an account?{" "}
            <button
              onClick={() => navigate("/signup")}
              className="text-gray-200 hover:text-white"
            >
              Create one
            </button>
          </p>

        </div>
      </div>
    </div>
  );
}
