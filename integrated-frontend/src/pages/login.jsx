import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { loginUser } from "../api/auth.js";
import { errorMessage } from "../api/client.js";
import { useAuth } from "../context/useAuth.js";
function Login() {
  const { login, loginWithKeycloak, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // Already signed in: nothing to do here.
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }
  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await loginUser(form);
      login(res.data.token, res.data.user);
      navigate("/dashboard");
    } catch (err) {
      // The backend deliberately does not say which half was wrong, so neither do we.
      setError(errorMessage(err, "Invalid email or password."));
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded-lg shadow-md w-full max-w-sm">
        <h1 className="text-xl font-semibold mb-6">Log in to LearnMateAI</h1>
        {error && (
          <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded p-2">
            {error}
          </div>
        )}
        <label className="block text-sm font-medium mb-1" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          name="email"
          value={form.email}
          onChange={handleChange}
          required
          autoComplete="email"
          className="w-full mb-4 border rounded px-3 py-2"
        />
        <label className="block text-sm font-medium mb-1" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          type="password"
          name="password"
          value={form.password}
          onChange={handleChange}
          required
          autoComplete="current-password"
          className="w-full mb-4 border rounded px-3 py-2"
        />
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white rounded py-2 disabled:opacity-50"
        >
          {loading ? "Logging in..." : "Log in"}
        </button>

        <div className="flex items-center gap-3 my-4">
          <div className="flex-1 h-px bg-gray-200" />
          <span className="text-xs text-gray-400">OR</span>
          <div className="flex-1 h-px bg-gray-200" />
        </div>

        <button
          type="button"
          onClick={loginWithKeycloak}
          className="w-full border border-gray-300 rounded py-2 text-sm font-medium hover:bg-gray-50"
        >
          Log in with Keycloak
        </button>

        <p className="text-sm text-gray-600 mt-4 text-center">
          Don&apos;t have an account?{" "}
          <Link to="/register" className="text-blue-600">
            Register
          </Link>
        </p>
      </form>
    </div>
  );
}
export default Login;
