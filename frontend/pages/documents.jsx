import { useState, useEffect } from "react";
import { listDocuments, getDocumentFile } from "../api/routes.jsx";
import ResourcesPanel from "../src/components/ResourcesPanel.jsx";


function Documents() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [viewerLoading, setViewerLoading] = useState(false);

  async function fetchDocuments() {
    setLoading(true);
    setError("");
    try {
      const res = await listDocuments();
      setDocuments(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not load documents.");
    } finally {
      setLoading(false);
    }
  }

  async function handleView(doc) {
    setSelectedDoc(doc);
    setViewerLoading(true);
    setError("");

    if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    setPdfUrl(null);

    try {
      const res = await getDocumentFile(doc.id);
      const blobUrl = URL.createObjectURL(res.data);
      setPdfUrl(blobUrl);
    } catch {
      setError("Could not load this document. Please try again.");
    } finally {
      setViewerLoading(false);
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount pattern, see https://react.dev/learn/you-might-not-need-an-effect
    fetchDocuments();
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-semibold">Your Documents</h1>
        <button
          onClick={fetchDocuments}
          className="text-sm text-blue-600 hover:underline"
        >
          Refresh
        </button>
      </div>
      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <div className="grid gap-6 md:grid-cols-2">
        <div className="bg-white rounded-lg shadow-sm p-4">
          {loading ? (
            <p className="text-sm text-gray-500">Loading documents...</p>
          ) : documents.length === 0 ? (
            <p className="text-sm text-gray-500">
              No documents yet — upload one from the Dashboard to get started.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="pb-2">Filename</th>
                  <th className="pb-2">Subject</th>
                  <th className="pb-2">Pages</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Chunks</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr
                    key={doc.id}
                    onClick={() => handleView(doc)}
                    className={`cursor-pointer border-b hover:bg-gray-50 ${
                      selectedDoc?.id === doc.id ? "bg-blue-50" : ""
                    }`}
                  >
                    <td className="py-2">{doc.filename}</td>
                    <td className="py-2">{doc.subject}</td>
                    <td className="py-2">{doc.page_count}</td>
                    <td className="py-2">{doc.chunk_count}</td>
                    <td className="py-2">
                      <span className="text-xs bg-gray-100 rounded px-2 py-1">
                        {doc.processing_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div>
          <div className="bg-white rounded-lg shadow-sm p-4 min-h-[400px] flex items-center justify-center">
            {!selectedDoc ? (
              <p className="text-sm text-gray-400">Select a document to view it here.</p>
            ) : viewerLoading ? (
              <p className="text-sm text-gray-500">Loading preview...</p>
            ) : pdfUrl ? (
              <iframe src={pdfUrl} title={selectedDoc.filename} className="w-full h-[500px] rounded border" />
            ) : null}
          </div>

          {selectedDoc && (
            <ResourcesPanel documentId={selectedDoc.id} documentStatus={selectedDoc.processing_status} />
          )}
        </div>
      </div>
    </div>
  );
}

export default Documents;