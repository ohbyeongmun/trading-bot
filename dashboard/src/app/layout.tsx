import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trading Dashboard",
  description: "Upbit 트레이딩봇 실시간 대시보드",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen">
        <div className="flex">
          {/* Sidebar */}
          <nav className="w-56 min-h-screen bg-[var(--bg-secondary)] border-r border-gray-800 p-4 flex flex-col gap-1">
            <h1 className="text-lg font-bold mb-6 px-3">Trading Bot</h1>
            <NavLink href="/" label="대시보드" />
            <NavLink href="/trades" label="거래 내역" />
            <NavLink href="/strategies" label="전략 분석" />
          </nav>

          {/* Main */}
          <main className="flex-1 p-6 overflow-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}

function NavLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="px-3 py-2 rounded-lg text-sm text-[var(--text-secondary)] hover:text-white hover:bg-gray-800 transition-colors"
    >
      {label}
    </Link>
  );
}
