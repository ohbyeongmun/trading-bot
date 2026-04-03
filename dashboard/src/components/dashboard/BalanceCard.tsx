"use client";

import { StatusBadge } from "@/components/common/StatusBadge";
import type { DashboardData } from "@/lib/api";

function formatKrw(n: number) {
  return new Intl.NumberFormat("ko-KR", { style: "currency", currency: "KRW", maximumFractionDigits: 0 }).format(n);
}

function formatPct(n: number) {
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export function BalanceCard({ data }: { data: DashboardData }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 총 자산 */}
      <div className="bg-[var(--bg-card)] rounded-xl p-4 col-span-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm text-[var(--text-secondary)]">총 자산</span>
          <div className="flex gap-2">
            <StatusBadge status={data.bot_status} />
            <StatusBadge status={data.market_regime} />
          </div>
        </div>
        <p className="text-2xl font-bold">{formatKrw(data.total_balance)}</p>
        <p className="text-sm text-[var(--text-secondary)]">
          보유 포지션 {data.open_positions}개
        </p>
      </div>

      {/* 일일 수익 */}
      <div className="bg-[var(--bg-card)] rounded-xl p-4">
        <span className="text-sm text-[var(--text-secondary)]">일일</span>
        <p className={`text-xl font-bold ${data.daily_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
          {formatPct(data.daily_pnl_pct)}
        </p>
        <p className="text-xs text-[var(--text-secondary)]">{formatKrw(data.daily_pnl)}</p>
      </div>

      {/* 주간 수익 */}
      <div className="bg-[var(--bg-card)] rounded-xl p-4">
        <span className="text-sm text-[var(--text-secondary)]">주간</span>
        <p className={`text-xl font-bold ${data.weekly_pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
          {formatPct(data.weekly_pnl_pct)}
        </p>
      </div>
    </div>
  );
}
