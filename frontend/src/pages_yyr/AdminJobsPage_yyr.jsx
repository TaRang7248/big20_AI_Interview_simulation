import React, { useEffect, useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";

const API_BASE_URL = "http://127.0.0.1:8001";

export default function AdminJobsPage_yyr() {
    const nav = useNavigate();

    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);

    // 폼 상태
    const [jobCode, setJobCode] = useState("");
    const [title, setTitle] = useState("");
    const [status, setStatus] = useState("모집중");
    const [applicants, setApplicants] = useState(0);

    const glass =
        "bg-white/70 backdrop-blur-xl border border-white/60 shadow-[0_20px_40px_-20px_rgba(0,0,0,0.15)] rounded-3xl";

    const fetchJobs = async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE_URL}/admin/jobs`);
            setJobs(res.data?.jobs ?? []);
        } catch (e) {
            console.error(e);
            alert("공고 목록 조회 실패 (백엔드 /admin/jobs 확인)");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchJobs();
    }, []);

    const handleCreate = async (e) => {
        e.preventDefault();

        if (!jobCode.trim() || !title.trim()) {
            alert("job_code / title은 필수입니다.");
            return;
        }

        try {
            await axios.post(`${API_BASE_URL}/admin/jobs`, {
                job_code: jobCode.trim(),
                title: title.trim(),
                status,
                applicants: Number(applicants) || 0,
            });

            alert("등록 완료!");
            setJobCode("");
            setTitle("");
            setStatus("모집중");
            setApplicants(0);

            await fetchJobs();
        } catch (e) {
            console.error(e);
            alert("공고 등록 실패 (백엔드 POST /admin/jobs 확인)");
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-indigo-50 text-slate-900">
            <header className="sticky top-0 z-40 backdrop-blur-xl bg-white/60 border-b border-white/60">
                <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
                    <div>
                        <div className="text-sm font-extrabold">공고 관리</div>
                        <div className="text-[11px] text-slate-500">등록/조회 (MVP)</div>
                    </div>

                    <button
                        onClick={() => nav("/admin")}
                        className="px-3 py-2 rounded-xl bg-slate-900 text-white text-sm font-bold"
                    >
                        대시보드로
                    </button>
                </div>
            </header>

            <main className="max-w-6xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* 등록 폼 */}
                <section className={`lg:col-span-5 ${glass} p-6`}>
                    <div className="text-base font-extrabold">공고 등록</div>
                    <p className="text-sm text-slate-500 mt-2">
                        (MVP) job_code는 유니크. status/applicants는 테스트용.
                    </p>

                    <form onSubmit={handleCreate} className="mt-5 space-y-3">
                        <div>
                            <label className="text-xs font-bold text-slate-600">job_code</label>
                            <input
                                value={jobCode}
                                onChange={(e) => setJobCode(e.target.value)}
                                placeholder="예: JOB-010"
                                className="mt-1 w-full px-3 py-2 rounded-xl border border-slate-200 bg-white"
                            />
                        </div>

                        <div>
                            <label className="text-xs font-bold text-slate-600">title</label>
                            <input
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                placeholder="예: 데이터 분석가 (SQL/BI)"
                                className="mt-1 w-full px-3 py-2 rounded-xl border border-slate-200 bg-white"
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="text-xs font-bold text-slate-600">status</label>
                                <select
                                    value={status}
                                    onChange={(e) => setStatus(e.target.value)}
                                    className="mt-1 w-full px-3 py-2 rounded-xl border border-slate-200 bg-white"
                                >
                                    <option value="모집중">모집중</option>
                                    <option value="마감">마감</option>
                                    <option value="임시저장">임시저장</option>
                                </select>
                            </div>

                            <div>
                                <label className="text-xs font-bold text-slate-600">applicants</label>
                                <input
                                    type="number"
                                    value={applicants}
                                    onChange={(e) => setApplicants(e.target.value)}
                                    className="mt-1 w-full px-3 py-2 rounded-xl border border-slate-200 bg-white"
                                />
                            </div>
                        </div>

                        <button
                            type="submit"
                            className="w-full mt-2 px-4 py-3 rounded-2xl text-sm font-extrabold text-white bg-gradient-to-r from-sky-500 to-violet-500 hover:opacity-95"
                        >
                            등록
                        </button>
                    </form>
                </section>

                {/* 목록 */}
                <section className={`lg:col-span-7 ${glass} p-6`}>
                    <div className="flex items-center justify-between">
                        <div>
                            <div className="text-base font-extrabold">공고 목록</div>
                            <div className="text-sm text-slate-500 mt-1">
                                /admin/jobs GET 결과 표시
                            </div>
                        </div>
                        <button
                            onClick={fetchJobs}
                            className="px-3 py-2 rounded-xl bg-white/70 border border-white/60 hover:bg-white transition text-sm font-bold"
                        >
                            새로고침
                        </button>
                    </div>

                    <div className="mt-5 overflow-x-auto">
                        {loading ? (
                            <div className="text-sm text-slate-500">불러오는 중…</div>
                        ) : (
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="text-left text-slate-500">
                                        <th className="py-2 pr-3">상태</th>
                                        <th className="py-2 pr-3">공고</th>
                                        <th className="py-2 pr-3">지원자</th>
                                        <th className="py-2 pr-3">업데이트</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {jobs.map((j) => (
                                        <tr key={j.job_code} className="border-t border-white/60">
                                            <td className="py-3 pr-3">{j.status}</td>
                                            <td className="py-3 pr-3">
                                                <div className="font-bold text-slate-900">{j.title}</div>
                                                <div className="text-xs text-slate-500">{j.job_code}</div>
                                            </td>
                                            <td className="py-3 pr-3 font-bold">{j.applicants}</td>
                                            <td className="py-3 pr-3 text-slate-600">
                                                {String(j.updated_at).slice(0, 10)}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </section>
            </main>
        </div>
    );
}