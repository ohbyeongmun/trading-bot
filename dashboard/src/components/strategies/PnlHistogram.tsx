"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";
import type { Trade } from "@/lib/api";

export function PnlHistogram({ trades }: { trades: Trade[] }) {
  // 매도 거래에서 수익률 추출
  const pnlValues: number[] = [];
  for (const t of trades) {
    if (t.side !== "sell") continue;
    const match = t.reason.match(/([+-]?\d+\.?\d*)%/);
    if (match) pnlValues.push(parseFloat(match[1]));
  }

  if (pnlValues.length < 3) {
    return <div className="bg-[var(--bg-card)] rounded-xl p-6 text-center text-[var(--text-secondary)]">데이터 부족</div>;
  }

  // 히스토그램 빈 생성 (-6% ~ +6%, 0.5% 간격)
  const binSize = 0.5;
  const minBin = -6;
  const maxBin = 6;
  const bins: Record<string, number> = {};
  for (let b = minBin; b < maxBin; b += binSize) {
    const label = `${b >= 0 ? "+" : ""}${b.toFixed(1)}`;
    bins[label] = 0;
  }

  for (const pnl of pnlValues) {
    const binIndex = Math.max(minBin, Math.min(maxBin - binSize, Math.floor(pnl / binSize) * binSize));
    const label = `${binIndex >= 0 ? "+" : ""}${binIndex.toFixed(1)}`;
    if (bins[label] !== undefined) bins[label]++;
  }

  const data = Object.entries(bins).map(([label, count]) => ({
    range: label,
    count,
    isPositive: parseFloat(label) >= 0,
  }));

  const avgPnl = pnlValues.reduce((a, b) => a + b, 0) / pnlValues.length;

  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-4">
      <h3 className="font-medium mb-2">
        수익률 분포
        <span className={`ml-2 text-sm ${avgPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
          평균 {avgPnl >= 0 ? "+" : ""}{avgPnl.toFixed(2)}%
        </span>
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3148" />
          <XAxis dataKey="range" tick={{ fill: "#9ca3af", fontSize: 9 }} interval={3} />
          <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ backgroundColor: "#1e2130", border: "1px solid #374151", borderRadius: 8 }}
            formatter={(value: number) => [`${value}건`, "거래수"]}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.isPositive ? "#10b981" : "#ef4444"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
