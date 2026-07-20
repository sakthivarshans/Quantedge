import { useParams, Link } from "react-router-dom";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { useQuery } from "@tanstack/react-query";
import { fetchPairDetail } from "../api/client";
import StatCard from "../components/StatCard";

export default function PairDetail() {
  const { a, b } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ["pairDetail", a, b],
    queryFn: () => fetchPairDetail(a!, b!),
    enabled: Boolean(a && b),
  });

  if (isLoading) return <div className="p-8 text-gray-500">Loading pair analysis…</div>;
  if (error || !data) return <div className="p-8 text-red-400">Could not load pair data.</div>;

  const priceChart = data.dates.map((d, i) => ({
    date: d, [data.ticker_a]: data.price_a[i], [data.ticker_b]: data.price_b[i],
  }));
  const spreadChart = data.dates.map((d, i) => ({ date: d, spread: data.spread[i] }));
  const zChart = data.dates.map((d, i) => ({ date: d, z: data.zscore_series[i] }));

  const pvalue = data.cointegration.p_value;
  const cointegrated = pvalue < 0.05;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <Link to="/scanner" className="text-xs text-gray-500 hover:text-gray-300">← Back to Scanner</Link>
      <h1 className="text-2xl font-semibold text-white mt-2 mb-1">
        {data.ticker_a} / {data.ticker_b}
      </h1>
      <p className="text-gray-500 text-sm mb-6">
        Signal: <span className={data.signal === "BUY" ? "text-green-400" : data.signal === "SELL" ? "text-red-400" : "text-gray-400"}>{data.signal}</span>
        {" · "}Confidence {data.confidence}%
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Correlation" value={data.correlation.toFixed(3)} />
        <StatCard label="Hedge Ratio (β)" value={data.hedge_ratio.toFixed(3)} />
        <StatCard
          label="Cointegration p-value"
          value={pvalue.toExponential(2)}
          positive={cointegrated}
          negative={!cointegrated}
          sub={cointegrated ? "Cointegrated (95% conf.)" : "Not cointegrated"}
        />
        <StatCard label="Half-life" value={data.half_life_days ? `${data.half_life_days} days` : "—"} sub="mean reversion speed" />
      </div>

      <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5 mb-6">
        <h2 className="text-white font-medium mb-4">Price Chart</h2>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={priceChart}>
            <CartesianGrid strokeDasharray="3 3" stroke="#232838" />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b7280" }} minTickGap={40} />
            <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} />
            <Tooltip contentStyle={{ background: "#12151f", border: "1px solid #232838" }} />
            <Line type="monotone" dataKey={data.ticker_a} stroke="#3b82f6" dot={false} strokeWidth={1.5} />
            <Line type="monotone" dataKey={data.ticker_b} stroke="#f59e0b" dot={false} strokeWidth={1.5} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid md:grid-cols-2 gap-6 mb-6">
        <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5">
          <h2 className="text-white font-medium mb-4">Spread</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={spreadChart}>
              <CartesianGrid strokeDasharray="3 3" stroke="#232838" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b7280" }} minTickGap={60} />
              <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} />
              <Tooltip contentStyle={{ background: "#12151f", border: "1px solid #232838" }} />
              <Line type="monotone" dataKey="spread" stroke="#a78bfa" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5">
          <h2 className="text-white font-medium mb-4">Z-score</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={zChart}>
              <CartesianGrid strokeDasharray="3 3" stroke="#232838" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b7280" }} minTickGap={60} />
              <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} domain={[-4, 4]} />
              <Tooltip contentStyle={{ background: "#12151f", border: "1px solid #232838" }} />
              <ReferenceLine y={2} stroke="#ef4444" strokeDasharray="3 3" />
              <ReferenceLine y={-2} stroke="#22c55e" strokeDasharray="3 3" />
              <ReferenceLine y={0} stroke="#6b7280" />
              <Line type="monotone" dataKey="z" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-[#12151f] border border-[#232838] rounded-lg p-5 mb-6">
        <h2 className="text-white font-medium mb-3">Statistical Tests</h2>
        <div className="grid md:grid-cols-2 gap-6 text-sm">
          <div>
            <div className="text-gray-500 mb-1">Engle-Granger Cointegration Test</div>
            <div className="text-gray-300">Statistic: {data.cointegration.coint_stat.toFixed(3)}</div>
            <div className="text-gray-300">p-value: {data.cointegration.p_value.toExponential(3)}</div>
            <div className="text-gray-500 text-xs mt-1">
              Critical values — 1%: {data.cointegration.crit_1pct.toFixed(2)}, 5%: {data.cointegration.crit_5pct.toFixed(2)}, 10%: {data.cointegration.crit_10pct.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-gray-500 mb-1">ADF Test on Spread (Residuals)</div>
            <div className="text-gray-300">Statistic: {data.adf_on_spread.adf_stat.toFixed(3)}</div>
            <div className="text-gray-300">p-value: {data.adf_on_spread.p_value.toExponential(3)}</div>
            <div className="text-gray-500 text-xs mt-1">
              Critical values — 1%: {data.adf_on_spread.crit_1pct.toFixed(2)}, 5%: {data.adf_on_spread.crit_5pct.toFixed(2)}, 10%: {data.adf_on_spread.crit_10pct.toFixed(2)}
            </div>
          </div>
        </div>
      </div>

      <Link
        to={`/lab?a=${data.ticker_a}&b=${data.ticker_b}`}
        className="inline-block bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded"
      >
        Backtest this pair in Strategy Lab →
      </Link>
    </div>
  );
}
