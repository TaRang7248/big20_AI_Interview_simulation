"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)]">
      <div className="glass-card max-w-md w-full text-center p-8">
        <div className="text-5xl mb-4">⚠️</div>
        <h2 className="text-xl font-bold text-white mb-2">오류가 발생했습니다</h2>
        <p className="text-sm text-[var(--text-secondary)] mb-6">
          {error.message || "알 수 없는 오류가 발생했습니다."}
        </p>
        <button
          onClick={reset}
          className="btn-gradient px-6 py-2 rounded-lg"
        >
          다시 시도
        </button>
      </div>
    </div>
  );
}
