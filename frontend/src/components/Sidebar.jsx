import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/chat", label: "Chat" },
  { to: "/analytics", label: "Analytics" },
];

function Sidebar() {
  return (
    <nav className="bg-white sm:w-56 w-full border-b sm:border-b-0 sm:border-r p-4">
      <h2 className="text-lg font-bold mb-6 hidden sm:block">LearnMateAI</h2>
      <ul className="flex sm:flex-col gap-2">
        {navItems.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                `block px-3 py-2 rounded text-sm font-medium ${
                  isActive ? "bg-blue-100 text-blue-700" : "text-gray-600 hover:bg-gray-100"
                }`
              }
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export default Sidebar;