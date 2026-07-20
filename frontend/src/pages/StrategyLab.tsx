import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { runBacktest, submitBacktestJob, fetchBacktestJob, fetchBacktestHistory } from "../api/client";
import type { BacktestResult, BacktestJobDetail, BacktestHistoryItem } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import StatCard from "../components/StatCard";

export default function StrategyLab() {
  const { token } = useAuth();
  const { push } = useToast();
  const [params] = useSearchParams();
  const [tickerA, setTickerA] = useState(params.get("a") || "V");
  const [tickerB, setTickerB] = useState(params.get("b") || "MA");
  const [capital, setCapital] = useState(100000);
  const [entryThreshold, setEntryThreshold] = useState(2.0);
  const [exitThreshold, setExitThreshold] = useState(0.5);
  const [stopLoss, setStopLoss] = useState(3.5);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [job, setJob] = useState<BacktestJobDetail | null>(null);
  const [submittingJob, setSubmittingJob] = useState(false);
  const pollRef = useRef<number | null>(null);

  const [history, setHistory] = useState<BacktestHistoryItem[]>([]);
  const loadHistory = () => { if (token) fetchBacktestHistory().then(setHistory).catch(() => {}); };
  useEffect(loadHistory, [token]);

  const handleRun = () => {
    setLoading(true);
    setError(null);
    runBacktest({
      ticker_a: tickerA, ticker_b: tickerB, capital,
      entry_threshold: entryThreshold, exit_threshold: exitThreshold, stop_loss_z: stopLoss,
    })
      .then(setResult)
      .catch(() => setError("Backtest failed. Check tickers and try again."))
      .finally(() => setLoading(false));
  };

  const handleRunInBackground = async () => {
    setSubmittingJob(true);
    setError(null);
    setJob(null);
    try {
      const submitted = await submitBacktestJob({
        ticker_a: tickerA, ticker_b: tickerB, capital,
        entry_threshold: entryThreshold, exit_threshold: exitThreshold, stop_loss_z: stopLoss,
      });
      pollJob(submitted.job_id);
    } catch {
      setError("Could not submit background job. Are you signed in?");
    } finally {
      setSubmittingJob(false);
    }
  };

  const pollJob = (jobId: number) => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    const tick = async () => {
      const detail = await fetchBacktestJob(jobId);
      setJob(detail);
      if (detail.status === "SUCCESS" || detail.status === "FAILED") {
        if (pollRef.current) window.clearInterval(pollRef.current);
        loadHistory();
        if (detail.status === "SUCCESS" && detail.metrics) {
          push({
            variant: "success",
            title: `Backtest complete: ${detail.ticker_a}/${detail.ticker_b}`,
            description: `Sharpe ${detail.metrics.sharpe_ratio.toFixed(2)} · ${detail.metrics.total_return_pct}% return`,
          });
        } else if (detail.status === "FAILED") {
          push({ variant: "error", title: "Backtest job failed", description: detail.error ?? undefined });
        }
      }
    };
    tick();
    pollRef.current = window.setInterval(tick, 2000);
  };

  useEffect(() => () => { if (pollRef.current) window.clearInterval(pollRef.current); }, []);

  const equityChart = result?.dates.map((d, i) => ({ date: d, equity: result.equity_curve[i] })) || [];
  const jobEquityChart = job?.equity_curve?.map((v, i) => ({ date: String(i), equity: v })) || [];

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-semibold text-white mb-1">Strategy Lab</h1>
      <p className="text-gray-500 text-sm mb-6">Configure and backtest a pairs mean-reversion strategy</p>

      <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5 mb-6">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-4">
          <Field label="Ticker A" value={tickerA} onChange={(v) => setTickerA(v.toUpperCase())} />
          <Field label="Ticker B" value={tickerB} onChange={(v) => setTickerB(v.toUpperCase())} />
          <Field label="Capital ($)" value={String(capital)} onChange={(v) => setCapital(Number(v) || 0)} type="number" />
          <Field label="Entry Z" value={String(entryThreshold)} onChange={(v) => setEntryThreshold(Number(v))} type="number" step="0.1" />
          <Field label="Exit Z" value={String(exitThreshold)} onChange={(v) => setExitThreshold(Number(v))} type="number" step="0.1" />
          <Field label="Stop Loss Z" value={String(stopLoss)} onChange={(v) => setStopLoss(Number(v))} type="number" step="0.1" />
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRun}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded"
          >
            {loading ? "Running backtest…" : "Run Backtest"}
          </button>
          {token && (
            <button
              onClick={handleRunInBackground}
              disabled={submittingJob}
              className="bg-[#0d1017] border border-[#232838] hover:border-blue-500 disabled:opacity-50 text-gray-300 text-sm px-4 py-2 rounded"
              title="Queues the backtest as a background job via Celery instead of blocking this request"
            >
              {submittingJob ? "Submitting…" : "Run in Background ⚙"}
            </button>
          )}
        </div>
        {error && <div className="text-red-400 text-sm mt-3">{error}</div>}
      </div>

      {job && (
        <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-white font-medium">
              Background Job — {job.ticker_a}/{job.ticker_b}
            </h2>
            <span className={`text-xs px-2 py-1 rounded ${
              job.status === "SUCCESS" ? "bg-green-500/15 text-green-400"
              : job.status === "FAILED" ? "bg-red-500/15 text-red-400"
              : "bg-amber-500/15 text-amber-400"
            }`}>
              {job.status === "PENDING" || job.status === "RUNNING" ? `${job.status}…` : job.status}
            </span>
          </div>
          {job.error && <div className="text-red-400 text-xs mb-3">{job.error}</div>}
          {job.status === "SUCCESS" && job.metrics && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <StatCard label="Total Return" value={`${job.metrics.total_return_pct}%`} positive={job.metrics.total_return_pct > 0} negative={job.metrics.total_return_pct < 0} />
                <StatCard label="Sharpe Ratio" value={job.metrics.sharpe_ratio.toFixed(2)} positive={job.metrics.sharpe_ratio > 1} />
                <StatCard label="Max Drawdown" value={`${job.metrics.max_drawdown_pct}%`} negative />
                <StatCard label="# Trades" value={String(job.metrics.num_trades)} />
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={jobEquityChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#232838" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b7280" }} minTickGap={60} />
                  <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} domain={["auto", "auto"]} />
                  <Tooltip contentStyle={{ background: "#12151f", border: "1px solid #232838" }} />
                  <Line type="monotone" dataKey="equity" stroke="#22c55e" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </>
          )}
          {(job.status === "PENDING" || job.status === "RUNNING") && (
            <div className="text-xs text-gray-500">Polling for updates every 2s…</div>
          )}
        </div>
      )}

      {result && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatCard label="Total Return" value={`${result.metrics.total_return_pct}%`} positive={result.metrics.total_return_pct > 0} negative={result.metrics.total_return_pct < 0} />
            <StatCard label="Sharpe Ratio" value={result.metrics.sharpe_ratio.toFixed(2)} positive={result.metrics.sharpe_ratio > 1} />
            <StatCard label="Sortino Ratio" value={result.metrics.sortino_ratio.toFixed(2)} />
            <StatCard label="Max Drawdown" value={`${result.metrics.max_drawdown_pct}%`} negative />
            <StatCard label="Win Rate" value={`${result.metrics.win_rate_pct}%`} />
            <StatCard label="# Trades" value={String(result.metrics.num_trades)} />
            <StatCard label="Annual Return" value={`${result.metrics.annual_return_pct}%`} positive={result.metrics.annual_return_pct > 0} negative={result.metrics.annual_return_pct < 0} />
            <StatCard label="Final Equity" value={`$${result.metrics.final_equity.toLocaleString()}`} />
          </div>

          <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5 mb-6">
            <h2 className="text-white font-medium mb-4">Equity Curve</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={equityChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#232838" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b7280" }} minTickGap={60} />
                <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "#12151f", border: "1px solid #232838" }} />
                <Line type="monotone" dataKey="equity" stroke="#22c55e" dot={false} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {token && history.length > 0 && (
        <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5">
          <h2 className="text-white font-medium mb-3">Backtest History</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-[#232838]">
                <th className="pb-2 font-normal">Pair</th>
                <th className="pb-2 font-normal">Status</th>
                <th className="pb-2 font-normal">Sharpe</th>
                <th className="pb-2 font-normal">Total Return</th>
                <th className="pb-2 font-normal">Run At</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.job_id} className="border-b border-[#1a1f2e]">
                  <td className="py-2 text-gray-300">{h.pair}</td>
                  <td className="py-2 text-gray-400">{h.status}</td>
                  <td className="py-2 text-gray-400">{h.metrics?.sharpe_ratio ?? "—"}</td>
                  <td className={`py-2 ${(h.metrics?.total_return_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {h.metrics ? `${h.metrics.total_return_pct}%` : "—"}
                  </td>
                  <td className="py-2 text-gray-500 text-xs">{new Date(h.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange, type = "text", step }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; step?: string;
}) {
  return (
    <div>
      <label className="text-xs text-gray-500 block mb-1">{label}</label>
      <input
        type={type}
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-[#0d1017] border border-[#232838] rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
      />
    </div>
  );
}
