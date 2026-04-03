"use client";

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import type { DailyReport } from "@/lib/api";

export function DrawdownChart({ reports }: { reports: DailyReport[] }) {
  const data = [...reports].reverse();
  if (data.length < 2) {
    return <div className="bg-[var(--bg-card)] rounded-xl p-6 text-center text-[var(--text-secondary)]">데이터 부족</div>;
  }

  // 최대 낙폭(MDD) 계산
  let peak = data[0].ending_balance;
  const mddData = data.map((r) => {
    if (r.ending_balance > peak) peak = r.ending_balance;
    const drawdown = peak > 0 ? ((peak - r.ending_balance) / peak) * -100 : 0;
    return { date: r.date.slice(5), drawdown: Math.round(drawdown * 100) / 100 };
  });

  const maxDD = Math.min(...mddData.map((d) => d.drawdown));

  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-4">
      <h3 className="font-medium mb-2">
        최대 낙폭 (MDD)
        <span className="ml-2 text-sm text-red-400">{maxDD.toFixed(2)}%</span>
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={mddData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3148" />
          <XAxis dataKey="date" tick={{ fill: "#9ca3af", fontSize: 11 }} />
          <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} unit="%" domain={[Math.min(maxDD * 1.2, -1), 0]} />
          <Tooltip
            contentStyle={{ backgroundColor: "#1e2130", border: "1px solid #374151", borderRadius: 8 }}
            formatter={(value: number) => [`${value.toFixed(2)}%`, "낙폭"]}
          />
          <Area type="monotone" dataKey="drawdown" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
