import { useState } from "react";
import { fetchRiskReport, fetchOptimizer } from "../api/client";
import StatCard from "../components/StatCard";

interface Position { ticker: string; market_value: number }
interface Opportunity { pair: string; expected_return: number; volatility: number }

const DEFAULT_POSITIONS: Position[] = [
  { ticker: "AAPL", market_value: 30000 },
  { ticker: "MSFT", market_value: 25000 },
  { ticker: "V", market_value: 20000 },
  { ticker: "XOM", market_value: 15000 },
  { ticker: "KO", market_value: 10000 },
];

const DEFAULT_OPPORTUNITIES: Opportunity[] = [
  { pair: "V/MA", expected_return: 0.023, volatility: 0.04 },
  { pair: "AAPL/MSFT", expected_return: 0.018, volatility: 0.03 },
  { pair: "XOM/CVX", expected_return: 0.015, volatility: 0.05 },
  { pair: "KO/PEP", expected_return: 0.012, volatility: 0.025 },
];

export default function RiskPortfolio() {
  const [positions] = useState<Position[]>(DEFAULT_POSITIONS);
  const [opportunities] = useState<Opportunity[]>(DEFAULT_OPPORTUNITIES);
  const [riskReport, setRiskReport] = useState<any>(null);
  const [allocation, setAllocation] = useState<any>(null);
  const [method, setMethod] = useState("mean_variance");
  const [loading, setLoading] = useState(false);

  const runAnalysis = () => {
    setLoading(true);
    Promise.all([
      fetchRiskReport(positions),
      fetchOptimizer(opportunities, 100000, method),
    ])
      .then(([risk, opt]) => {
        setRiskReport(risk);
        setAllocation(opt);
      })
      .finally(() => setLoading(false));
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-semibold text-white mb-1">Risk & Portfolio</h1>
      <p className="text-gray-500 text-sm mb-6">Sample portfolio risk analysis and capital allocation across opportunities</p>

      <div className="grid md:grid-cols-2 gap-6 mb-6">
        <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5">
          <h2 className="text-white font-medium mb-3">Sample Positions</h2>
          <table className="w-full text-sm">
            <tbody>
              {positions.map((p) => (
                <tr key={p.ticker} className="border-b border-[#1a1f2e]">
                  <td className="py-1.5 text-gray-300">{p.ticker}</td>
                  <td className="py-1.5 text-right text-gray-400">${p.market_value.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5">
          <h2 className="text-white font-medium mb-3">Optimizer Method</h2>
          <div className="flex gap-2 mb-4">
            {["mean_variance", "risk_parity"].map((m) => (
              <button
                key={m}
                onClick={() => setMethod(m)}
                className={`text-xs px-3 py-1.5 rounded ${
                  method === m ? "bg-blue-600 text-white" : "bg-[#0d1017] text-gray-400 border border-[#232838]"
                }`}
              >
                {m === "mean_variance" ? "Mean-Variance" : "Risk Parity"}
              </button>
            ))}
          </div>
          <button
            onClick={runAnalysis}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded"
          >
            {loading ? "Analyzing…" : "Run Risk & Optimizer Analysis"}
          </button>
        </div>
      </div>

      {riskReport && (
        <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5 mb-6">
          <h2 className="text-white font-medium mb-4">Risk Report</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <StatCard label="Portfolio Value" value={`$${riskReport.total_market_value.toLocaleString()}`} />
            <StatCard label="VaR (95%)" value={`${riskReport.value_at_risk_95_pct}%`} negative />
            <StatCard label="CVaR (95%)" value={`${riskReport.conditional_var_95_pct}%`} negative />
            <StatCard label="Max Drawdown" value={`${riskReport.max_drawdown_pct}%`} negative />
          </div>
          <div className="mb-4">
            <div className="text-xs text-gray-500 mb-2">Sector Exposure</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(riskReport.sector_exposure_pct).map(([sector, pct]: any) => (
                <span key={sector} className="text-xs bg-[#0d1017] border border-[#232838] rounded px-2 py-1 text-gray-300">
                  {sector}: {pct}%
                </span>
              ))}
            </div>
          </div>
          {riskReport.warnings?.length > 0 && (
            <div className="space-y-1">
              {riskReport.warnings.map((w: string, i: number) => (
                <div key={i} className="text-xs bg-red-500/10 text-red-400 border border-red-500/20 rounded px-3 py-2">
                  {w}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {allocation && (
        <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5">
          <h2 className="text-white font-medium mb-4">Optimized Capital Allocation ({allocation.method})</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-[#232838]">
                <th className="pb-2 font-normal">Opportunity</th>
                <th className="pb-2 font-normal">Weight</th>
                <th className="pb-2 font-normal">Capital Allocated</th>
                <th className="pb-2 font-normal">Expected Return</th>
              </tr>
            </thead>
            <tbody>
              {allocation.allocations.map((a: any) => (
                <tr key={a.pair} className="border-b border-[#1a1f2e]">
                  <td className="py-2 text-gray-300">{a.pair}</td>
                  <td className="py-2 text-gray-400">{a.weight_pct}%</td>
                  <td className="py-2 text-gray-400">${a.capital_allocated.toLocaleString()}</td>
                  <td className="py-2 text-green-400">+{a.expected_return_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
