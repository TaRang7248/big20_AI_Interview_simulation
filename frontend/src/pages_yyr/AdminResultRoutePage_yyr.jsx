// frontend/src/pages_yyr/AdminResultRoutePage_yyr.jsx
import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

export default function AdminResultRoutePage_yyr() {
    const nav = useNavigate();
    const { threadId } = useParams();

    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState("");
    const [data, setData] = useState(null);

    useEffect(() => {
        let alive = true;

        async function run() {
            setLoading(true);
            setErr("");
            setData(null);

            try {
                const res = await fetch(
                    `http://127.0.0.1:8001/report/${encodeURIComponent(threadId)}/result`
                );

                if (!res.ok) {
                    const text = await res.text();
                    throw new Error(`API 오류: ${res.status}\n${text}`);
                }

                const json = await res.json();
                if (!alive) return;
                setData(json);
            } catch (e) {
                if (!alive) return;
                setErr(String(e));
            } finally {
                if (!alive) return;
                setLoading(false);
            }
        }

        if (threadId) run();
        return () => {
            alive = false;
        };
    }, [threadId]);

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900">
            <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-2">
                <button
                    onClick={() => nav("/admin")}
                    className="px-3 py-2 rounded-xl bg-white border font-extrabold"
                >
                    ← 목록으로
                </button>
                <button
                    onClick={() => nav(-1)}
                    className="px-3 py-2 rounded-xl bg-slate-900 text-white font-extrabold"
                >
                    뒤로가기
                </button>

                <div className="ml-auto text-xs text-slate-500">
                    thread_id: <span className="font-bold">{threadId}</span>
                </div>
            </div>

            <div className="max-w-5xl mx-auto px-4 pb-10">
                {loading && (
                    <div className="bg-white border rounded-2xl p-5 font-semibold text-slate-600">
                        결과 불러오는 중...
                    </div>
                )}

                {!loading && err && (
                    <div className="bg-white border rounded-2xl p-5">
                        <div className="font-extrabold text-rose-600">결과를 불러오지 못했어요</div>
                        <pre className="mt-3 text-xs whitespace-pre-wrap text-slate-700">{err}</pre>
                    </div>
                )}

                {!loading && !err && data && (
                    <div className="bg-white border rounded-2xl p-6">
                        <div className="text-lg font-extrabold">관리자 결과</div>
                        <div className="mt-2 text-sm text-slate-600">
                            총점: <span className="font-extrabold">{data.total_score ?? "-"}</span> / 판정:{" "}
                            <span className="font-extrabold">{data.final_result ?? "-"}</span>
                        </div>
                        <div className="mt-4 text-sm text-slate-700 whitespace-pre-wrap">
                            {data.summary ?? "-"}
                        </div>

                        {/* TODO: 여기서 radar/feedback UI로 확장 */}
                    </div>
                )}
            </div>
        </div>
    );
}