"use client";

export function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: "bg-green-500/20 text-green-400",
    watching: "bg-blue-500/20 text-blue-400",
    circuit_breaker: "bg-red-500/20 text-red-400",
    stopped: "bg-red-500/20 text-red-400",
    paused: "bg-yellow-500/20 text-yellow-400",
    bull: "bg-green-500/20 text-green-400",
    bear: "bg-red-500/20 text-red-400",
    sideways: "bg-gray-500/20 text-gray-400",
  };

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] || "bg-gray-700 text-gray-300"}`}>
      {status.toUpperCase()}
    </span>
  );
}
