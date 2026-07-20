import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchScanner } from "../api/client";

export default function Scanner() {
  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["scanner", 30],
    queryFn: () => fetchScanner(30),
  });

  const opportunities = data?.opportunities ?? [];
  const universeSize = data?.universe_size ?? 0;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-semibold text-white">Market Scanner</h1>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-3 py-1.5 rounded"
        >
          {isFetching ? "Scanning…" : "Re-scan"}
        </button>
      </div>
      <p className="text-gray-500 text-sm mb-6">
        Scanning {universeSize} tickers for statistically significant pricing relationships
      </p>

      {isLoading && <div className="text-gray-500 text-sm py-16 text-center">Running cointegration analysis across pairs…</div>}
      {error && <div className="text-red-400 text-sm py-16 text-center">Could not reach the QuantEdge API.</div>}

      {!isLoading && !error && (
        <div className="bg-[#12151f] border border-[#232838] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 bg-[#0d1017] border-b border-[#232838]">
                <th className="px-4 py-3 font-normal">Pair</th>
                <th className="px-4 py-3 font-normal">Signal</th>
                <th className="px-4 py-3 font-normal">Confidence</th>
                <th className="px-4 py-3 font-normal">Correlation</th>
                <th className="px-4 py-3 font-normal">Coint. p-value</th>
                <th className="px-4 py-3 font-normal">Z-score</th>
                <th className="px-4 py-3 font-normal">Half-life</th>
                <th className="px-4 py-3 font-normal">Exp. Return</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.map((o) => (
                <tr key={o.pair} className="border-b border-[#1a1f2e] hover:bg-[#151b28]">
                  <td className="px-4 py-3">
                    <Link to={`/pairs/${o.ticker_a}/${o.ticker_b}`} className="text-blue-400 hover:underline font-medium">
                      {o.pair}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        o.signal === "BUY" ? "bg-green-500/15 text-green-400" : "bg-red-500/15 text-red-400"
                      }`}
                    >
                      {o.signal}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-[#232838] rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500" style={{ width: `${o.confidence}%` }} />
                      </div>
                      <span className="text-gray-400 text-xs">{o.confidence}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-400">{o.correlation.toFixed(2)}</td>
                  <td className="px-4 py-3 text-gray-400">{o.cointegration_pvalue.toExponential(2)}</td>
                  <td className="px-4 py-3 text-gray-400">{o.latest_zscore.toFixed(2)}</td>
                  <td className="px-4 py-3 text-gray-400">{o.half_life_days ? `${o.half_life_days}d` : "—"}</td>
                  <td className="px-4 py-3 text-green-400">+{o.expected_return_pct}%</td>
                </tr>
              ))}
              {opportunities.length === 0 && (
                <tr>
                  <td colSpan={8} className="text-center text-gray-500 py-10">
                    No significant opportunities detected right now.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
