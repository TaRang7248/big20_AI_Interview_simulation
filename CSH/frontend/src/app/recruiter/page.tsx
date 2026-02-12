"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/contexts/ToastContext";
import Header from "@/components/common/Header";
import { jobPostingApi, type JobPosting } from "@/lib/api";
import {
  Briefcase, Plus, Edit3, Trash2, Search, X, Loader2,
  CalendarDays, DollarSign, Tag, MapPin, Building2,
  CheckCircle2, XCircle, Clock, BarChart3, Users, FileText,
  ChevronDown, ChevronUp, AlertCircle, Eye, EyeOff,
} from "lucide-react";

// ── 경력 수준 옵션 ──
const EXPERIENCE_OPTIONS = [
  { value: "", label: "전체" },
  { value: "신입", label: "신입" },
  { value: "1~3년", label: "1~3년" },
  { value: "3~5년", label: "3~5년" },
  { value: "5~10년", label: "5~10년" },
  { value: "10년 이상", label: "10년 이상" },
];

// ── 직무 분야 옵션 ──
const CATEGORY_OPTIONS = [
  { value: "", label: "전체" },
  { value: "backend", label: "백엔드" },
  { value: "frontend", label: "프론트엔드" },
  { value: "fullstack", label: "풀스택" },
  { value: "data", label: "데이터/AI" },
  { value: "devops", label: "DevOps/인프라" },
  { value: "mobile", label: "모바일" },
  { value: "security", label: "보안" },
  { value: "etc", label: "기타" },
];

// 직무 분야 라벨 변환 헬퍼
const getCategoryLabel = (value: string) =>
  CATEGORY_OPTIONS.find(o => o.value === value)?.label || value || "미지정";

/**
 * 인사담당자(Recruiter) 전용 대시보드 ─────────────────────
 *
 * 기능:
 * 1. 대시보드 통계 요약 (등록 공고 수, 진행 중/마감 공고, 지원자 수)
 * 2. 면접 공고 등록 (모달 폼)
 * 3. 등록한 공고 목록 관리 (수정, 마감, 삭제)
 * 4. 공고 상세보기 (펼침/접기)
 */
export default function RecruiterDashboard() {
  const { user, token, loading } = useAuth();
  const { toast } = useToast();
  const router = useRouter();

  // ── 공고 목록 상태 ──
  const [postings, setPostings] = useState<JobPosting[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "open" | "closed">("all");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // ── 공고 등록/수정 모달 ──
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({
    title: "", company: "", location: "", job_category: "",
    experience_level: "", description: "", salary_info: "", deadline: "",
  });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  // ── 삭제 확인 ──
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  // ── 모달 overlay 클릭 보호 (드래그 오작동 방지) ──
  // mousedown이 overlay 자체에서 시작했을 때만 모달 닫기 허용
  const overlayMouseDownTarget = useRef<EventTarget | null>(null);

  // ── 인증 + 역할 확인 ──
  useEffect(() => {
    if (!loading && !token) {
      router.push("/");
      return;
    }
    // 지원자(candidate)가 접근하면 일반 대시보드로 리다이렉트
    if (!loading && user && user.role !== "recruiter") {
      router.push("/dashboard");
    }
  }, [loading, token, user, router]);

  // ── 공고 목록 로드 ──
  useEffect(() => {
    if (user?.role === "recruiter") loadPostings();
  }, [user]);

  const loadPostings = async () => {
    setListLoading(true);
    try {
      // 인사담당자 → 전체 상태 공고 조회 (본인 공고만 필터링은 프론트에서)
      const res = await jobPostingApi.list("all");
      // 본인이 등록한 공고만 필터
      setPostings(res.postings.filter(p => p.recruiter_email === user?.email));
    } catch (e) {
      console.error("공고 로드 실패:", e);
    } finally {
      setListLoading(false);
    }
  };

  // ── 통계 계산 ──
  const stats = {
    total: postings.length,
    open: postings.filter(p => p.status === "open").length,
    closed: postings.filter(p => p.status === "closed").length,
    expiringSoon: postings.filter(p => {
      if (!p.deadline || p.status !== "open") return false;
      const d = new Date(p.deadline);
      const now = new Date();
      const diff = (d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
      return diff >= 0 && diff <= 7;
    }).length,
  };

  // ── 공고 필터링 ──
  const filtered = postings.filter(p => {
    // 상태 필터
    if (filterStatus !== "all" && p.status !== filterStatus) return false;
    // 검색어
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      return (
        p.title.toLowerCase().includes(q) ||
        p.company.toLowerCase().includes(q) ||
        (p.description || "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  // ── 모달 열기 (등록 / 수정) ──
  const openCreateModal = () => {
    setEditingId(null);
    setForm({ title: "", company: "", location: "", job_category: "", experience_level: "", description: "", salary_info: "", deadline: "" });
    setFormError("");
    setShowModal(true);
  };

  const openEditModal = (p: JobPosting) => {
    setEditingId(p.id);
    setForm({
      title: p.title,
      company: p.company,
      location: p.location || "",
      job_category: p.job_category || "",
      experience_level: p.experience_level || "",
      description: p.description,
      salary_info: p.salary_info || "",
      deadline: p.deadline || "",
    });
    setFormError("");
    setShowModal(true);
  };

  // ── 공고 저장 (등록 / 수정) ──
  const handleSave = async () => {
    if (!form.title.trim() || !form.company.trim() || !form.description.trim()) {
      setFormError("제목, 회사명, 상세 내용은 필수 항목입니다.");
      return;
    }
    setSaving(true);
    setFormError("");
    try {
      if (editingId) {
        await jobPostingApi.update(editingId, form);
      } else {
        await jobPostingApi.create(form);
      }
      setShowModal(false);
      await loadPostings();
      // CRUD 성공 피드백 (토스트 알림)
      toast.success(editingId ? "공고가 수정되었습니다." : "공고가 등록되었습니다.");
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  };

  // ── 공고 삭제 ──
  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await jobPostingApi.delete(deleteTarget);
      setDeleteTarget(null);
      await loadPostings();
      toast.success("공고가 삭제되었습니다.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "삭제 실패");
    } finally {
      setDeleting(false);
    }
  };

  // ── 공고 상태 토글 (open ↔ closed) ──
  const togglePostingStatus = async (p: JobPosting) => {
    try {
      const newStatus = p.status === "open" ? "closed" : "open";
      await jobPostingApi.update(p.id, { status: newStatus });
      await loadPostings();
      toast.success(newStatus === "open" ? "공고가 재게시되었습니다." : "공고가 마감되었습니다.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "상태 변경 실패");
    }
  };

  // ── 로딩 / 권한 체크 ──
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-[var(--cyan)] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm text-[var(--text-secondary)]">로딩 중...</p>
      </div>
    </div>
  );

  if (!user || user.role !== "recruiter") return null;

  return (
    <div className="min-h-screen">
      <Header />

      <main className="max-w-[1200px] mx-auto px-6 py-8">
        {/* ── 환영 배너 ── */}
        <div className="glass-card mb-8 bg-gradient-to-r from-[rgba(206,147,216,0.08)] to-[rgba(0,217,255,0.06)]">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold mb-2">인사담당자 대시보드 🏢</h1>
              <p className="text-[var(--text-secondary)]">
                안녕하세요, <strong className="text-[var(--cyan)]">{user.name || user.email}</strong>님.
                면접 공고를 등록하고 관리하세요.
              </p>
            </div>
            <button onClick={openCreateModal} className="btn-gradient flex items-center gap-2 text-sm !py-3 !px-6">
              <Plus size={18} /> 새 공고 등록
            </button>
          </div>
        </div>

        {/* ── 통계 카드 ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard icon={<Briefcase size={22} />} label="전체 공고" value={stats.total} color="var(--cyan)" />
          <StatCard icon={<CheckCircle2 size={22} />} label="진행 중" value={stats.open} color="var(--green)" />
          <StatCard icon={<XCircle size={22} />} label="마감" value={stats.closed} color="var(--text-secondary)" />
          <StatCard icon={<Clock size={22} />} label="7일 내 마감" value={stats.expiringSoon} color="var(--warning)" />
        </div>

        {/* ── 검색 + 필터 ── */}
        <div className="glass-card mb-6">
          <div className="flex flex-wrap items-center gap-4">
            {/* 검색 */}
            <div className="relative flex-1 min-w-[240px]">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
              <input
                className="input-field pl-9 !py-2.5 text-sm"
                placeholder="공고 제목, 회사명으로 검색..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
              />
              {searchTerm && (
                <button onClick={() => setSearchTerm("")} className="absolute right-3 top-1/2 -translate-y-1/2">
                  <X size={14} className="text-[var(--text-secondary)]" />
                </button>
              )}
            </div>
            {/* 상태 필터 */}
            <div className="flex gap-2">
              {(["all", "open", "closed"] as const).map(s => (
                <button
                  key={s}
                  onClick={() => setFilterStatus(s)}
                  className={`px-4 py-2 text-sm rounded-lg border transition ${
                    filterStatus === s
                      ? "border-[var(--cyan)] bg-[rgba(0,217,255,0.12)] text-[var(--cyan)]"
                      : "border-[rgba(255,255,255,0.1)] text-[var(--text-secondary)] hover:border-[rgba(0,217,255,0.3)]"
                  }`}
                >
                  {s === "all" ? "전체" : s === "open" ? "진행 중" : "마감"}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── 공고 목록 ── */}
        {listLoading ? (
          <div className="text-center py-16">
            <Loader2 size={32} className="animate-spin text-[var(--cyan)] mx-auto mb-3" />
            <p className="text-sm text-[var(--text-secondary)]">공고 목록을 불러오는 중...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 glass-card">
            <Briefcase size={48} className="mx-auto mb-4 text-[var(--text-secondary)] opacity-40" />
            <p className="text-[var(--text-secondary)] mb-4">
              {postings.length === 0
                ? "아직 등록한 공고가 없습니다."
                : "검색 결과가 없습니다."}
            </p>
            {postings.length === 0 && (
              <button onClick={openCreateModal} className="btn-gradient text-sm !py-2 !px-6">
                첫 공고 등록하기
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map(p => (
              <div key={p.id} className="glass-card hover:border-[rgba(0,217,255,0.3)] transition-all">
                <div className="flex items-start justify-between gap-4">
                  {/* 좌측 정보 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      {/* 상태 뱃지 */}
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full ${
                        p.status === "open"
                          ? "bg-[rgba(0,255,136,0.12)] text-[var(--green)] border border-[rgba(0,255,136,0.3)]"
                          : "bg-[rgba(255,255,255,0.06)] text-[var(--text-secondary)] border border-[rgba(255,255,255,0.1)]"
                      }`}>
                        {p.status === "open" ? <Eye size={12} /> : <EyeOff size={12} />}
                        {p.status === "open" ? "진행 중" : "마감"}
                      </span>
                      <h3 className="text-lg font-semibold truncate">{p.title}</h3>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-[var(--text-secondary)]">
                      <span className="flex items-center gap-1"><Building2 size={14} /> {p.company}</span>
                      {p.location && <span className="flex items-center gap-1"><MapPin size={14} /> {p.location}</span>}
                      {p.job_category && <span className="flex items-center gap-1"><Tag size={14} /> {getCategoryLabel(p.job_category)}</span>}
                      {p.experience_level && <span className="flex items-center gap-1"><Users size={14} /> {p.experience_level}</span>}
                      {p.deadline && (
                        <span className={`flex items-center gap-1 ${
                          new Date(p.deadline) < new Date() ? "text-[var(--danger)]" : ""
                        }`}>
                          <CalendarDays size={14} /> 마감 {p.deadline}
                        </span>
                      )}
                      {p.salary_info && <span className="flex items-center gap-1"><DollarSign size={14} /> {p.salary_info}</span>}
                    </div>
                  </div>

                  {/* 우측 액션 버튼 */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {/* 상태 토글 */}
                    <button
                      onClick={() => togglePostingStatus(p)}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition ${
                        p.status === "open"
                          ? "border-[rgba(255,193,7,0.4)] text-[var(--warning)] hover:bg-[rgba(255,193,7,0.1)]"
                          : "border-[rgba(0,255,136,0.4)] text-[var(--green)] hover:bg-[rgba(0,255,136,0.1)]"
                      }`}
                      title={p.status === "open" ? "마감 처리" : "다시 열기"}
                    >
                      {p.status === "open" ? "마감" : "재오픈"}
                    </button>
                    {/* 수정 */}
                    <button
                      onClick={() => openEditModal(p)}
                      className="p-2 rounded-lg border border-[rgba(0,217,255,0.3)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.1)] transition"
                      title="수정"
                    >
                      <Edit3 size={14} />
                    </button>
                    {/* 삭제 */}
                    <button
                      onClick={() => setDeleteTarget(p.id)}
                      className="p-2 rounded-lg border border-[rgba(255,82,82,0.3)] text-[var(--danger)] hover:bg-[rgba(255,82,82,0.1)] transition"
                      title="삭제"
                    >
                      <Trash2 size={14} />
                    </button>
                    {/* 상세 토글 */}
                    <button
                      onClick={() => setExpandedId(expandedId === p.id ? null : p.id)}
                      className="p-2 rounded-lg border border-[rgba(255,255,255,0.1)] text-[var(--text-secondary)] hover:border-[rgba(0,217,255,0.3)] transition"
                      title="상세 보기"
                    >
                      {expandedId === p.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                  </div>
                </div>

                {/* 펼쳐진 상세 내용 */}
                {expandedId === p.id && (
                  <div className="mt-4 pt-4 border-t border-[rgba(255,255,255,0.06)]">
                    <p className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap leading-relaxed">{p.description}</p>
                    <div className="flex gap-4 mt-3 text-xs text-[var(--text-secondary)]">
                      {p.created_at && <span>등록일: {new Date(p.created_at).toLocaleDateString("ko-KR")}</span>}
                      {p.updated_at && <span>수정일: {new Date(p.updated_at).toLocaleDateString("ko-KR")}</span>}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>

      {/* ═══════ 등록/수정 모달 ═══════ */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onMouseDown={e => { overlayMouseDownTarget.current = e.target; }}
          onClick={e => {
            // mousedown과 click 모두 overlay 자체에서 발생했을 때만 닫기
            // (폼 내부 드래그가 overlay로 빠져나가는 오작동 방지)
            if (e.target === e.currentTarget && overlayMouseDownTarget.current === e.currentTarget) {
              setShowModal(false);
            }
          }}
        >
          <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto glass-card !bg-[var(--bg-card)]">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold">{editingId ? "공고 수정" : "새 공고 등록"}</h2>
              <button onClick={() => setShowModal(false)} className="p-1 hover:bg-[rgba(255,255,255,0.05)] rounded-lg transition">
                <X size={20} className="text-[var(--text-secondary)]" />
              </button>
            </div>

            <div className="space-y-4">
              {/* 제목 */}
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">공고 제목 <span className="text-[var(--danger)]">*</span></label>
                <input className="input-field" placeholder="예: 백엔드 개발자 채용" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
              </div>

              {/* 회사명 + 근무지 */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-[var(--text-secondary)] mb-1">회사명 <span className="text-[var(--danger)]">*</span></label>
                  <input className="input-field" placeholder="예: (주)테크컴퍼니" value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm text-[var(--text-secondary)] mb-1">근무지</label>
                  <input className="input-field" placeholder="예: 서울 강남구" value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} />
                </div>
              </div>

              {/* 직무분야 + 경력수준 */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-[var(--text-secondary)] mb-1">직무 분야</label>
                  <select className="input-field" value={form.job_category} onChange={e => setForm({ ...form, job_category: e.target.value })}>
                    {CATEGORY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-[var(--text-secondary)] mb-1">경력 수준</label>
                  <select className="input-field" value={form.experience_level} onChange={e => setForm({ ...form, experience_level: e.target.value })}>
                    {EXPERIENCE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
              </div>

              {/* 급여 + 마감일 */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-[var(--text-secondary)] mb-1">급여 정보</label>
                  <input className="input-field" placeholder="예: 4,000~6,000만원" value={form.salary_info} onChange={e => setForm({ ...form, salary_info: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm text-[var(--text-secondary)] mb-1">마감일</label>
                  <input className="input-field" type="date" value={form.deadline} onChange={e => setForm({ ...form, deadline: e.target.value })} />
                </div>
              </div>

              {/* 상세 내용 */}
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">상세 내용 <span className="text-[var(--danger)]">*</span></label>
                <textarea
                  className="input-field min-h-[180px] resize-y"
                  placeholder={"직무 설명, 자격 요건, 우대 사항, 복리후생 등을 입력해주세요.\n\n예:\n• 주요 업무: FastAPI/Django 기반 REST API 개발\n• 자격 요건: Python 3년 이상, RDBMS 경험\n• 우대 사항: AWS, Docker, CI/CD 경험"}
                  value={form.description}
                  onChange={e => setForm({ ...form, description: e.target.value })}
                />
              </div>

              {/* 에러 메시지 */}
              {formError && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-[rgba(255,82,82,0.1)] text-[var(--danger)] text-sm">
                  <AlertCircle size={16} /> {formError}
                </div>
              )}

              {/* 버튼 */}
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setShowModal(false)} className="px-5 py-2.5 text-sm rounded-lg border border-[rgba(255,255,255,0.15)] text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)] transition">
                  취소
                </button>
                <button onClick={handleSave} disabled={saving} className="btn-gradient text-sm !py-2.5 !px-6 flex items-center gap-2">
                  {saving ? <Loader2 size={16} className="animate-spin" /> : editingId ? <Edit3 size={16} /> : <Plus size={16} />}
                  {saving ? "저장 중..." : editingId ? "수정 완료" : "등록하기"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ═══════ 삭제 확인 모달 ═══════ */}
      {deleteTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onMouseDown={e => { overlayMouseDownTarget.current = e.target; }}
          onClick={e => {
            if (e.target === e.currentTarget && overlayMouseDownTarget.current === e.currentTarget) {
              setDeleteTarget(null);
            }
          }}
        >
          <div className="w-full max-w-md glass-card !bg-[var(--bg-card)] text-center">
            <AlertCircle size={48} className="mx-auto mb-4 text-[var(--danger)]" />
            <h3 className="text-lg font-bold mb-2">공고를 삭제하시겠습니까?</h3>
            <p className="text-sm text-[var(--text-secondary)] mb-6">이 작업은 되돌릴 수 없습니다.</p>
            <div className="flex justify-center gap-3">
              <button onClick={() => setDeleteTarget(null)} className="px-5 py-2.5 text-sm rounded-lg border border-[rgba(255,255,255,0.15)] text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)] transition">
                취소
              </button>
              <button onClick={handleDelete} disabled={deleting} className="px-5 py-2.5 text-sm rounded-lg bg-[rgba(255,82,82,0.2)] border border-[rgba(255,82,82,0.4)] text-[var(--danger)] hover:bg-[rgba(255,82,82,0.3)] transition flex items-center gap-2">
                {deleting ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                {deleting ? "삭제 중..." : "삭제"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── 통계 카드 컴포넌트 ── */
function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number; color: string }) {
  return (
    <div className="glass-card flex items-center gap-4">
      <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${color}18` }}>
        <span style={{ color }}>{icon}</span>
      </div>
      <div>
        <p className="text-2xl font-bold">{value}</p>
        <p className="text-xs text-[var(--text-secondary)]">{label}</p>
      </div>
    </div>
  );
}
