"use client";

import type { DashboardData } from "@/lib/api";
import { StatusBadge } from "@/components/common/StatusBadge";

export function BotControl({ data }: { data: DashboardData }) {
  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-4">
      <h3 className="font-medium mb-3">봇 상태</h3>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--text-secondary)]">상태</span>
          <StatusBadge status={data.bot_status} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--text-secondary)]">시장</span>
          <StatusBadge status={data.market_regime} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--text-secondary)]">포지션</span>
          <span className="text-sm">{data.open_positions}개</span>
        </div>
        <div className="pt-2 text-xs text-[var(--text-secondary)] text-center">
          24시간 자동 운영
        </div>
      </div>
    </div>
  );
}
