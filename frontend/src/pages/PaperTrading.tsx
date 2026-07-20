import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchPortfolio, openPaperTrade, closePaperTrade } from "../api/client";
import { useLiveScanner } from "../hooks/useLiveScanner";
import { useToast } from "../components/Toast";
import StatCard from "../components/StatCard";

export default function PaperTrading() {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [liveMode, setLiveMode] = useState(false);
  const [tickerA, setTickerA] = useState("V");
  const [tickerB, setTickerB] = useState("MA");
  const [capital, setCapital] = useState(10000);
  const [formError, setFormError] = useState<string | null>(null);

  const { opportunities, connected, lastUpdate } = useLiveScanner(liveMode);

  const { data: portfolio, isLoading } = useQuery({
    queryKey: ["portfolio"],
    queryFn: fetchPortfolio,
    // Portfolio PnL is mark-to-market against live prices, so keep it fresher than
    // the default cache policy -- especially important while "Go Live" is on.
    staleTime: 5_000,
    refetchInterval: liveMode ? 15_000 : false,
  });

  const openMutation = useMutation({
    mutationFn: () => openPaperTrade(tickerA.toUpperCase(), tickerB.toUpperCase(), capital),
    onSuccess: (data) => {
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      push({
        variant: "info",
        title: `Position opened: ${data.pair}`,
        description: `${data.direction.replace("_", " ")} · entry z-score ${data.entry_z}`,
      });
    },
    onError: (e: any) => {
      setFormError(e?.response?.data?.detail || "Could not open trade.");
    },
  });

  const closeMutation = useMutation({
    mutationFn: (tradeId: number) => closePaperTrade(tradeId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      const won = (data.pnl ?? 0) >= 0;
      push({
        variant: won ? "success" : "error",
        title: won ? `🎉 Trade closed: +$${data.pnl?.toLocaleString()}` : `Trade closed: $${data.pnl?.toLocaleString()}`,
        description: won ? "Nice — that spread reverted in your favor." : "Not every trade wins — that's why sizing matters.",
      });
    },
  });

  // Surface a one-time nudge (not a repeating toast) when a live position crosses
  // into "suggest close" territory, so the signal isn't easy to miss in the table.
  const [nudgedIds, setNudgedIds] = useState<Set<number>>(new Set());
  useEffect(() => {
    if (!portfolio) return;
    for (const p of portfolio.open_positions) {
      if (p.suggest_close && !nudgedIds.has(p.id)) {
        push({ variant: "info", title: `${p.pair} looks ready to close`, description: "Z-score has reverted toward the exit threshold." });
        setNudgedIds((prev) => new Set(prev).add(p.id));
      }
    }
  }, [portfolio, nudgedIds, push]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-semibold text-white">Paper Trading</h1>
      </div>
      <p className="text-gray-500 text-sm mb-6">Simulated positions — no real money involved</p>

      {isLoading && <div className="text-gray-500 text-sm py-8">Loading portfolio…</div>}

      {portfolio && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard label="Equity" value={`$${portfolio.equity.toLocaleString()}`} />
          <StatCard
            label="Unrealized PnL"
            value={`${portfolio.unrealized_pnl >= 0 ? "+" : ""}$${portfolio.unrealized_pnl.toLocaleString()}`}
            positive={portfolio.unrealized_pnl > 0}
            negative={portfolio.unrealized_pnl < 0}
          />
          <StatCard
            label="Realized PnL"
            value={`${portfolio.realized_pnl >= 0 ? "+" : ""}$${portfolio.realized_pnl.toLocaleString()}`}
            positive={portfolio.realized_pnl > 0}
            negative={portfolio.realized_pnl < 0}
          />
          <StatCard label="Open Positions" value={String(portfolio.open_positions.length)} />
        </div>
      )}

      <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5 mb-6">
        <h2 className="text-white font-medium mb-3">Open New Position</h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Ticker A</label>
            <input value={tickerA} onChange={(e) => setTickerA(e.target.value)} className="bg-[#0d1017] border border-[#232838] rounded px-2 py-1.5 text-sm w-24" />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Ticker B</label>
            <input value={tickerB} onChange={(e) => setTickerB(e.target.value)} className="bg-[#0d1017] border border-[#232838] rounded px-2 py-1.5 text-sm w-24" />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Capital ($)</label>
            <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value))} className="bg-[#0d1017] border border-[#232838] rounded px-2 py-1.5 text-sm w-32" />
          </div>
          <button
            onClick={() => openMutation.mutate()}
            disabled={openMutation.isPending}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded"
          >
            {openMutation.isPending ? "Opening…" : "Open Position"}
          </button>
        </div>
        {formError && <div className="text-red-400 text-xs mt-3">{formError}</div>}
      </div>

      <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-white font-medium">Open Positions</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-[#232838]">
              <th className="pb-2 font-normal">Pair</th>
              <th className="pb-2 font-normal">Direction</th>
              <th className="pb-2 font-normal">Entry Z → Current Z</th>
              <th className="pb-2 font-normal">Unrealized PnL</th>
              <th className="pb-2 font-normal"></th>
            </tr>
          </thead>
          <tbody>
            {portfolio?.open_positions.map((p) => (
              <tr key={p.id} className="border-b border-[#1a1f2e]">
                <td className="py-2 text-gray-300">{p.pair}</td>
                <td className="py-2 text-gray-400">{p.direction.replace("_", " ")}</td>
                <td className="py-2 text-gray-400">
                  {p.entry_z.toFixed(2)} → {p.current_z?.toFixed(2) ?? "—"}
                  {p.suggest_close && <span className="ml-2 text-xs text-amber-400">suggest close</span>}
                </td>
                <td className={`py-2 ${p.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"} animate-value-flash`}>
                  {p.unrealized_pnl >= 0 ? "+" : ""}${p.unrealized_pnl.toLocaleString()}
                </td>
                <td className="py-2 text-right">
                  <button
                    onClick={() => closeMutation.mutate(p.id)}
                    disabled={closeMutation.isPending}
                    className="text-xs text-blue-400 hover:underline disabled:opacity-50"
                  >
                    Close
                  </button>
                </td>
              </tr>
            ))}
            {portfolio?.open_positions.length === 0 && (
              <tr><td colSpan={5} className="text-center text-gray-500 py-6">No open positions</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-white font-medium">Live Monitoring</h2>
          <button
            onClick={() => setLiveMode(!liveMode)}
            className={`text-xs px-3 py-1.5 rounded ${liveMode ? "bg-green-600 text-white" : "bg-[#0d1017] text-gray-400 border border-[#232838]"}`}
          >
            {liveMode ? "● Live" : "Go Live"}
          </button>
        </div>
        {liveMode && (
          <div className="text-xs text-gray-500 mb-3">
            {connected ? "Connected" : "Connecting…"}
            {lastUpdate && ` · last update ${lastUpdate.toLocaleTimeString()}`}
          </div>
        )}
        {liveMode && opportunities.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-[#232838]">
                <th className="pb-2 font-normal">Pair</th>
                <th className="pb-2 font-normal">Signal</th>
                <th className="pb-2 font-normal">Confidence</th>
                <th className="pb-2 font-normal">Z-score</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.slice(0, 8).map((o) => (
                <tr key={o.pair} className="border-b border-[#1a1f2e]">
                  <td className="py-2 text-gray-300">{o.pair}</td>
                  <td className={`py-2 ${o.signal === "BUY" ? "text-green-400" : "text-red-400"}`}>{o.signal}</td>
                  <td className="py-2 text-gray-400">{o.confidence}%</td>
                  <td className="py-2 text-gray-400">{o.latest_zscore.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!liveMode && <div className="text-xs text-gray-500">Toggle on to stream live scanner updates via WebSocket every 15s.</div>}
      </div>
    </div>
  );
}
