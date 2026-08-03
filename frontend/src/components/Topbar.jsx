import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/useAuth.js";

function Topbar() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    function handleLogout() {
        logout();
        navigate("/login");
    }

    return (
        <header className="bg-white border-b px-6 py-4 flex justify-between items-center">
            <span className="text-sm text-gray-600">Welcome, {user?.name || "there"}</span>
            <button onClick={handleLogout} className="text-sm text-red-600 hover:underline">
                Log out
            </button>
        </header>
    );
}

export default Topbar;