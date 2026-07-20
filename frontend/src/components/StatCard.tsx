interface Props {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
  negative?: boolean;
}

export default function StatCard({ label, value, sub, positive, negative }: Props) {
  const color = positive ? "text-green-400" : negative ? "text-red-400" : "text-white";
  return (
    <div className="bg-[#12151f] border border-[#232838] rounded-lg p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-2xl font-semibold ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  );
}
