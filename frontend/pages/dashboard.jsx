function Dashboard() {
  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6"> Your Workspace</h1>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="bg-white rounded-lg shadow-sm p-5">
          <h2 className="font-medium mb-2">Documents</h2>
          <p className="text-sm text-gray-500 mb-4">No documents yet — upload one to get started.</p>
          <button
            disabled
            title="Coming Day 5"
            className="text-sm bg-blue-600 text-white rounded px-3 py-1.5 opacity-50 cursor-not-allowed"
          >
            Upload Document
          </button>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-5">
          <h2 className="font-medium mb-2">Generated Resources</h2>
          <p className="text-sm text-gray-500">
            Once you upload a document, generated summaries, key points, and quizzes will appear here.
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-5">
          <h2 className="font-medium mb-2">Your Analytics</h2>
          <p className="text-sm text-gray-500 mb-4">Track your study progress over time.</p>
          <a href="/analytics" className="text-sm text-blue-600 hover:underline">
            View analytics →
          </a>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;