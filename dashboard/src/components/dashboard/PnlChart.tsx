"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import type { DailyReport } from "@/lib/api";

function formatKrw(n: number) {
  return `${(n / 10000).toFixed(0)}만`;
}

export function PnlChart({ reports }: { reports: DailyReport[] }) {
  const data = [...reports].reverse().map((r) => ({
    date: r.date,
    balance: r.ending_balance,
    pnl: r.pnl,
  }));

  if (data.length === 0) {
    return (
      <div className="bg-[var(--bg-card)] rounded-xl p-6 text-center text-[var(--text-secondary)]">
        일일 리포트 데이터 없음
      </div>
    );
  }

  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-4">
      <h3 className="font-medium mb-4">자산 추이</h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3148" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            tickFormatter={(v) => v.slice(5)}
          />
          <YAxis
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            tickFormatter={formatKrw}
          />
          <Tooltip
            contentStyle={{ backgroundColor: "#1e2130", border: "1px solid #374151", borderRadius: 8 }}
            labelStyle={{ color: "#9ca3af" }}
            formatter={(value: number) => [`${value.toLocaleString()}원`, "잔고"]}
          />
          <Line
            type="monotone"
            dataKey="balance"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
