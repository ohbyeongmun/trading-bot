"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";
import type { Trade } from "@/lib/api";

export function DailyActivity({ trades }: { trades: Trade[] }) {
  // 날짜별 매수/매도 건수 집계
  const byDate: Record<string, { buys: number; sells: number }> = {};

  for (const t of trades) {
    const date = t.timestamp.slice(0, 10);
    if (!byDate[date]) byDate[date] = { buys: 0, sells: 0 };
    t.side === "buy" ? byDate[date].buys++ : byDate[date].sells++;
  }

  const data = Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-14) // 최근 14일
    .map(([date, { buys, sells }]) => ({
      date: date.slice(5),
      매수: buys,
      매도: sells,
    }));

  if (data.length === 0) {
    return (
      <div className="bg-[var(--bg-card)] rounded-xl p-6 text-center text-[var(--text-secondary)]">
        거래 활동 데이터 없음
      </div>
    );
  }

  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-4">
      <h3 className="font-medium mb-4">일별 거래 활동</h3>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3148" />
          <XAxis dataKey="date" tick={{ fill: "#9ca3af", fontSize: 11 }} />
          <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ backgroundColor: "#1e2130", border: "1px solid #374151", borderRadius: 8 }}
          />
          <Bar dataKey="매수" fill="#10b981" radius={[2, 2, 0, 0]} />
          <Bar dataKey="매도" fill="#ef4444" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
