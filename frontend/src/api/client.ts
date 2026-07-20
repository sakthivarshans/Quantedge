import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "/api";

export const api = axios.create({ baseURL: BASE_URL });

export interface Opportunity {
  pair: string;
  ticker_a: string;
  ticker_b: string;
  signal: "BUY" | "SELL" | "HOLD";
  confidence: number;
  correlation: number;
  cointegration_pvalue: number;
  half_life_days: number | null;
  latest_zscore: number;
  expected_return_pct: number;
}

export interface ScannerResponse {
  universe_size: number;
  opportunities: Opportunity[];
}

export interface PairDetail {
  ticker_a: string;
  ticker_b: string;
  dates: string[];
  price_a: number[];
  price_b: number[];
  correlation: number;
  hedge_ratio: number;
  cointegration: { coint_stat: number; p_value: number; crit_1pct: number; crit_5pct: number; crit_10pct: number };
  adf_on_spread: { adf_stat: number; p_value: number; crit_1pct: number; crit_5pct: number; crit_10pct: number };
  half_life_days: number | null;
  latest_zscore: number;
  spread: number[];
  zscore_series: number[];
  signal: string;
  confidence: number;
}

export interface BacktestResult {
  hedge_ratio: number;
  metrics: {
    total_return_pct: number;
    annual_return_pct: number;
    annual_volatility_pct: number;
    sharpe_ratio: number;
    sortino_ratio: number;
    max_drawdown_pct: number;
    num_trades: number;
    win_rate_pct: number;
    final_equity: number;
  };
  equity_curve: number[];
  positions: number[];
  zscore_series: number[];
  dates: string[];
  ticker_a: string;
  ticker_b: string;
}

export const fetchScanner = async (topN = 20): Promise<ScannerResponse> => {
  const { data } = await api.get(`/scanner`, { params: { top_n: topN } });
  return data;
};

export const fetchPairDetail = async (a: string, b: string): Promise<PairDetail> => {
  const { data } = await api.get(`/pairs/${a}/${b}`);
  return data;
};

export const runBacktest = async (params: {
  ticker_a: string; ticker_b: string; capital?: number;
  entry_threshold?: number; exit_threshold?: number; stop_loss_z?: number;
}): Promise<BacktestResult> => {
  const { data } = await api.post(`/backtest`, params);
  return data;
};

export interface BacktestJobSummary {
  job_id: number;
  task_id: string;
  status: string;
}

export interface BacktestJobDetail {
  job_id: number;
  status: "PENDING" | "RUNNING" | "SUCCESS" | "FAILED";
  ticker_a: string;
  ticker_b: string;
  params: Record<string, any>;
  metrics: BacktestResult["metrics"] | null;
  equity_curve: number[] | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface BacktestHistoryItem {
  job_id: number;
  status: string;
  pair: string;
  metrics: BacktestResult["metrics"] | null;
  created_at: string;
}

export const submitBacktestJob = async (params: {
  ticker_a: string; ticker_b: string; capital?: number;
  entry_threshold?: number; exit_threshold?: number; stop_loss_z?: number; days?: number;
}): Promise<BacktestJobSummary> => {
  const { data } = await api.post(`/backtest/async`, params);
  return data;
};

export const fetchBacktestJob = async (jobId: number): Promise<BacktestJobDetail> => {
  const { data } = await api.get(`/backtest/jobs/${jobId}`);
  return data;
};

export const fetchBacktestHistory = async (): Promise<BacktestHistoryItem[]> => {
  const { data } = await api.get(`/backtest/history`);
  return data;
};

export const fetchRiskReport = async (positions: { ticker: string; market_value: number }[]) => {
  const { data } = await api.post(`/risk`, { positions });
  return data;
};

export const registerUser = async (email: string, password: string) => {
  const { data } = await api.post(`/auth/register`, { email, password });
  return data;
};

export const loginUser = async (email: string, password: string) => {
  const { data } = await api.post(`/auth/login`, { email, password });
  return data;
};

export interface OpenPosition {
  id: number;
  pair: string;
  direction: string;
  hedge_ratio: number;
  entry_z: number;
  current_z: number | null;
  entry_price_a: number;
  entry_price_b: number;
  current_price_a: number;
  current_price_b: number;
  capital_allocated: number;
  unrealized_pnl: number;
  opened_at: string;
  suggest_close: boolean;
}

export interface ClosedPosition {
  id: number;
  pair: string;
  direction: string;
  pnl: number;
  opened_at: string;
  closed_at: string | null;
}

export interface PortfolioResponse {
  starting_capital: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  open_positions: OpenPosition[];
  closed_positions: ClosedPosition[];
}

export const fetchPortfolio = async (): Promise<PortfolioResponse> => {
  const { data } = await api.get(`/paper-trading/portfolio`);
  return data;
};

export const openPaperTrade = async (ticker_a: string, ticker_b: string, capital_allocated = 10000) => {
  const { data } = await api.post(`/paper-trading/open`, { ticker_a, ticker_b, capital_allocated });
  return data;
};

export const closePaperTrade = async (tradeId: number) => {
  const { data } = await api.post(`/paper-trading/close/${tradeId}`);
  return data;
};

export const fetchOptimizer = async (
  opportunities: { pair: string; expected_return: number; volatility: number }[],
  capital: number,
  method: string
) => {
  const { data } = await api.post(`/optimizer`, { opportunities, capital, method });
  return data;
};

export interface NotebookCell {
  id: string;
  type: string;
  params: Record<string, any>;
  result?: any;
  error?: string;
}

export const runCell = async (cellType: string, params: Record<string, any>) => {
  const { data } = await api.post(`/research/run-cell`, { cell_type: cellType, params });
  return data.result;
};

export const listSessions = async () => {
  const { data } = await api.get(`/research/sessions`);
  return data as { id: number; name: string; num_cells: number; updated_at: string }[];
};

export const saveSession = async (name: string, cells: NotebookCell[]) => {
  const { data } = await api.post(`/research/sessions`, { name, cells });
  return data;
};

export const updateSession = async (id: number, name: string, cells: NotebookCell[]) => {
  const { data } = await api.put(`/research/sessions/${id}`, { name, cells });
  return data;
};

export const loadSession = async (id: number) => {
  const { data } = await api.get(`/research/sessions/${id}`);
  return data as { id: number; name: string; cells: NotebookCell[] };
};

export const deleteSession = async (id: number) => {
  const { data } = await api.delete(`/research/sessions/${id}`);
  return data;
};
