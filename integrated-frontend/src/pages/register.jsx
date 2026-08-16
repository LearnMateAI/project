import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { registerUser } from "../api/auth.js";
import { errorMessage } from "../api/client.js";
import AuthAside from "../components/AuthAside.jsx";
import { useAuth } from "../context/useAuth.js";

function Register() {
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await registerUser(form);
      login(res.data.token, res.data.user);
      navigate("/dashboard");
    } catch (err) {
      // Registration errors are shown verbatim: "Password must contain at least one
      // number" is something the user can act on, and a form that cannot say what is
      // wrong cannot be completed.
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-surface">
      <AuthAside
        heading="Turn your reading list into study material."
        blurb="Built for students working through dense texts: upload once, then generate, quiz and question your way through it — with the source always a click away."
      />

      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-sm animate-fade-in">
          <div className="lg:hidden w-11 h-11 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center mb-5 shadow-[0_6px_16px_-6px_rgba(35,64,224,0.55)]">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342" />
            </svg>
          </div>

          <h1 className="text-[26px] font-bold tracking-tight m-0">Create your account</h1>
          <p className="text-[13.5px] text-muted mt-1.5 mb-7">Start learning with LearnMateAI</p>

          <form onSubmit={handleSubmit}>
            {error && <div className="notice notice-error mb-4">{error}</div>}

            <div className="mb-4">
              <label className="field-label" htmlFor="name">
                Name
              </label>
              <input
                id="name"
                name="name"
                value={form.name}
                onChange={handleChange}
                required
                autoComplete="name"
                className="input"
                placeholder="Your full name"
              />
            </div>

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

            <div>
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
                minLength={8}
                autoComplete="new-password"
                className="input"
                placeholder="••••••••"
              />
              {/* Mirrors the server-side rule in app/auth/users.py. The server enforces it
                  regardless; this is only so the user learns it before submitting. */}
              <p className="field-hint">At least 8 characters, including one number.</p>
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full py-3 mt-6">
              {loading ? (
                <>
                  <span className="spinner spinner-light" />
                  Creating account...
                </>
              ) : (
                "Create account"
              )}
            </button>

            <p className="text-[13px] text-muted mt-5 text-center">
              Already have an account?{" "}
              <Link to="/login" className="text-primary font-semibold no-underline hover:underline">
                Sign in
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}

export default Register;
