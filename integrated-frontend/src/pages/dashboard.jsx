import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAnalytics } from "../api/analytics.js";
import { listResources, resourceLabel } from "../api/resources.js";
import DocumentsCard from "../components/DocumentsCard.jsx";

function Dashboard() {
  const [recent, setRecent] = useState([]);
  const [stats, setStats] = useState(null);

  const refresh = useCallback(async () => {
    // Neither of these is worth failing the page over: a dashboard that renders the upload
    // card and two empty panels is far more useful than an error screen.
    try {
      const res = await listResources();
      setRecent(res.data.slice(0, 5));
    } catch {
      setRecent([]);
    }
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

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Your Workspace</h1>

      <div className="grid gap-4 sm:grid-cols-3">
        <DocumentsCard onUploaded={refresh} />

        <div className="bg-white rounded-lg shadow-sm p-5">
          <h2 className="font-medium mb-2">Generated Resources</h2>
          {recent.length === 0 ? (
            <p className="text-sm text-gray-500">
              Once a document is ready, open it from Documents and generate summaries, key
              points, MCQs or practice questions.
            </p>
          ) : (
            <>
              <ul className="text-sm divide-y mb-3">
                {recent.map((resource) => (
                  <li key={resource.id} className="py-1.5">
                    <Link to={`/resources/${resource.id}`} className="text-blue-600 hover:underline">
                      {resourceLabel(resource.resource_type)}
                    </Link>
                    <span className="text-gray-400 text-xs ml-2">
                      {new Date(resource.created_at).toLocaleDateString()}
                    </span>
                  </li>
                ))}
              </ul>
              <Link to="/resources" className="text-sm text-blue-600 hover:underline">
                View all resources →
              </Link>
            </>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-sm p-5">
          <h2 className="font-medium mb-2">Your Analytics</h2>
          {stats ? (
            <dl className="text-sm text-gray-600 space-y-1 mb-4">
              <div className="flex justify-between">
                <dt>Documents</dt>
                <dd className="font-medium">{stats.documents}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Resources</dt>
                <dd className="font-medium">{stats.resources?.total ?? 0}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Questions asked</dt>
                <dd className="font-medium">{stats.questions_asked ?? 0}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-gray-500 mb-4">Track your study progress over time.</p>
          )}
          <Link to="/analytics" className="text-sm text-blue-600 hover:underline">
            View analytics →
          </Link>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
