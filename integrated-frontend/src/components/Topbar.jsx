import { useAuth } from "../context/useAuth.js";

function Topbar() {
  const { user, logout } = useAuth();

  return (
    <header className="bg-white border-b border-gray-100 px-6 py-4 flex justify-between items-center">
      <span className="text-sm text-muted">Welcome, {user?.name || "there"}</span>
      <button onClick={logout} className="text-sm text-danger hover:underline">
        Log out
      </button>
    </header>
  );
}

export default Topbar;
