"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

const SIGNAL_COLORS: Record<string, string> = {
  STRONG_BUY: "bg-green-500/30 text-green-300 font-bold",
  BUY: "bg-green-500/20 text-green-400",
  NEUTRAL: "bg-gray-700/30 text-gray-400",
  SELL: "bg-red-500/20 text-red-400",
  STRONG_SELL: "bg-red-500/30 text-red-300 font-bold",
};

function getRsiColor(rsi: number | null) {
  if (rsi === null) return "text-gray-500";
  if (rsi <= 30) return "text-green-400 font-bold";
  if (rsi <= 45) return "text-green-400";
  if (rsi >= 70) return "text-red-400 font-bold";
  if (rsi >= 55) return "text-red-400";
  return "text-gray-300";
}

function getBBColor(bb: number | null) {
  if (bb === null) return "text-gray-500";
  if (bb <= 20) return "text-green-400";
  if (bb >= 80) return "text-red-400";
  return "text-gray-300";
}

function getVolColor(vol: number | null) {
  if (vol === null) return "text-gray-500";
  if (vol >= 3) return "text-yellow-300 font-bold";
  if (vol >= 2) return "text-yellow-400";
  if (vol >= 1.5) return "text-blue-400";
  return "text-gray-300";
}

export default function ScannerPage() {
  const [coins, setCoins] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"ALL" | "BUY" | "SELL" | "HELD">("ALL");

  const fetchScanner = useCallback(async () => {
    try {
      const data = await api.scanner();
      setCoins(data);
      setLoading(false);
    } catch {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchScanner();
    const interval = setInterval(fetchScanner, 30000); // 30초마다 갱신
    return () => clearInterval(interval);
  }, [fetchScanner]);

  const filtered = coins.filter((c) => {
    if (filter === "BUY") return c.signal === "BUY" || c.signal === "STRONG_BUY";
    if (filter === "SELL") return c.signal === "SELL" || c.signal === "STRONG_SELL";
    if (filter === "HELD") return c.held;
    return true;
  });

  const buyCount = coins.filter((c) => c.signal === "BUY" || c.signal === "STRONG_BUY").length;
  const sellCount = coins.filter((c) => c.signal === "SELL" || c.signal === "STRONG_SELL").length;
  const heldCount = coins.filter((c) => c.held).length;

  if (loading) {
    return <div className="text-[var(--text-secondary)] p-8 text-center">스캐너 로딩 중... (50코인 분석, 약 10초)</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">코인 스캐너</h2>
        <span className="text-xs text-[var(--text-secondary)]">{coins.length}개 코인 관찰 중</span>
      </div>

      {/* 필터 탭 */}
      <div className="flex gap-2">
        {[
          { key: "ALL", label: `전체 (${coins.length})` },
          { key: "BUY", label: `매수 신호 (${buyCount})` },
          { key: "SELL", label: `매도 신호 (${sellCount})` },
          { key: "HELD", label: `보유 중 (${heldCount})` },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key as any)}
            className={`px-3 py-1.5 rounded-lg text-xs transition ${
              filter === key ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* 테이블 */}
      <div className="bg-[var(--bg-card)] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[var(--text-secondary)] border-b border-gray-800 text-xs">
                <th className="text-left px-3 py-2">코인</th>
                <th className="text-center px-3 py-2">신호</th>
                <th className="text-right px-3 py-2">가격</th>
                <th className="text-right px-3 py-2">24h</th>
                <th className="text-right px-3 py-2">RSI</th>
                <th className="text-right px-3 py-2">BB%</th>
                <th className="text-right px-3 py-2">거래량</th>
                <th className="text-right px-3 py-2">신뢰도</th>
                <th className="text-center px-3 py-2">보유</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.ticker} className={`border-b border-gray-800/30 hover:bg-gray-800/30 ${c.held ? "bg-blue-900/10" : ""}`}>
                  <td className="px-3 py-2.5 font-medium">{c.coin}</td>
                  <td className="px-3 py-2.5 text-center">
                    <span className={`px-2 py-0.5 rounded text-xs ${SIGNAL_COLORS[c.signal] || ""}`}>
                      {c.signal}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right">{c.price?.toLocaleString()}</td>
                  <td className={`px-3 py-2.5 text-right ${(c.change_24h ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {c.change_24h != null ? `${c.change_24h >= 0 ? "+" : ""}${c.change_24h}%` : "-"}
                  </td>
                  <td className={`px-3 py-2.5 text-right ${getRsiColor(c.rsi)}`}>
                    {c.rsi ?? "-"}
                  </td>
                  <td className={`px-3 py-2.5 text-right ${getBBColor(c.bb_position)}`}>
                    {c.bb_position != null ? `${c.bb_position}%` : "-"}
                  </td>
                  <td className={`px-3 py-2.5 text-right ${getVolColor(c.volume_ratio)}`}>
                    {c.volume_ratio != null ? `${c.volume_ratio}x` : "-"}
                  </td>
                  <td className="px-3 py-2.5 text-right text-gray-400">
                    {(c.confidence * 100).toFixed(0)}%
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    {c.held ? (
                      <span className={`text-xs ${(c.pnl_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {c.pnl_pct != null ? `${c.pnl_pct >= 0 ? "+" : ""}${c.pnl_pct}%` : "보유"}
                      </span>
                    ) : (
                      <span className="text-gray-600">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
