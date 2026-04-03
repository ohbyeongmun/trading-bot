"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from "recharts";
import type { DailyReport, Trade } from "@/lib/api";

function formatKrw(n: number) {
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1)}만`;
  return `${n.toLocaleString()}`;
}

interface PnlChartProps {
  reports: DailyReport[];
  trades: Trade[];
}

export function PnlChart({ reports, trades }: PnlChartProps) {
  // 거래 기반 누적 PnL 차트 (매도 거래의 손익 누적)
  const tradeData = buildTradeBasedData(trades);
  // 일일 리포트 기반 잔고 차트
  const reportData = [...reports].reverse().map((r) => ({
    date: r.date,
    balance: r.ending_balance,
  }));

  // 거래 데이터가 있으면 누적 PnL, 없으면 일일 잔고
  const hasTradeData = tradeData.length > 1;
  const hasReportData = reportData.length > 1;

  if (!hasTradeData && !hasReportData) {
    return (
      <div className="bg-[var(--bg-card)] rounded-xl p-6 text-center text-[var(--text-secondary)]">
        차트 데이터가 아직 없습니다. 거래가 발생하면 여기에 표시됩니다.
      </div>
    );
  }

  if (hasTradeData) {
    const values = tradeData.map((d) => d.cumPnl);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max(Math.abs(max - min) * 0.1, 1000);

    return (
      <div className="bg-[var(--bg-card)] rounded-xl p-4">
        <h3 className="font-medium mb-4">
          누적 손익
          <span className={`ml-2 text-sm ${values[values.length - 1] >= 0 ? "text-green-400" : "text-red-400"}`}>
            {values[values.length - 1] >= 0 ? "+" : ""}{formatKrw(values[values.length - 1])}원
          </span>
        </h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={tradeData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2d3148" />
            <XAxis
              dataKey="date"
              tick={{ fill: "#9ca3af", fontSize: 11 }}
            />
            <YAxis
              tick={{ fill: "#9ca3af", fontSize: 11 }}
              tickFormatter={formatKrw}
              domain={[min - padding, max + padding]}
            />
            <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="3 3" />
            <Tooltip
              contentStyle={{ backgroundColor: "#1e2130", border: "1px solid #374151", borderRadius: 8 }}
              labelStyle={{ color: "#9ca3af" }}
              formatter={(value: number) => [`${value >= 0 ? "+" : ""}${value.toLocaleString()}원`, "누적 손익"]}
            />
            <Line
              type="monotone"
              dataKey="cumPnl"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ r: 3, fill: "#3b82f6" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // 일일 리포트 기반 (폴백)
  const balances = reportData.map((d) => d.balance);
  const min = Math.min(...balances);
  const max = Math.max(...balances);
  const padding = Math.max((max - min) * 0.1, 1000);

  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-4">
      <h3 className="font-medium mb-4">자산 추이</h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={reportData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3148" />
          <XAxis dataKey="date" tick={{ fill: "#9ca3af", fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
          <YAxis
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            tickFormatter={formatKrw}
            domain={[min - padding, max + padding]}
          />
          <Tooltip
            contentStyle={{ backgroundColor: "#1e2130", border: "1px solid #374151", borderRadius: 8 }}
            labelStyle={{ color: "#9ca3af" }}
            formatter={(value: number) => [`${value.toLocaleString()}원`, "잔고"]}
          />
          <Line type="monotone" dataKey="balance" stroke="#3b82f6" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}


function buildTradeBasedData(trades: Trade[]) {
  // 매도 거래만 추출하여 날짜별 PnL 누적
  const sellTrades = [...trades]
    .filter((t) => t.side === "sell")
    .reverse(); // 오래된 것부터

  if (sellTrades.length === 0) return [];

  let cumPnl = 0;
  const byDate: Record<string, number> = {};

  for (const t of sellTrades) {
    // 매도 금액에서 대략적 PnL 추정 (reason에 % 정보가 있으면 파싱)
    const pnlMatch = t.reason.match(/([+-]?\d+\.?\d*)%/);
    if (pnlMatch) {
      const pct = parseFloat(pnlMatch[1]);
      const pnl = t.amount_krw * (pct / 100);
      cumPnl += pnl;
    }

    const dateKey = t.timestamp.slice(0, 10);
    byDate[dateKey] = cumPnl;
  }

  return Object.entries(byDate).map(([date, cumPnl]) => ({
    date: date.slice(5), // MM-DD
    cumPnl: Math.round(cumPnl),
  }));
}
