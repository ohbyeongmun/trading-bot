const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "X-API-Key": API_KEY,
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface DashboardData {
  total_balance: number;
  daily_pnl: number;
  daily_pnl_pct: number;
  weekly_pnl_pct: number;
  monthly_pnl_pct: number;
  open_positions: number;
  bot_status: "running" | "stopped" | "paused";
  market_regime: "bull" | "bear" | "sideways";
}

export interface Position {
  id: number;
  ticker: string;
  entry_price: number;
  volume: number;
  amount_krw: number;
  strategy: string;
  entry_time: string;
  highest_price: number;
  current_price: number | null;
  pnl_pct: number | null;
}

export interface Trade {
  id: number;
  ticker: string;
  side: string;
  amount_krw: number;
  price: number;
  strategy: string;
  reason: string;
  timestamp: string;
}

export interface StrategyStats {
  name: string;
  total_trades: number;
  win_rate: number;
  avg_profit_pct: number;
  avg_loss_pct: number;
  total_pnl: number;
}

export interface DailyReport {
  date: string;
  starting_balance: number;
  ending_balance: number;
  pnl: number;
  pnl_pct: number;
  trades_count: number;
  win_rate: number;
  max_drawdown: number;
}

export const api = {
  dashboard: () => fetchApi<DashboardData>("/api/dashboard"),
  positions: () => fetchApi<Position[]>("/api/positions"),
  trades: (limit = 50) => fetchApi<Trade[]>(`/api/trades?limit=${limit}`),
  strategies: () => fetchApi<StrategyStats[]>("/api/strategies"),
  dailyReports: (limit = 30) => fetchApi<DailyReport[]>(`/api/daily-reports?limit=${limit}`),
  botStart: () => fetchApi("/api/bot/start", { method: "POST" }),
  botStop: () => fetchApi("/api/bot/stop", { method: "POST" }),
};
