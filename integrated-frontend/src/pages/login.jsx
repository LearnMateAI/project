import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { loginUser } from "../api/auth.js";
import { errorMessage } from "../api/client.js";
import AuthAside from "../components/AuthAside.jsx";
import { useAuth } from "../context/useAuth.js";

function Login() {
  const { login, isAuthenticated } = useAuth();
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
    <div className="min-h-screen grid lg:grid-cols-2 bg-surface">
      <AuthAside
        heading="Study with material you can check."
        blurb="Upload a PDF and LearnMateAI turns it into summaries, key points and quizzes — every one of them graded by a second model, and every chat answer traced back to its pages."
      />

      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-sm animate-fade-in">
          <div className="lg:hidden w-11 h-11 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center mb-5 shadow-[0_6px_16px_-6px_rgba(35,64,224,0.55)]">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342" />
            </svg>
          </div>

          <h1 className="text-[26px] font-bold tracking-tight m-0">Welcome back</h1>
          <p className="text-[13.5px] text-muted mt-1.5 mb-7">
            Sign in to your LearnMateAI account
          </p>

          <form onSubmit={handleSubmit}>
            {error && <div className="notice notice-error mb-4">{error}</div>}

            <div className="mb-4">
              <label className="field-label" htmlFor="email">
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
                className="input"
                placeholder="you@example.com"
              />
            </div>

            <div className="mb-6">
              <label className="field-label" htmlFor="password">
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
                className="input"
                placeholder="••••••••"
              />
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full py-3">
              {loading ? (
                <>
                  <span className="spinner spinner-light" />
                  Signing in...
                </>
              ) : (
                "Sign in"
              )}
            </button>

            <p className="text-[13px] text-muted mt-5 text-center">
              Don&apos;t have an account?{" "}
              <Link to="/register" className="text-primary font-semibold no-underline hover:underline">
                Create one
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}

export default Login;
