"use client";

import { useState } from "react";
import { api, type DashboardData } from "@/lib/api";
import { StatusBadge } from "@/components/common/StatusBadge";

export function BotControl({ data, onRefresh }: { data: DashboardData; onRefresh: () => void }) {
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    setLoading(true);
    try {
      await api.botStart();
      onRefresh();
    } catch {}
    setLoading(false);
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await api.botStop();
      onRefresh();
    } catch {}
    setLoading(false);
  };

  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-4">
      <h3 className="font-medium mb-3">봇 제어</h3>
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
        <div className="flex gap-2 pt-2">
          {data.bot_status === "running" ? (
            <button
              onClick={handleStop}
              disabled={loading}
              className="flex-1 px-3 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-sm font-medium transition disabled:opacity-50"
            >
              {loading ? "..." : "거래 중지"}
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={loading}
              className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium transition disabled:opacity-50"
            >
              {loading ? "..." : "거래 시작"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
