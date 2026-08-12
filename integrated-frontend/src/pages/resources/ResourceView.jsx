/**
 * One generated resource, whichever kind it is.
 *
 * The route is `/resources/:resourceId` and the *type* comes from the fetched record, not
 * from the URL. One route rather than four means a resource can be linked, bookmarked and
 * refreshed — none of which works when the object is handed over in router state, which is
 * how this used to be done.
 *
 *     summary       a string           prose
 *     keypoints     ["...", ...]       bulleted list
 *     mcq           [{question, options[4], correct_answer}]   an interactive quiz
 *     practice_qsn  [{question, answer}]                       question, answer on demand
 */

import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../../api/client.js";
import { deleteResource, getResource, resourceLabel } from "../../api/resources.js";
import QualityBadge from "../../components/QualityBadge.jsx";
import McqQuiz from "./McqQuiz.jsx";
import PracticeQuestions from "./PracticeQuestions.jsx";

function Body({ resource }) {
  const { resource_type: type, content } = resource;

  if (content === null || content === undefined || (Array.isArray(content) && !content.length)) {
    return (
      <p className="bg-white rounded-lg shadow-sm p-5 text-sm text-gray-500">
        This resource came back empty. Try generating it again.
      </p>
    );
  }

  if (type === "summary") {
    return (
      <div className="bg-white rounded-lg shadow-sm p-6 whitespace-pre-wrap leading-relaxed text-gray-800">
        {content}
      </div>
    );
  }

  if (type === "keypoints") {
    return (
      <ul className="bg-white rounded-lg shadow-sm p-6 space-y-3 list-disc list-inside text-gray-800">
        {content.map((point, index) => (
          <li key={index}>{point}</li>
        ))}
      </ul>
    );
  }

  if (type === "mcq") return <McqQuiz questions={content} />;
  if (type === "practice_qsn") return <PracticeQuestions questions={content} />;

  // A type this build does not know about -- a fifth resource type added to the backend,
  // say. Showing the raw content beats showing nothing.
  return (
    <pre className="bg-white rounded-lg shadow-sm p-6 text-sm overflow-x-auto">
      {JSON.stringify(content, null, 2)}
    </pre>
  );
}

function ResourceView() {
  const { resourceId } = useParams();
  const navigate = useNavigate();
  const [resource, setResource] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchResource = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getResource(resourceId);
      setResource(res.data);
      setError("");
    } catch (err) {
      setError(errorMessage(err, "Could not load this resource."));
    } finally {
      setLoading(false);
    }
  }, [resourceId]);

  useEffect(() => {
    // Fetch-on-mount. The rule guards against cascading renders from derived state;
    // this is a request to an external system, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchResource();
  }, [fetchResource]);

  async function handleDelete() {
    if (!window.confirm("Delete this resource?")) return;
    try {
      await deleteResource(resourceId);
      navigate("/resources");
    } catch (err) {
      setError(errorMessage(err, "Could not delete this resource."));
    }
  }

  if (loading) return <p className="text-sm text-gray-500">Loading...</p>;

  if (error || !resource) {
    return (
      <div>
        <p className="text-sm text-red-600 mb-4">{error || "Resource not found."}</p>
        <Link to="/resources" className="text-sm text-blue-600 hover:underline">
          ← Back to Resources
        </Link>
      </div>
    );
  }

  const params = resource.params || {};

  return (
    <div>
      <Link to="/resources" className="text-sm text-blue-600 hover:underline mb-4 block">
        ← Back to Resources
      </Link>

      <div className="flex items-start justify-between gap-4 mb-2">
        <h1 className="text-2xl font-semibold">{resourceLabel(resource.resource_type)}</h1>
        <button onClick={handleDelete} className="text-sm text-red-600 hover:underline shrink-0">
          Delete
        </button>
      </div>

      <p className="text-xs text-gray-400 mb-3">
        Generated {new Date(resource.created_at).toLocaleString()}
        {/* whole_document runs record this; a passage run does not. */}
        {params.whole_document ? " from the whole document" : ""}
        {params.groups ? ` (${params.groups} group${params.groups === 1 ? "" : "s"})` : ""}
      </p>

      <QualityBadge resource={resource} className="mb-5" />

      <Body resource={resource} />
    </div>
  );
}

export default ResourceView;
