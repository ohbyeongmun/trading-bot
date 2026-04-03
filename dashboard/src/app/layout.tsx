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
        <div className="flex flex-col md:flex-row">
          {/* Sidebar: 모바일에서는 상단 가로 바, 데스크톱에서는 좌측 세로 */}
          <nav className="md:w-56 md:min-h-screen bg-[var(--bg-secondary)] border-b md:border-b-0 md:border-r border-gray-800 p-3 md:p-4 flex md:flex-col gap-1 overflow-x-auto">
            <h1 className="text-lg font-bold md:mb-6 px-3 whitespace-nowrap">Trading Bot</h1>
            <NavLink href="/" label="대시보드" />
            <NavLink href="/trades" label="거래 내역" />
            <NavLink href="/strategies" label="전략 분석" />
            <NavLink href="/scanner" label="스캐너" />
          </nav>

          {/* Main */}
          <main className="flex-1 p-4 md:p-6 overflow-auto min-w-0">{children}</main>
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
