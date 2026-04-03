"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Position } from "@/lib/api";

interface CandleChartProps {
  positions: Position[];
}

export function CandleChart({ positions }: CandleChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const observerRef = useRef<ResizeObserver | null>(null);
  const [selectedTicker, setSelectedTicker] = useState<string>("");
  const [interval, setInterval_] = useState("minute15");
  const [loading, setLoading] = useState(false);

  const tickers = positions.map((p) => p.ticker);

  useEffect(() => {
    if (tickers.length > 0 && !selectedTicker) {
      setSelectedTicker(tickers[0]);
    }
  }, [tickers, selectedTicker]);

  useEffect(() => {
    if (!selectedTicker || !containerRef.current) return;

    let cancelled = false;

    // 이전 차트 정리
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
    }
    if (chartRef.current) {
      try { chartRef.current.remove(); } catch {}
      chartRef.current = null;
    }

    async function loadChart() {
      setLoading(true);
      try {
        const { createChart } = await import("lightweight-charts");

        if (cancelled || !containerRef.current) return;

        const chart = createChart(containerRef.current, {
          width: containerRef.current.clientWidth,
          height: 350,
          layout: {
            background: { color: "#1e2130" },
            textColor: "#9ca3af",
          },
          grid: {
            vertLines: { color: "#2d3148" },
            horzLines: { color: "#2d3148" },
          },
          timeScale: {
            timeVisible: true,
            secondsVisible: false,
          },
        });

        if (cancelled) {
          try { chart.remove(); } catch {}
          return;
        }

        chartRef.current = chart;

        const candleSeries = chart.addCandlestickSeries({
          upColor: "#10b981",
          downColor: "#ef4444",
          borderDownColor: "#ef4444",
          borderUpColor: "#10b981",
          wickDownColor: "#ef4444",
          wickUpColor: "#10b981",
        });

        const candles = await api.ohlcv(selectedTicker, interval, 200);

        if (cancelled) return;

        if (candles.length > 0) {
          candleSeries.setData(candles);

          try {
            const markers = await api.tickerTrades(selectedTicker, 30);
            if (!cancelled && markers.length > 0) {
              candleSeries.setMarkers(
                markers.filter((m: any) => m.time > 0).sort((a: any, b: any) => a.time - b.time)
              );
            }
          } catch {}

          if (!cancelled) {
            chart.timeScale().fitContent();
          }
        }

        // 리사이즈 대응
        if (!cancelled && containerRef.current) {
          const observer = new ResizeObserver(() => {
            if (containerRef.current && chartRef.current) {
              try { chartRef.current.applyOptions({ width: containerRef.current.clientWidth }); } catch {}
            }
          });
          observer.observe(containerRef.current);
          observerRef.current = observer;
        }
      } catch (e) {
        if (!cancelled) console.error("Chart load error:", e);
      }
      if (!cancelled) setLoading(false);
    }

    loadChart();

    return () => {
      cancelled = true;
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }
      if (chartRef.current) {
        try { chartRef.current.remove(); } catch {}
        chartRef.current = null;
      }
    };
  }, [selectedTicker, interval]);

  if (tickers.length === 0) {
    return (
      <div className="bg-[var(--bg-card)] rounded-xl p-6 text-center text-[var(--text-secondary)]">
        보유 코인이 없어 차트를 표시할 수 없습니다.
      </div>
    );
  }

  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium">캔들차트</h3>
        <div className="flex gap-2">
          <select
            value={selectedTicker}
            onChange={(e) => setSelectedTicker(e.target.value)}
            className="bg-gray-800 text-sm rounded px-2 py-1 border border-gray-700"
          >
            {tickers.map((t) => (
              <option key={t} value={t}>{t.replace("KRW-", "")}</option>
            ))}
          </select>
          <select
            value={interval}
            onChange={(e) => setInterval_(e.target.value)}
            className="bg-gray-800 text-sm rounded px-2 py-1 border border-gray-700"
          >
            <option value="minute5">5분</option>
            <option value="minute15">15분</option>
            <option value="minute60">1시간</option>
            <option value="minute240">4시간</option>
            <option value="day">일봉</option>
          </select>
        </div>
      </div>
      <div ref={containerRef} className="w-full" style={{ minHeight: 350 }}>
        {loading && (
          <div className="flex items-center justify-center h-[350px] text-[var(--text-secondary)]">
            로딩 중...
          </div>
        )}
      </div>
    </div>
  );
}
