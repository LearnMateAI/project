import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { generateResource, listResources } from "../../api/routes.jsx";

const RESOURCE_TYPES = [
  { type: "summary", label: "Summary", path: "/resources/summary" },
  { type: "key_points", label: "Key Points", path: "/resources/key-points" },
];

const COMING_SOON = ["MCQs", "Practice Questions", "Short Answer"];

function ResourcesPanel({ documentId, documentStatus }) {
  const navigate = useNavigate();
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generatingType, setGeneratingType] = useState(null);
  const [error, setError] = useState("");

  async function fetchResources() {
    setLoading(true);
    try {
      const res = await listResources(documentId);
      setResources(res.data);
    } catch {
      setResources([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchResources();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId]);

  async function handleGenerate(resourceType) {
    setError("");
    setGeneratingType(resourceType);
    try {
      await generateResource({ documentId, resourceType });
      await fetchResources();
    } catch (err) {
      setError(err.response?.data?.detail || "Generation failed. Please try again.");
    } finally {
      setGeneratingType(null);
    }
  }

  function handleView(resource, path) {
    navigate(path, { state: { resource } });
  }

  const notReady = documentStatus !== "Ready";

  return (
    <div className="bg-white rounded-lg shadow-sm p-4 mt-4">
      <h3 className="font-medium mb-3">Resources</h3>

      {notReady && (
        <p className="text-sm text-amber-600 mb-3">
          This document is still processing — resource generation will be available once it's ready.
        </p>
      )}

      <div className="flex flex-wrap gap-2 mb-4">
        {RESOURCE_TYPES.map((rt) => (
          <button
            key={rt.type}
            onClick={() => handleGenerate(rt.type)}
            disabled={notReady || generatingType !== null}
            className="text-sm bg-blue-600 text-white rounded px-3 py-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generatingType === rt.type ? "Generating..." : `Generate ${rt.label}`}
          </button>
        ))}
        {COMING_SOON.map((label) => (
          <button
            key={label}
            disabled
            title="Coming Day 10"
            className="text-sm bg-gray-200 text-gray-500 rounded px-3 py-1.5 cursor-not-allowed"
          >
            {label}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

      {loading ? (
        <p className="text-sm text-gray-500">Loading resources...</p>
      ) : resources.length === 0 ? (
        <p className="text-sm text-gray-500">No resources generated yet.</p>
      ) : (
        <ul className="divide-y">
          {resources.map((r) => {
            const meta = RESOURCE_TYPES.find((rt) => rt.type === r.resource_type);
            return (
              <li key={r.id} className="py-2 flex justify-between items-center">
                <span className="text-sm">
                  {meta ? meta.label : r.resource_type} — {new Date(r.created_at).toLocaleString()}
                </span>
                <button
                  onClick={() => handleView(r, meta?.path || "/documents")}
                  className="text-sm text-blue-600 hover:underline"
                >
                  View
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default ResourcesPanel;