import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { routeImports } from "../routeImports";

const navItems = [
  { to: "/", label: "Dashboard", icon: "◆", prefetch: routeImports.dashboard },
  { to: "/scanner", label: "Market Scanner", icon: "⌕", prefetch: routeImports.scanner },
  { to: "/lab", label: "Strategy Lab", icon: "⚙", prefetch: routeImports.lab },
  { to: "/risk", label: "Risk & Portfolio", icon: "▲", prefetch: routeImports.risk },
  { to: "/paper-trading", label: "Paper Trading", icon: "●", prefetch: routeImports.paperTrading },
  { to: "/research", label: "Research Notebook", icon: "▤", prefetch: routeImports.research },
];

export default function Layout() {
  const { token, email, name, pictureUrl, logout } = useAuth();
  const location = useLocation();
  return (
    <div className="flex min-h-screen bg-[#060814] text-gray-200">
      <aside className="w-60 shrink-0 border-r border-[#1b2032] bg-[#080b18] flex flex-col">
        <div className="px-5 py-5 border-b border-[#1b2032]">
          <div className="text-lg font-semibold tracking-tight text-white">QuantEdge</div>
          <div className="text-xs text-gray-500">Statistical Arbitrage Platform</div>
        </div>
        <nav className="flex-1 py-4">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              onMouseEnter={() => item.prefetch()}
              onFocus={() => item.prefetch()}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                  isActive
                    ? "bg-[#131828] text-white border-r-2 border-blue-500"
                    : "text-gray-400 hover:text-gray-200 hover:bg-[#0d1120]"
                }`
              }
            >
              <span className="w-4 text-center text-gray-500">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-[#1b2032] text-xs text-gray-600">
          {token ? (
            <div className="flex items-center gap-2">
              {pictureUrl ? (
                <img src={pictureUrl} alt="" className="w-7 h-7 rounded-full" referrerPolicy="no-referrer" />
              ) : (
                <div className="w-7 h-7 rounded-full bg-blue-600/30 text-blue-300 flex items-center justify-center text-xs font-medium">
                  {(name || email || "?").charAt(0).toUpperCase()}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="text-gray-300 truncate">{name || email}</div>
                <button onClick={logout} className="text-red-400 hover:underline text-xs">Sign out</button>
              </div>
            </div>
          ) : (
            <NavLink to="/paper-trading" className="text-blue-400 hover:underline">Sign in for Paper Trading</NavLink>
          )}
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <div key={location.pathname} className="animate-page-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
