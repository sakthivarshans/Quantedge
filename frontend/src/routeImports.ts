// Shared between App.tsx (feeds React.lazy) and Layout.tsx (feeds hover-prefetch) so
// both resolve to the exact same dynamic import -- Vite dedupes repeated import() calls
// to the same module, so prefetching on hover costs nothing extra if the user does click.
//
// This lives in its own file rather than App.tsx deliberately: App.tsx imports Layout,
// and Layout needs this map, so defining it inside App.tsx created a circular import
// (App -> Layout -> App) that failed at runtime with "Cannot access 'routeImports'
// before initialization" -- the whole app rendered blank because of it.
export const routeImports = {
  dashboard: () => import("./pages/Dashboard"),
  scanner: () => import("./pages/Scanner"),
  pairDetail: () => import("./pages/PairDetail"),
  lab: () => import("./pages/StrategyLab"),
  risk: () => import("./pages/RiskPortfolio"),
  login: () => import("./pages/Login"),
  paperTrading: () => import("./pages/PaperTrading"),
  research: () => import("./pages/ResearchNotebook"),
};
