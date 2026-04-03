"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import type { Position } from "@/lib/api";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"];

function formatKrw(n: number) {
  return `${n.toLocaleString()}원`;
}

export function PortfolioPie({ positions }: { positions: Position[] }) {
  if (positions.length === 0) {
    return (
      <div className="bg-[var(--bg-card)] rounded-xl p-6 text-center text-[var(--text-secondary)]">
        보유 포지션 없음
      </div>
    );
  }

  const data = positions.map((p) => ({
    name: p.ticker.replace("KRW-", ""),
    value: p.current_price ? p.current_price * p.volume : p.amount_krw,
    pnl: p.pnl_pct,
  }));

  const total = data.reduce((sum, d) => sum + d.value, 0);

  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-4">
      <h3 className="font-medium mb-2">포트폴리오 구성</h3>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={80}
            dataKey="value"
            stroke="none"
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ backgroundColor: "#1e2130", border: "1px solid #374151", borderRadius: 8 }}
            formatter={(value: number, name: string) => [
              `${formatKrw(Math.round(value))} (${((value / total) * 100).toFixed(1)}%)`,
              name,
            ]}
          />
          <Legend
            formatter={(value, entry: any) => {
              const item = data.find((d) => d.name === value);
              const pnl = item?.pnl;
              const pnlStr = pnl != null ? ` ${pnl >= 0 ? "+" : ""}${pnl.toFixed(1)}%` : "";
              return <span className="text-xs">{value}<span className={pnl != null && pnl >= 0 ? "text-green-400" : "text-red-400"}>{pnlStr}</span></span>;
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
