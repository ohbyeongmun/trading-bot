"use client";

import { useEffect, useState } from "react";
import { api, type Trade } from "@/lib/api";

function formatKrw(n: number) {
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(n);
}

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.trades(200).then((t) => { setTrades(t); setLoading(false); }).catch(console.error);
  }, []);

  if (loading) {
    return <div className="text-[var(--text-secondary)]">로딩 중...</div>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">거래 내역</h2>

      <div className="bg-[var(--bg-card)] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[var(--text-secondary)] border-b border-gray-800">
                <th className="text-left px-4 py-3">시간</th>
                <th className="text-left px-4 py-3">타입</th>
                <th className="text-left px-4 py-3">코인</th>
                <th className="text-right px-4 py-3">가격</th>
                <th className="text-right px-4 py-3">금액</th>
                <th className="text-left px-4 py-3">전략</th>
                <th className="text-left px-4 py-3">사유</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">
                    {new Date(t.timestamp).toLocaleString("ko-KR")}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                      t.side === "buy" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
                    }`}>
                      {t.side === "buy" ? "매수" : "매도"}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium">{t.ticker.replace("KRW-", "")}</td>
                  <td className="px-4 py-3 text-right">{formatKrw(t.price)}</td>
                  <td className="px-4 py-3 text-right">{formatKrw(t.amount_krw)}원</td>
                  <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">{t.strategy}</td>
                  <td className="px-4 py-3 text-xs text-[var(--text-secondary)] max-w-xs truncate">
                    {t.reason}
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
