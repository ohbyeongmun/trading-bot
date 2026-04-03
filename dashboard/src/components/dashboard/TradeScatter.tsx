"use client";

import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine, ZAxis } from "recharts";
import type { Trade } from "@/lib/api";

export function TradeScatter({ trades }: { trades: Trade[] }) {
  // 매도 거래에서 수익률과 금액 추출
  const data = trades
    .filter((t) => t.side === "sell")
    .map((t) => {
      const match = t.reason.match(/([+-]?\d+\.?\d*)%/);
      const pnl = match ? parseFloat(match[1]) : null;
      if (pnl === null) return null;
      return {
        coin: t.ticker.replace("KRW-", ""),
        pnl,
        amount: t.amount_krw,
        strategy: t.strategy,
        time: t.timestamp.slice(5, 16),
      };
    })
    .filter(Boolean);

  if (data.length === 0) {
    return (
      <div className="bg-[var(--bg-card)] rounded-xl p-6 text-center text-[var(--text-secondary)]">
        수익률 데이터 없음
      </div>
    );
  }

  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-4">
      <h3 className="font-medium mb-4">거래별 수익률 분포</h3>
      <ResponsiveContainer width="100%" height={220}>
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3148" />
          <XAxis
            dataKey="time"
            tick={{ fill: "#9ca3af", fontSize: 10 }}
            name="시간"
          />
          <YAxis
            dataKey="pnl"
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            unit="%"
            name="수익률"
          />
          <ZAxis dataKey="amount" range={[30, 200]} name="금액" />
          <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="3 3" />
          <Tooltip
            contentStyle={{ backgroundColor: "#1e2130", border: "1px solid #374151", borderRadius: 8 }}
            formatter={(value: any, name: string) => {
              if (name === "수익률") return [`${value}%`, name];
              if (name === "금액") return [`${Number(value).toLocaleString()}원`, name];
              return [value, name];
            }}
            labelFormatter={(label) => `${label}`}
          />
          <Scatter
            data={data}
            fill="#3b82f6"
            shape={(props: any) => {
              const { cx, cy, payload } = props;
              const color = payload.pnl >= 0 ? "#10b981" : "#ef4444";
              const r = Math.max(4, Math.min(12, payload.amount / 3000));
              return <circle cx={cx} cy={cy} r={r} fill={color} fillOpacity={0.7} stroke={color} strokeWidth={1} />;
            }}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
