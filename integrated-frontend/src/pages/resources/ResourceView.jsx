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
import McqQuiz from "./McqQuiz.jsx";
import PracticeQuestions from "./PracticeQuestions.jsx";

function Body({ resource }) {
  const { resource_type: type, content } = resource;

  if (content === null || content === undefined || (Array.isArray(content) && !content.length)) {
    return (
      <p className="card p-6 text-[13px] text-muted">
        This resource came back empty. Try generating it again.
      </p>
    );
  }

  if (type === "summary") {
    return (
      <div className="card p-6 sm:p-7 whitespace-pre-wrap leading-[1.8] text-[14.5px] text-body">
        {content}
      </div>
    );
  }

  if (type === "keypoints") {
    return (
      <ul className="card p-6 sm:p-7 space-y-3.5 list-none m-0">
        {content.map((point, index) => (
          <li key={index} className="flex gap-3 text-[14px] leading-relaxed text-body">
            {/* A numbered chip rather than a bullet: key points are a set you work
                through, and the number is what you refer back to. */}
            <span className="shrink-0 w-6 h-6 rounded-lg bg-primary-light text-primary text-[11px] font-bold flex items-center justify-center mt-0.5">
              {index + 1}
            </span>
            {point}
          </li>
        ))}
      </ul>
    );
  }

  if (type === "mcq") return <McqQuiz questions={content} />;
  if (type === "practice_qsn") return <PracticeQuestions questions={content} />;

  // A type this build does not know about -- a fifth resource type added to the backend,
  // say. Showing the raw content beats showing nothing.
  return (
    <pre className="card p-6 text-[12.5px] overflow-x-auto text-body">
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

  if (loading) {
    return (
      <p className="flex items-center gap-2.5 text-[13px] text-muted">
        <span className="spinner" />
        Loading...
      </p>
    );
  }

  if (error || !resource) {
    return (
      <div className="max-w-lg">
        <p className="notice notice-error mb-4">{error || "Resource not found."}</p>
        <Link to="/resources" className="btn-secondary">
          ← Back to Resources
        </Link>
      </div>
    );
  }

  const params = resource.params || {};

  return (
    <div className="max-w-4xl">
      <Link
        to="/resources"
        className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-muted no-underline hover:text-primary mb-4"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
        </svg>
        Back to Resources
      </Link>

      <div className="flex items-start justify-between gap-4 mb-1.5">
        <h1 className="text-2xl font-bold tracking-tight m-0">
          {resourceLabel(resource.resource_type)}
        </h1>
        <button
          onClick={handleDelete}
          className="btn-secondary shrink-0 hover:text-danger hover:border-danger-light"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
          </svg>
          Delete
        </button>
      </div>

      <p className="text-[12px] text-subtle mb-3">
        Generated {new Date(resource.created_at).toLocaleString()}
        {/* whole_document runs record this; a passage run does not. */}
        {params.whole_document ? " from the whole document" : ""}
        {params.groups ? ` (${params.groups} group${params.groups === 1 ? "" : "s"})` : ""}
      </p>

      <Body resource={resource} />
    </div>
  );
}

export default ResourceView;
