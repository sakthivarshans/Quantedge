import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchScanner } from "../api/client";
import StatCard from "../components/StatCard";
import GradientHero from "../components/GradientHero";
import { useAuth } from "../auth/AuthContext";

export default function Dashboard() {
  const { name, email } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["scanner", 6],
    queryFn: () => fetchScanner(6),
  });
  const opportunities = data?.opportunities ?? [];

  return (
    <div>
      <GradientHero className="px-8 pt-10 pb-8" overlayFade={false}>
        <div className="max-w-7xl mx-auto">
          <div className="text-blue-400 text-xs font-medium tracking-wide mb-2">DASHBOARD</div>
          <h1 className="text-white font-semibold text-3xl sm:text-4xl tracking-tight mb-1">
            {name ? `Welcome back, ${name.split(" ")[0]}` : email ? `Welcome back` : "Portfolio overview"}
          </h1>
          <p className="text-gray-400 text-sm mb-8">Today's opportunities and portfolio snapshot</p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Portfolio Value" value="$100,000" sub="paper trading" />
            <StatCard label="Today's PnL" value="+$0.00" sub="no open positions" />
            <StatCard label="Sharpe Ratio" value="—" sub="run a backtest" />
            <StatCard label="Risk Score" value="Low" positive sub="no open exposure" />
          </div>
        </div>
      </GradientHero>

      <div className="p-8 max-w-7xl mx-auto">
        <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-medium">Top Arbitrage Opportunities</h2>
            <Link to="/scanner" className="text-xs text-blue-400 hover:text-blue-300">
              View full scanner →
            </Link>
          </div>

          {isLoading && <div className="text-gray-500 text-sm py-8 text-center">Scanning market…</div>}
          {error && <div className="text-red-400 text-sm py-8 text-center">Could not reach the QuantEdge API. Is the backend running on :8000?</div>}

          {!isLoading && !error && (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b border-[#232838]">
                  <th className="pb-2 font-normal">Pair</th>
                  <th className="pb-2 font-normal">Signal</th>
                  <th className="pb-2 font-normal">Confidence</th>
                  <th className="pb-2 font-normal">Expected Return</th>
                  <th className="pb-2 font-normal">Half-life</th>
                </tr>
              </thead>
              <tbody>
                {opportunities.map((o) => (
                  <tr key={o.pair} className="border-b border-[#1a1f2e] hover:bg-[#151b28]">
                    <td className="py-3">
                      <Link to={`/pairs/${o.ticker_a}/${o.ticker_b}`} className="text-blue-400 hover:underline">
                        {o.pair}
                      </Link>
                    </td>
                    <td className="py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          o.signal === "BUY"
                            ? "bg-green-500/15 text-green-400"
                            : "bg-red-500/15 text-red-400"
                        }`}
                      >
                        {o.signal}
                      </span>
                    </td>
                    <td className="py-3">{o.confidence}%</td>
                    <td className="py-3 text-green-400">+{o.expected_return_pct}%</td>
                    <td className="py-3 text-gray-400">{o.half_life_days ? `${o.half_life_days}d` : "—"}</td>
                  </tr>
                ))}
                {opportunities.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center text-gray-500 py-8">
                      No significant opportunities detected right now.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
