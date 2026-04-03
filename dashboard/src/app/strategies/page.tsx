"use client";

import { useEffect, useState } from "react";
import { api, type StrategyStats, type DailyReport, type Trade } from "@/lib/api";
import { StrategyComparison } from "@/components/strategies/StrategyComparison";
import { DrawdownChart } from "@/components/strategies/DrawdownChart";
import { PnlHistogram } from "@/components/strategies/PnlHistogram";

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<StrategyStats[]>([]);
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);

  useEffect(() => {
    Promise.all([
      api.strategies(),
      api.dailyReports(90),
      api.trades(500),
    ]).then(([s, r, t]) => {
      setStrategies(s);
      setReports(r);
      setTrades(t);
    }).catch(console.error);
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">전략 분석</h2>
      <StrategyComparison strategies={strategies} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DrawdownChart reports={reports} />
        <PnlHistogram trades={trades} />
      </div>
    </div>
  );
}
