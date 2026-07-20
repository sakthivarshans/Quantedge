import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./auth/AuthContext";
import { ToastProvider } from "./components/Toast";
import ProtectedRoute from "./auth/ProtectedRoute";
import Layout from "./components/Layout";
import { routeImports } from "./routeImports";

const Dashboard = lazy(routeImports.dashboard);
const Scanner = lazy(routeImports.scanner);
const PairDetail = lazy(routeImports.pairDetail);
const StrategyLab = lazy(routeImports.lab);
const RiskPortfolio = lazy(routeImports.risk);
const Login = lazy(routeImports.login);
const PaperTrading = lazy(routeImports.paperTrading);
const ResearchNotebook = lazy(routeImports.research);

function PageFallback() {
  return (
    <div className="p-8 space-y-4">
      <div className="h-8 w-64 bg-[#12151f] rounded animate-pulse" />
      <div className="h-4 w-96 bg-[#12151f] rounded animate-pulse" />
      <div className="grid grid-cols-4 gap-4 mt-6">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-24 bg-[#12151f] rounded-lg animate-pulse" />
        ))}
      </div>
    </div>
  );
}

// Data fetched via useQuery stays "fresh" for this long before a background
// refetch is triggered on next mount/focus -- this is what makes switching back
// to a tab you already visited feel instant instead of re-fetching from scratch.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <Suspense fallback={<PageFallback />}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route element={<Layout />}>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/scanner" element={<Scanner />} />
                  <Route path="/pairs/:a/:b" element={<PairDetail />} />
                  <Route path="/lab" element={<StrategyLab />} />
                  <Route path="/risk" element={<RiskPortfolio />} />
                  <Route element={<ProtectedRoute />}>
                    <Route path="/paper-trading" element={<PaperTrading />} />
                    <Route path="/research" element={<ResearchNotebook />} />
                  </Route>
                </Route>
              </Routes>
            </Suspense>
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
