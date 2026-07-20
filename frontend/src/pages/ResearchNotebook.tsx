import { useEffect, useState } from "react";
import {
  runCell, listSessions, saveSession, updateSession, loadSession, deleteSession,
} from "../api/client";
import type { NotebookCell } from "../api/client";

const CELL_TYPES = [
  { value: "correlation_matrix", label: "Correlation Matrix" },
  { value: "pair_diagnostics", label: "Pair Diagnostics" },
  { value: "rolling_stats", label: "Rolling Volatility & Return" },
  { value: "beta_exposure", label: "Beta Exposure" },
];

function newCell(type: string): NotebookCell {
  const defaults: Record<string, any> = {
    correlation_matrix: { tickers: "AAPL,MSFT,GOOG,V,MA" },
    pair_diagnostics: { ticker_a: "V", ticker_b: "MA" },
    rolling_stats: { tickers: "AAPL,MSFT", window: 30 },
    beta_exposure: { tickers: "MSFT,V,XOM", benchmark: "AAPL" },
  };
  return { id: crypto.randomUUID(), type, params: defaults[type] };
}

export default function ResearchNotebook() {
  const [cells, setCells] = useState<NotebookCell[]>([newCell("correlation_matrix")]);
  const [sessionName, setSessionName] = useState("Untitled Session");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [sessions, setSessions] = useState<{ id: number; name: string; num_cells: number; updated_at: string }[]>([]);
  const [showSessions, setShowSessions] = useState(false);

  const refreshSessions = () => listSessions().then(setSessions).catch(() => {});
  useEffect(() => { refreshSessions(); }, []);

  const addCell = (type: string) => setCells([...cells, newCell(type)]);

  const updateCellParams = (id: string, params: Record<string, any>) => {
    setCells(cells.map((c) => (c.id === id ? { ...c, params } : c)));
  };

  const removeCell = (id: string) => setCells(cells.filter((c) => c.id !== id));

  const runOneCell = async (cell: NotebookCell) => {
    setCells((prev) => prev.map((c) => (c.id === cell.id ? { ...c, result: undefined, error: undefined } : c)));
    try {
      const params = normalizeParams(cell.type, cell.params);
      const result = await runCell(cell.type, params);
      setCells((prev) => prev.map((c) => (c.id === cell.id ? { ...c, result } : c)));
    } catch (e: any) {
      setCells((prev) => prev.map((c) => (c.id === cell.id ? { ...c, error: e?.response?.data?.detail || "Failed to run cell" } : c)));
    }
  };

  const handleSave = async () => {
    if (sessionId) {
      await updateSession(sessionId, sessionName, cells);
    } else {
      const res = await saveSession(sessionName, cells);
      setSessionId(res.id);
    }
    refreshSessions();
  };

  const handleLoad = async (id: number) => {
    const res = await loadSession(id);
    setSessionId(res.id);
    setSessionName(res.name);
    setCells(res.cells.length ? res.cells : [newCell("correlation_matrix")]);
    setShowSessions(false);
  };

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteSession(id);
    if (id === sessionId) { setSessionId(null); }
    refreshSessions();
  };

  const handleNew = () => {
    setSessionId(null);
    setSessionName("Untitled Session");
    setCells([newCell("correlation_matrix")]);
    setShowSessions(false);
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-semibold text-white">Research Notebook</h1>
        <div className="flex items-center gap-2">
          <button onClick={handleNew} className="text-xs text-gray-400 hover:text-gray-200 border border-[#232838] rounded px-3 py-1.5">
            New
          </button>
          <div className="relative">
            <button onClick={() => setShowSessions(!showSessions)} className="text-xs text-gray-400 hover:text-gray-200 border border-[#232838] rounded px-3 py-1.5">
              Sessions ({sessions.length})
            </button>
            {showSessions && (
              <div className="absolute right-0 mt-1 w-64 bg-[#12151f] border border-[#232838] rounded-lg shadow-lg z-10 max-h-80 overflow-y-auto">
                {sessions.length === 0 && <div className="p-3 text-xs text-gray-500">No saved sessions yet</div>}
                {sessions.map((s) => (
                  <div
                    key={s.id}
                    onClick={() => handleLoad(s.id)}
                    className="flex items-center justify-between px-3 py-2 text-xs hover:bg-[#151b28] cursor-pointer border-b border-[#1a1f2e] last:border-0"
                  >
                    <div>
                      <div className="text-gray-300">{s.name}</div>
                      <div className="text-gray-600">{s.num_cells} cells</div>
                    </div>
                    <button onClick={(e) => handleDelete(s.id, e)} className="text-red-400 hover:underline">del</button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button onClick={handleSave} className="text-xs bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-1.5">
            Save
          </button>
        </div>
      </div>

      <input
        value={sessionName}
        onChange={(e) => setSessionName(e.target.value)}
        className="bg-transparent text-gray-400 text-sm mb-6 border-none focus:outline-none focus:text-white"
      />

      <div className="space-y-4 mb-6">
        {cells.map((cell) => (
          <Cell
            key={cell.id}
            cell={cell}
            onParamsChange={(p) => updateCellParams(cell.id, p)}
            onRun={() => runOneCell(cell)}
            onRemove={() => removeCell(cell.id)}
          />
        ))}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-gray-500">Add cell:</span>
        {CELL_TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => addCell(t.value)}
            className="text-xs bg-[#12151f] border border-[#232838] hover:border-blue-500 text-gray-300 rounded px-3 py-1.5"
          >
            + {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function normalizeParams(_type: string, params: Record<string, any>): Record<string, any> {
  const p = { ...params };
  if (typeof p.tickers === "string") {
    p.tickers = p.tickers.split(",").map((t: string) => t.trim().toUpperCase()).filter(Boolean);
  }
  if (p.ticker_a) p.ticker_a = p.ticker_a.toUpperCase();
  if (p.ticker_b) p.ticker_b = p.ticker_b.toUpperCase();
  if (p.benchmark) p.benchmark = p.benchmark.toUpperCase();
  if (p.window) p.window = Number(p.window);
  return p;
}

function Cell({ cell, onParamsChange, onRun, onRemove }: {
  cell: NotebookCell; onParamsChange: (p: Record<string, any>) => void; onRun: () => void; onRemove: () => void;
}) {
  const [running, setRunning] = useState(false);
  const label = CELL_TYPES.find((t) => t.value === cell.type)?.label || cell.type;

  const handleRun = async () => {
    setRunning(true);
    await onRun();
    setRunning(false);
  };

  return (
    <div className="bg-[#12151f] border border-[#232838] rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-gray-500 uppercase tracking-wide">{label}</span>
        <div className="flex items-center gap-2">
          <button onClick={handleRun} disabled={running} className="text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded px-3 py-1">
            {running ? "Running…" : "Run ▶"}
          </button>
          <button onClick={onRemove} className="text-xs text-gray-600 hover:text-red-400">✕</button>
        </div>
      </div>

      <CellParamsForm type={cell.type} params={cell.params} onChange={onParamsChange} />

      {cell.error && <div className="text-red-400 text-xs mt-3">{cell.error}</div>}
      {cell.result && <div className="mt-4 pt-4 border-t border-[#1a1f2e]"><CellResult type={cell.type} result={cell.result} /></div>}
    </div>
  );
}

function CellParamsForm({ type, params, onChange }: { type: string; params: Record<string, any>; onChange: (p: Record<string, any>) => void }) {
  const field = (key: string, label: string, width = "w-40") => (
    <div key={key}>
      <label className="text-xs text-gray-500 block mb-1">{label}</label>
      <input
        value={params[key] ?? ""}
        onChange={(e) => onChange({ ...params, [key]: e.target.value })}
        className={`bg-[#0d1017] border border-[#232838] rounded px-2 py-1.5 text-sm text-gray-200 ${width}`}
      />
    </div>
  );

  if (type === "correlation_matrix") return <div className="flex gap-3">{field("tickers", "Tickers (comma-separated)", "w-96")}</div>;
  if (type === "pair_diagnostics") return <div className="flex gap-3">{field("ticker_a", "Ticker A")}{field("ticker_b", "Ticker B")}</div>;
  if (type === "rolling_stats") return <div className="flex gap-3">{field("tickers", "Tickers (comma-separated)", "w-64")}{field("window", "Window (days)", "w-28")}</div>;
  if (type === "beta_exposure") return <div className="flex gap-3">{field("tickers", "Tickers (comma-separated)", "w-64")}{field("benchmark", "Benchmark")}</div>;
  return null;
}

function CellResult({ type, result }: { type: string; result: any }) {
  if (type === "correlation_matrix") {
    return (
      <table className="text-xs">
        <thead>
          <tr>
            <th></th>
            {result.tickers.map((t: string) => <th key={t} className="px-2 py-1 text-gray-500">{t}</th>)}
          </tr>
        </thead>
        <tbody>
          {result.matrix.map((row: number[], i: number) => (
            <tr key={i}>
              <td className="px-2 py-1 text-gray-500">{result.tickers[i]}</td>
              {row.map((v, j) => (
                <td key={j} className="px-2 py-1 text-center" style={{ color: v > 0.5 ? "#22c55e" : v < -0.2 ? "#ef4444" : "#9ca3af" }}>
                  {v.toFixed(2)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  if (type === "pair_diagnostics") {
    return (
      <div className="text-sm space-y-1">
        <div className="text-gray-300">Signal: <span className={result.signal === "BUY" ? "text-green-400" : result.signal === "SELL" ? "text-red-400" : "text-gray-400"}>{result.signal}</span> ({result.confidence}%)</div>
        <div className="text-gray-400">Correlation: {result.correlation}</div>
        <div className="text-gray-400">Cointegration p-value: {result.cointegration.p_value.toExponential(2)}</div>
        <div className="text-gray-400">Hedge ratio: {result.hedge_ratio}</div>
        <div className="text-gray-400">Half-life: {result.half_life_days ? `${result.half_life_days}d` : "—"}</div>
        <div className="text-gray-400">Latest z-score: {result.latest_zscore}</div>
      </div>
    );
  }

  if (type === "rolling_stats") {
    return (
      <table className="text-xs w-full">
        <thead>
          <tr className="text-gray-500 text-left">
            <th className="pb-1">Ticker</th><th className="pb-1">Latest Ann. Vol</th><th className="pb-1">Latest Ann. Return</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(result.series).map(([ticker, s]: any) => (
            <tr key={ticker}>
              <td className="py-1 text-gray-300">{ticker}</td>
              <td className="py-1 text-gray-400">{(s.latest_volatility * 100).toFixed(1)}%</td>
              <td className={`py-1 ${s.latest_return >= 0 ? "text-green-400" : "text-red-400"}`}>{(s.latest_return * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  if (type === "beta_exposure") {
    return (
      <table className="text-xs w-full">
        <thead>
          <tr className="text-gray-500 text-left">
            <th className="pb-1">Ticker</th><th className="pb-1">Beta vs {result.benchmark}</th><th className="pb-1">Correlation</th>
          </tr>
        </thead>
        <tbody>
          {result.exposures.map((e: any) => (
            <tr key={e.ticker}>
              <td className="py-1 text-gray-300">{e.ticker}</td>
              <td className="py-1 text-gray-400">{e.beta}</td>
              <td className="py-1 text-gray-400">{e.correlation}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  return <pre className="text-xs text-gray-500">{JSON.stringify(result, null, 2)}</pre>;
}
