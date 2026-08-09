import { useLocation, useNavigate } from "react-router-dom";

function ExplanationSummary() {
  const location = useLocation();
  const navigate = useNavigate();
  const resource = location.state?.resource;

  if (!resource) {
    return (
      <div>
        <p className="text-sm text-gray-500 mb-4">
          No summary selected. Go back to your documents and generate or select one.
        </p>
        <button onClick={() => navigate("/documents")} className="text-sm text-blue-600 hover:underline">
          ← Back to Documents
        </button>
      </div>
    );
  }

  return (
    <div>
      <button onClick={() => navigate("/documents")} className="text-sm text-blue-600 hover:underline mb-4 block">
        ← Back to Documents
      </button>
      <h1 className="text-2xl font-semibold mb-2">Summary</h1>
      <p className="text-xs text-gray-400 mb-4">
        Generated {new Date(resource.created_at).toLocaleString()}
      </p>
      <div className="bg-white rounded-lg shadow-sm p-6 whitespace-pre-wrap leading-relaxed text-gray-800">
        {resource.content}
      </div>
    </div>
  );
}

export default ExplanationSummary;