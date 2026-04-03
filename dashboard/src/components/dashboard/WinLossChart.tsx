"use client";

import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import type { Trade } from "@/lib/api";

export function WinLossChart({ trades }: { trades: Trade[] }) {
  const sellTrades = trades.filter((t) => t.side === "sell");
  if (sellTrades.length === 0) {
    return (
      <div className="bg-[var(--bg-card)] rounded-xl p-6 text-center text-[var(--text-secondary)]">
        매도 거래 없음
      </div>
    );
  }

  let wins = 0;
  let losses = 0;

  for (const t of sellTrades) {
    const match = t.reason.match(/([+-]?\d+\.?\d*)%/);
    if (match) {
      parseFloat(match[1]) >= 0 ? wins++ : losses++;
    }
  }

  const total = wins + losses;
  if (total === 0) {
    return (
      <div className="bg-[var(--bg-card)] rounded-xl p-6 text-center text-[var(--text-secondary)]">
        수익률 데이터 없음
      </div>
    );
  }

  const winRate = ((wins / total) * 100).toFixed(1);
  const data = [
    { name: "수익", value: wins },
    { name: "손실", value: losses },
  ];

  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-4">
      <h3 className="font-medium mb-2">승패 비율</h3>
      <div className="flex items-center gap-4">
        <ResponsiveContainer width={120} height={120}>
          <PieChart>
            <Pie data={data} cx="50%" cy="50%" innerRadius={35} outerRadius={50} dataKey="value" stroke="none">
              <Cell fill="#10b981" />
              <Cell fill="#ef4444" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="space-y-2">
          <div className="text-2xl font-bold">{winRate}%</div>
          <div className="text-xs text-[var(--text-secondary)]">
            <span className="text-green-400">{wins}승</span> / <span className="text-red-400">{losses}패</span>
          </div>
          <div className="text-xs text-[var(--text-secondary)]">총 {total}건 매도</div>
        </div>
      </div>
    </div>
  );
}
