import { useNavigate } from "react-router-dom";

function Dashboard() {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "null");

  function handleLogout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl font-semibold">Welcome, {user?.name || "there"}</h1>
        <button onClick={handleLogout} className="text-sm text-red-600">
          Log out
        </button>
      </div>
      <p className="text-gray-600">
        This is a placeholder — the real dashboard (document list, resource
        panel, chat) is built starting Day 4.
      </p>
    </div>
  );
}

export default Dashboard;