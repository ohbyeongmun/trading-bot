"use client";

import type { Trade } from "@/lib/api";

function formatKrw(n: number) {
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(n);
}

function timeAgo(ts: string) {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "방금";
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

export function RecentTrades({ trades }: { trades: Trade[] }) {
  return (
    <div className="bg-[var(--bg-card)] rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800">
        <h3 className="font-medium">최근 거래</h3>
      </div>
      <div className="divide-y divide-gray-800/50 max-h-80 overflow-y-auto">
        {trades.length === 0 && (
          <div className="px-4 py-6 text-center text-[var(--text-secondary)]">거래 내역 없음</div>
        )}
        {trades.map((t) => (
          <div key={t.id} className="px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                t.side === "buy" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
              }`}>
                {t.side === "buy" ? "매수" : "매도"}
              </span>
              <div>
                <p className="text-sm font-medium">{t.ticker.replace("KRW-", "")}</p>
                <p className="text-xs text-[var(--text-secondary)]">{t.strategy}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm">{formatKrw(t.amount_krw)}원</p>
              <p className="text-xs text-[var(--text-secondary)]">{timeAgo(t.timestamp)}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
