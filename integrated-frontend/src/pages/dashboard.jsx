/**
 * The workspace overview: what to do next, and what you last made.
 *
 * Deliberately not a measurement page. The activity chart, the running totals and the mix
 * by type moved to Analytics, which is where a question like "how am I doing" is actually
 * being asked -- on the way in they were read as decoration above the two controls anybody
 * came here to use.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listDocuments } from "../api/documents.js";
import { listResources, resourceLabel } from "../api/resources.js";
import DocumentsCard from "../components/DocumentsCard.jsx";

const QUICK_START_BASE = [
  {
    key: "file",
    to: "/documents",
    title: "Upload a document",
    icon: "M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5",
  },
  {
    key: "resources",
    to: "/resources",
    title: "View Study Materials",
    icon: "M6.75 3.75h10.5A2.25 2.25 0 0119.5 6v12a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 18V6a2.25 2.25 0 012.25-2.25zM8.25 8.25h7.5m-7.5 3h7.5m-7.5 3h4.5",
  },
  {
    key: "ask",
    to: "/chat",
    title: "Ask a Question",
    icon: "M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155",
  },
];

function Dashboard() {
  const [resources, setResources] = useState([]);
  const [documents, setDocuments] = useState([]);

  const refresh = useCallback(async () => {
    // Neither call is worth failing the page over: a dashboard that renders the upload card
    // and an empty panel is far more useful than an error screen.
    try {
      const res = await listResources();
      setResources(res.data);
    } catch {
      setResources([]);
    }
    // Only for the names in "Recent resources": a resource carries the id of the document
    // it came from but not its filename, and "Summary" on its own does not say which PDF
    // it summarises once there is more than one.
    try {
      const res = await listDocuments();
      setDocuments(res.data);
    } catch {
      setDocuments([]);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount. The rule guards against cascading renders from derived state;
    // this is a request to an external system, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  // document_id -> filename, so a recent row can name the PDF it came from. Built once per
  // documents change rather than scanning the list inside the render for every row.
  const filenames = useMemo(
    () => new Map(documents.map((document) => [document.id, document.filename])),
    [documents],
  );

  const recent = resources.slice(0, 5);

  const quickStart = QUICK_START_BASE;

  return (
    <div>
      {/* Quick start ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-4 mb-3">
        <h2 className="section-title mb-0">Quick start</h2>
        <Link to="/tour" className="text-[12.5px] font-semibold text-primary no-underline hover:underline">
          Take a tour →
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 mb-6">
        {quickStart.map((action) => (
          <Link key={action.key} to={action.to} className="card card-hover p-4 flex items-center gap-4 no-underline">
            <span className="icon-tile">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
                <path strokeLinecap="round" strokeLinejoin="round" d={action.icon} />
              </svg>
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[14px] font-semibold text-heading truncate">{action.title}</span>
              <span className="block text-[12px] text-muted truncate">{action.caption}</span>
            </span>
            <svg className="w-5 h-5 text-subtle shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>
          </Link>
        ))}
      </div>

      {/* The measurements -- activity over time, the running totals and the mix by type --
          live on Analytics rather than here. A dashboard answers "what do I do next"; the
          numbers answer "how am I doing", and they were being read as decoration. */}
      <div className="grid gap-5 xl:grid-cols-2 items-start">
        <DocumentsCard onUploaded={refresh} />

        <section className="card">
            <div className="card-head">
              <h2>Recent resources</h2>
              <Link to="/resources" className="text-[12.5px] font-semibold text-primary no-underline hover:underline">
                View all →
              </Link>
            </div>

            {recent.length === 0 ? (
              <p className="px-5 py-6 text-[13px] text-muted leading-relaxed">
                Once a document is ready, open it from the library and generate materials.
              </p>
            ) : (
              <div>
                {recent.map((resource) => (
                  <Link key={resource.id} to={`/resources/${resource.id}`} className="list-row">
                    <span className="min-w-0">
                      <span className="block text-[13.5px] font-semibold text-heading truncate">
                        {resourceLabel(resource.resource_type, resource.params)}
                      </span>
                      {/* Which PDF it came from. Omitted rather than shown as a blank line
                          when the document has since been deleted and the id resolves to
                          nothing. */}
                      {filenames.get(resource.document_id) && (
                        <span className="block text-[11.5px] text-muted truncate">
                          {filenames.get(resource.document_id)}
                        </span>
                      )}
                      <span className="block text-[11.5px] text-subtle">
                        {new Date(resource.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </span>
                    </span>
                  </Link>
                ))}
              </div>
            )}
        </section>
      </div>
    </div>
  );
}

export default Dashboard;
