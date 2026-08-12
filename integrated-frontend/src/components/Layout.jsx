import Sidebar from "./Sidebar.jsx";
import Topbar from "./Topbar.jsx";

function Layout({ children }) {
  return (
    <div className="min-h-screen flex flex-col sm:flex-row bg-gray-50">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}

export default Layout;
