"use client";

import { useEffect, useState, useCallback } from "react";
import { api, type DashboardData, type Position, type Trade, type DailyReport } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import { BalanceCard } from "@/components/dashboard/BalanceCard";
import { PositionsTable } from "@/components/dashboard/PositionsTable";
import { RecentTrades } from "@/components/dashboard/RecentTrades";
import { PnlChart } from "@/components/dashboard/PnlChart";
import { PortfolioPie } from "@/components/dashboard/PortfolioPie";
import { WinLossChart } from "@/components/dashboard/WinLossChart";
import { DailyActivity } from "@/components/dashboard/DailyActivity";
import { TradeScatter } from "@/components/dashboard/TradeScatter";

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [d, p, t, r] = await Promise.all([
        api.dashboard(),
        api.positions(),
        api.trades(500),
        api.dailyReports(30),
      ]);
      setDashboard(d);
      setPositions(p);
      setTrades(t);
      setReports(r);
      setError(null);
    } catch (e) {
      setError("API 연결 실패. 서버가 실행 중인지 확인하세요.");
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 10000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleEvent = useCallback(() => {
    fetchAll();
  }, [fetchAll]);

  const { connected } = useWebSocket(handleEvent);

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="bg-[var(--bg-card)] rounded-xl p-8 text-center max-w-md">
          <p className="text-red-400 text-lg mb-2">연결 실패</p>
          <p className="text-[var(--text-secondary)] text-sm">{error}</p>
          <button
            onClick={fetchAll}
            className="mt-4 px-4 py-2 bg-blue-600 rounded-lg text-sm hover:bg-blue-700 transition"
          >
            재시도
          </button>
        </div>
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-[var(--text-secondary)]">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">대시보드</h2>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-red-400"}`} />
          <span className="text-xs text-[var(--text-secondary)]">
            {connected ? "실시간 연결" : "연결 끊김"}
          </span>
        </div>
      </div>

      {/* Row 1: 자산 요약 */}
      <BalanceCard data={dashboard} />

      {/* Row 2: 누적 손익 + 포트폴리오 + 승패 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <PnlChart reports={reports} trades={trades} />
        </div>
        <div className="space-y-6">
          <PortfolioPie positions={positions} />
          <WinLossChart trades={trades} />
        </div>
      </div>

      {/* Row 3: 거래 분포 + 일별 활동 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TradeScatter trades={trades} />
        <DailyActivity trades={trades} />
      </div>

      {/* Row 4: 포지션 + 최근 거래 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PositionsTable positions={positions} />
        <RecentTrades trades={trades} />
      </div>
    </div>
  );
}
