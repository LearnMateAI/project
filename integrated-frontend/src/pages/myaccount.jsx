import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAnalytics } from "../api/analytics.js";
import { useAuth } from "../context/useAuth.js";

function MyAccount() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const res = await getAnalytics();
      setStats(res.data);
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount. The rule guards against cascading renders from derived state;
    // this is a request to an external system, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  const initials = (user?.name || "U")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <div className="animate-fade-in max-w-4xl">
      <div className="page-header">
        <h1>My Account</h1>
        <p>Manage your profile and view activity</p>
      </div>

      {/* Profile card */}
      <div className="card p-6 mb-6">
        <div className="flex items-center gap-5">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary to-accent text-white flex items-center justify-center text-xl font-bold shrink-0 shadow-[0_8px_20px_-8px_rgba(35,64,224,0.6)]">
            {initials}
          </div>
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-heading">{user?.name || "User"}</h2>
            <p className="text-[13px] text-muted">{user?.email || "No email"}</p>
            <p className="text-[12px] text-subtle mt-1">
              Member since {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
            </p>
          </div>
          <Link to="/account/settings" className="btn-secondary ml-auto shrink-0">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Settings
          </Link>
        </div>
      </div>

      {/* Activity stats */}
      <h2 className="text-[15px] font-semibold text-heading mb-3">Your Activity</h2>
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4 mb-6">
        <div className="stat-card">
          <p className="stat-label">Documents</p>
          <p className="stat-value">{stats?.documents ?? "—"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Resources</p>
          <p className="stat-value">{stats?.resources?.total ?? "—"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Conversations</p>
          <p className="stat-value">{stats?.sessions ?? "—"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Questions</p>
          <p className="stat-value">{stats?.questions_asked ?? "—"}</p>
        </div>
      </div>

    </div>
  );
}

export default MyAccount;
