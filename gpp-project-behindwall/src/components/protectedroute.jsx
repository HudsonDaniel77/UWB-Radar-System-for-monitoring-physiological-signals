export default function ProtectedRoute({ children }) {
  const isLoggedIn = localStorage.getItem("logged_in") === "true";

  if (!isLoggedIn) {
    return (
      <div className="w-screen min-h-screen bg-[#0d0d0d] text-gray-100">
        <div className="pt-24 pl-12 text-center">

          <span className="text-5xl mb-4 block">🔒</span>
          <h2 className="text-3xl font-bold mb-2">Access Restricted</h2>
          <p className="text-lg">You must log in to access this page.</p>

        </div>

      </div>
    );
  }

  return children;
}
