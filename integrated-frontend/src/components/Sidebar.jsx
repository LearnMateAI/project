import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/documents", label: "Documents" },
  { to: "/resources", label: "Resources" },
  { to: "/chat", label: "Chat" },
  { to: "/analytics", label: "Analytics" },
];

function Sidebar() {
  return (
    <nav className="bg-white sm:w-56 w-full border-b sm:border-b-0 sm:border-r border-gray-100 p-4 shrink-0">
      <h2 className="font-display text-lg font-bold mb-6 hidden sm:block text-ink">
        LearnMateAI
      </h2>
      <ul className="flex sm:flex-col gap-2 overflow-x-auto">
        {navItems.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                  isActive ? "bg-ink-light text-ink" : "text-muted hover:bg-gray-50"
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
