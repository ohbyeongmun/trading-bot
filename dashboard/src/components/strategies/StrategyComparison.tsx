"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";
import type { StrategyStats } from "@/lib/api";

export function StrategyComparison({ strategies }: { strategies: StrategyStats[] }) {
  const data = strategies.map((s) => ({
    name: s.name,
    win_rate: Math.round(s.win_rate * 100),
    total_pnl: s.total_pnl,
    total_trades: s.total_trades,
  }));

  return (
    <div className="space-y-6">
      {/* 승률 비교 */}
      <div className="bg-[var(--bg-card)] rounded-xl p-4">
        <h3 className="font-medium mb-4">전략별 승률</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2d3148" />
            <XAxis dataKey="name" tick={{ fill: "#9ca3af", fontSize: 11 }} />
            <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} unit="%" />
            <Tooltip
              contentStyle={{ backgroundColor: "#1e2130", border: "1px solid #374151", borderRadius: 8 }}
            />
            <Bar dataKey="win_rate" radius={[4, 4, 0, 0]}>
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.win_rate >= 50 ? "#10b981" : "#ef4444"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 전략 상세 테이블 */}
      <div className="bg-[var(--bg-card)] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-800">
          <h3 className="font-medium">전략 상세</h3>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[var(--text-secondary)] border-b border-gray-800">
              <th className="text-left px-4 py-2">전략</th>
              <th className="text-right px-4 py-2">거래수</th>
              <th className="text-right px-4 py-2">승률</th>
              <th className="text-right px-4 py-2">평균 수익</th>
              <th className="text-right px-4 py-2">평균 손실</th>
              <th className="text-right px-4 py-2">총 PnL</th>
            </tr>
          </thead>
          <tbody>
            {strategies.map((s) => (
              <tr key={s.name} className="border-b border-gray-800/50">
                <td className="px-4 py-3 font-medium">{s.name}</td>
                <td className="px-4 py-3 text-right">{s.total_trades}</td>
                <td className={`px-4 py-3 text-right ${s.win_rate >= 0.5 ? "text-green-400" : "text-red-400"}`}>
                  {(s.win_rate * 100).toFixed(1)}%
                </td>
                <td className="px-4 py-3 text-right text-green-400">+{s.avg_profit_pct.toFixed(2)}%</td>
                <td className="px-4 py-3 text-right text-red-400">-{s.avg_loss_pct.toFixed(2)}%</td>
                <td className={`px-4 py-3 text-right font-medium ${s.total_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {s.total_pnl >= 0 ? "+" : ""}{s.total_pnl.toLocaleString()}원
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
