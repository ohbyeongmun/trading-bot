"use client";

import type { Position } from "@/lib/api";

function formatKrw(n: number) {
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(n);
}

export function PositionsTable({ positions }: { positions: Position[] }) {
  if (positions.length === 0) {
    return (
      <div className="bg-[var(--bg-card)] rounded-xl p-6 text-center text-[var(--text-secondary)]">
        현재 보유 포지션 없음
      </div>
    );
  }

  return (
    <div className="bg-[var(--bg-card)] rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800">
        <h3 className="font-medium">보유 포지션</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[var(--text-secondary)] border-b border-gray-800">
              <th className="text-left px-4 py-2">코인</th>
              <th className="text-right px-4 py-2">매수가</th>
              <th className="text-right px-4 py-2">현재가</th>
              <th className="text-right px-4 py-2">수익률</th>
              <th className="text-right px-4 py-2">금액</th>
              <th className="text-left px-4 py-2">전략</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="px-4 py-3 font-medium">{p.ticker.replace("KRW-", "")}</td>
                <td className="px-4 py-3 text-right">{formatKrw(p.entry_price)}</td>
                <td className="px-4 py-3 text-right">
                  {p.current_price ? formatKrw(p.current_price) : "-"}
                </td>
                <td className={`px-4 py-3 text-right font-medium ${
                  (p.pnl_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"
                }`}>
                  {p.pnl_pct != null ? `${p.pnl_pct >= 0 ? "+" : ""}${p.pnl_pct.toFixed(2)}%` : "-"}
                </td>
                <td className="px-4 py-3 text-right">{formatKrw(p.amount_krw)}</td>
                <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">{p.strategy}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
