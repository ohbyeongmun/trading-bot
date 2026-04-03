"use client";

import { useEffect, useState } from "react";

interface ToastItem {
  id: number;
  type: "buy" | "sell" | "stop" | "info";
  message: string;
  timestamp: number;
}

let toastId = 0;

const TOAST_COLORS = {
  buy: "bg-green-600/90 border-green-500",
  sell: "bg-red-600/90 border-red-500",
  stop: "bg-yellow-600/90 border-yellow-500",
  info: "bg-blue-600/90 border-blue-500",
};

const TOAST_ICONS = {
  buy: "▲",
  sell: "▼",
  stop: "⚠",
  info: "ℹ",
};

export function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = (type: ToastItem["type"], message: string) => {
    const id = ++toastId;
    setToasts((prev) => [...prev.slice(-4), { id, type, message, timestamp: Date.now() }]);

    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  return { toasts, addToast };
}

export function ToastContainer({ toasts }: { toasts: ToastItem[] }) {
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 w-80">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`${TOAST_COLORS[toast.type]} border rounded-lg px-4 py-3 shadow-lg animate-slide-in backdrop-blur-sm`}
        >
          <div className="flex items-center gap-2">
            <span className="text-lg">{TOAST_ICONS[toast.type]}</span>
            <p className="text-sm text-white font-medium">{toast.message}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
