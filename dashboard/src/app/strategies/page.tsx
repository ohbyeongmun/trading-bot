"use client";

import { useEffect, useState } from "react";
import { api, type StrategyStats } from "@/lib/api";
import { StrategyComparison } from "@/components/strategies/StrategyComparison";

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<StrategyStats[]>([]);

  useEffect(() => {
    api.strategies().then(setStrategies).catch(console.error);
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">전략 분석</h2>
      <StrategyComparison strategies={strategies} />
    </div>
  );
}
