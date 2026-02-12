"use client";
import { useState, useEffect, useRef, useId } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/common/Header";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/contexts/ToastContext";
import { jobPostingApi, type JobPosting } from "@/lib/api";
import {
  Briefcase, MapPin, Clock, Building2, Plus, Edit3, Trash2,
  Search, Filter, X, ChevronDown, ChevronUp, Loader2, CalendarDays,
  DollarSign, Tag, AlertCircle,
} from "lucide-react";

/**
 * 지원 공고 페이지
 * - 지원자(candidate): 공고 목록 열람 + 상세 보기
 * - 인사담당자(recruiter): 공고 등록 / 수정 / 삭제 관리
 */

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

export default function JobPostingsPage() {
  const { user, token, loading } = useAuth();
  const { toast } = useToast();
  const router = useRouter();

  // ── 공고 목록 상태 ──
  const [postings, setPostings] = useState<JobPosting[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [filterExperience, setFilterExperience] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // ── 공고 등록/수정 모달 상태 ──
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({
    title: "", company: "", location: "", job_category: "",
    experience_level: "", description: "", salary_info: "", deadline: "",
  });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  // ── 삭제 확인 모달 ──
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  // ── 접근성: 모달 ARIA ID + overlay ref ──
  const formModalTitleId = useId();
  const deleteModalTitleId = useId();
  const overlayMouseDownTarget = useRef<EventTarget | null>(null);

  // ── 접근성: 모달 열림 시 Escape 키 닫기 + body 스크롤 잠금 ──
  const isAnyModalOpen = showModal || deleteTarget !== null;
  useEffect(() => {
    if (!isAnyModalOpen) return;
    // body 스크롤 잠금 (모달 뒤 배경 스크롤 방지)
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        // 삭제 모달이 열려 있으면 삭제 모달 먼저 닫기
        if (deleteTarget !== null) setDeleteTarget(null);
        else if (showModal) setShowModal(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isAnyModalOpen, deleteTarget, showModal]);

  // 인증 확인 — loading 완료 후에만 리다이렉트 (sessionStorage 복원 대기)
  useEffect(() => {
    if (!loading && !token) {
      router.push("/");
    }
  }, [loading, token, router]);

  // 공고 목록 로드
  useEffect(() => {
    loadPostings();
  }, []);

  const loadPostings = async () => {
    setListLoading(true);
    try {
      // 인사담당자는 본인 공고 관리용으로 전체 목록(open+closed), 지원자는 open만
      const status = user?.role === "recruiter" ? "all" : "open";
      const res = await jobPostingApi.list(status);
      setPostings(res.postings);
    } catch (e) {
      console.error("공고 로드 실패:", e);
    } finally {
      setListLoading(false);
    }
  };

  // ── 검색 + 필터링 ──
  const filtered = postings.filter(p => {
    // 인사담당자 → 본인 공고만 표시
    if (user?.role === "recruiter" && p.recruiter_email !== user.email) return false;
    // 검색어 필터
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      if (!p.title.toLowerCase().includes(q) && !p.company.toLowerCase().includes(q) && !(p.description || "").toLowerCase().includes(q)) {
        return false;
      }
    }
    // 직무 분야 필터
    if (filterCategory && p.job_category !== filterCategory) return false;
    // 경력 수준 필터
    if (filterExperience && p.experience_level !== filterExperience) return false;
    return true;
  });

  // ── 공고 등록/수정 모달 열기 ──
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

  // ── 저장 (등록 / 수정) ──
  const handleSave = async () => {
    if (!form.title.trim()) { setFormError("공고 제목을 입력해주세요."); return; }
    if (!form.company.trim()) { setFormError("회사명을 입력해주세요."); return; }
    if (!form.description.trim()) { setFormError("상세 내용을 입력해주세요."); return; }

    setSaving(true);
    setFormError("");
    try {
      if (editingId) {
        // 수정
        await jobPostingApi.update(editingId, form);
      } else {
        // 신규 등록
        await jobPostingApi.create(form);
      }
      setShowModal(false);
      await loadPostings();  // 목록 새로고침
      // CRUD 성공 피드백 (토스트 알림)
      toast.success(editingId ? "공고가 수정되었습니다." : "공고가 등록되었습니다.");
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  };

  // ── 삭제 ──
  const handleDelete = async () => {
    if (deleteTarget == null) return;
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
  const toggleStatus = async (p: JobPosting) => {
    try {
      const newStatus = p.status === "open" ? "closed" : "open";
      await jobPostingApi.update(p.id, { status: newStatus });
      await loadPostings();
      toast.success(newStatus === "open" ? "공고가 재게시되었습니다." : "공고가 마감되었습니다.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "상태 변경 실패");
    }
  };

  // 인증 상태 로딩 중이면 로딩 화면 표시
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-[var(--cyan)] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm text-[var(--text-secondary)]">로딩 중...</p>
      </div>
    </div>
  );

  if (!user) return null;

  const isRecruiter = user.role === "recruiter";

  return (
    <div className="min-h-screen">
      <Header />

      <main className="max-w-[1100px] mx-auto px-6 py-8">
        {/* ── 페이지 헤더 ── */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <Briefcase size={28} className="text-[var(--cyan)]" />
              {isRecruiter ? "공고 관리" : "지원 공고"}
            </h1>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              {isRecruiter
                ? "면접 공고를 등록하고 관리할 수 있습니다."
                : "채용 공고를 확인하고 면접을 준비하세요."}
            </p>
          </div>
          {/* 인사담당자: 공고 등록 버튼 */}
          {isRecruiter && (
            <button
              onClick={openCreateModal}
              className="btn-gradient flex items-center gap-2 !py-2.5 !px-5 rounded-xl"
            >
              <Plus size={18} /> 공고 등록
            </button>
          )}
        </div>

        {/* ── 검색 + 필터 영역 ── */}
        <div className="glass-card mb-6">
          <div className="flex flex-col md:flex-row gap-3">
            {/* 검색바 */}
            <div className="flex-1 relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
              <input
                type="text"
                placeholder="공고 제목, 회사명, 내용으로 검색..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="input-field !pl-10 w-full"
              />
            </div>
            {/* 직무 분야 필터 */}
            <select
              value={filterCategory}
              onChange={e => setFilterCategory(e.target.value)}
              className="input-field min-w-[140px]"
            >
              {CATEGORY_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            {/* 경력 수준 필터 */}
            <select
              value={filterExperience}
              onChange={e => setFilterExperience(e.target.value)}
              className="input-field min-w-[120px]"
            >
              {EXPERIENCE_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* ── 공고 목록 ── */}
        {listLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="animate-spin text-[var(--cyan)]" size={32} />
          </div>
        ) : filtered.length === 0 ? (
          <div className="glass-card text-center py-16">
            <AlertCircle size={40} className="mx-auto mb-4 text-[var(--text-secondary)]" />
            <p className="text-[var(--text-secondary)]">
              {isRecruiter ? "등록된 공고가 없습니다. 새 공고를 등록해보세요." : "현재 열린 공고가 없습니다."}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map(p => (
              <div
                key={p.id}
                className={`glass-card transition-all duration-200 hover:border-[rgba(0,217,255,0.3)] ${
                  p.status === "closed" ? "opacity-60" : ""
                }`}
              >
                {/* 공고 헤더 (클릭으로 상세 토글) */}
                <div
                  className="flex items-start justify-between cursor-pointer"
                  onClick={() => setExpandedId(expandedId === p.id ? null : p.id)}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      {/* 상태 뱃지 */}
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        p.status === "open"
                          ? "bg-[rgba(0,255,136,0.12)] text-[var(--green)] border border-[rgba(0,255,136,0.25)]"
                          : "bg-[rgba(255,82,82,0.12)] text-[var(--danger)] border border-[rgba(255,82,82,0.25)]"
                      }`}>
                        {p.status === "open" ? "모집중" : "마감"}
                      </span>
                      {/* 직무 분야 */}
                      {p.job_category && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-[rgba(0,217,255,0.1)] text-[var(--cyan)] border border-[rgba(0,217,255,0.2)]">
                          {CATEGORY_OPTIONS.find(c => c.value === p.job_category)?.label || p.job_category}
                        </span>
                      )}
                      {/* 경력 수준 */}
                      {p.experience_level && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-[rgba(206,147,216,0.1)] text-[#ce93d8] border border-[rgba(206,147,216,0.2)]">
                          {p.experience_level}
                        </span>
                      )}
                    </div>
                    {/* 제목 */}
                    <h3 className="text-lg font-semibold truncate">{p.title}</h3>
                    {/* 회사 + 위치 + 마감일 */}
                    <div className="flex items-center gap-4 mt-1 text-sm text-[var(--text-secondary)]">
                      <span className="flex items-center gap-1">
                        <Building2 size={14} /> {p.company}
                      </span>
                      {p.location && (
                        <span className="flex items-center gap-1">
                          <MapPin size={14} /> {p.location}
                        </span>
                      )}
                      {p.deadline && (
                        <span className="flex items-center gap-1">
                          <CalendarDays size={14} /> ~{p.deadline}
                        </span>
                      )}
                    </div>
                  </div>
                  {/* 확장/축소 아이콘 */}
                  <div className="ml-4 flex-shrink-0 mt-1">
                    {expandedId === p.id
                      ? <ChevronUp size={20} className="text-[var(--text-secondary)]" />
                      : <ChevronDown size={20} className="text-[var(--text-secondary)]" />}
                  </div>
                </div>

                {/* 상세 내용 (확장 시) */}
                {expandedId === p.id && (
                  <div className="mt-4 pt-4 border-t border-[rgba(255,255,255,0.06)]">
                    {/* 급여 정보 */}
                    {p.salary_info && (
                      <div className="flex items-center gap-2 mb-3 text-sm">
                        <DollarSign size={14} className="text-[var(--green)]" />
                        <span className="text-[var(--green)]">{p.salary_info}</span>
                      </div>
                    )}
                    {/* 상세 설명 */}
                    <div className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap leading-relaxed mb-4">
                      {p.description}
                    </div>
                    {/* 등록일 */}
                    <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                      <Clock size={12} />
                      등록일: {p.created_at ? new Date(p.created_at).toLocaleDateString("ko-KR") : "-"}
                    </div>

                    {/* 인사담당자: 관리 버튼 */}
                    {isRecruiter && p.recruiter_email === user.email && (
                      <div className="flex items-center gap-2 mt-4 pt-3 border-t border-[rgba(255,255,255,0.06)]">
                        <button
                          onClick={(e) => { e.stopPropagation(); openEditModal(p); }}
                          className="flex items-center gap-1 px-4 py-2 text-sm rounded-lg border border-[rgba(0,217,255,0.3)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.08)] transition"
                        >
                          <Edit3 size={14} /> 수정
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleStatus(p); }}
                          className={`flex items-center gap-1 px-4 py-2 text-sm rounded-lg border transition ${
                            p.status === "open"
                              ? "border-[rgba(255,193,7,0.3)] text-[var(--warning)] hover:bg-[rgba(255,193,7,0.08)]"
                              : "border-[rgba(0,255,136,0.3)] text-[var(--green)] hover:bg-[rgba(0,255,136,0.08)]"
                          }`}
                        >
                          {p.status === "open" ? "마감하기" : "다시 열기"}
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setDeleteTarget(p.id); }}
                          className="flex items-center gap-1 px-4 py-2 text-sm rounded-lg border border-[rgba(255,82,82,0.3)] text-[var(--danger)] hover:bg-[rgba(255,82,82,0.08)] transition"
                        >
                          <Trash2 size={14} /> 삭제
                        </button>
                      </div>
                    )}

                    {/* 지원자: 면접 시작 버튼 */}
                    {!isRecruiter && p.status === "open" && (
                      <div className="mt-4 pt-3 border-t border-[rgba(255,255,255,0.06)]">
                        <button
                          onClick={() => router.push(`/interview?job_posting_id=${p.id}`)}
                          className="btn-gradient !py-2.5 !px-6 rounded-xl text-sm"
                        >
                          🎥 이 공고로 면접 연습하기
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>

      {/* ════════════ 공고 등록/수정 모달 ════════════ */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onMouseDown={e => { overlayMouseDownTarget.current = e.target; }}
          onClick={e => {
            if (e.target === e.currentTarget && overlayMouseDownTarget.current === e.currentTarget) {
              setShowModal(false);
            }
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={formModalTitleId}
            className="glass-card w-full max-w-2xl max-h-[90vh] overflow-y-auto border border-[rgba(0,217,255,0.2)]"
          >
            {/* 모달 헤더 */}
            <div className="flex items-center justify-between mb-6">
              <h2 id={formModalTitleId} className="text-xl font-bold">
                {editingId ? "공고 수정" : "새 공고 등록"}
              </h2>
              <button
                onClick={() => setShowModal(false)}
                className="p-2 rounded-lg hover:bg-[rgba(255,255,255,0.05)] transition"
              >
                <X size={20} />
              </button>
            </div>

            {/* 폼 필드들 */}
            <div className="space-y-4">
              {/* 공고 제목 */}
              <div>
                <label className="block text-sm font-medium mb-1.5">
                  공고 제목 <span className="text-[var(--danger)]">*</span>
                </label>
                <input
                  type="text"
                  value={form.title}
                  onChange={e => setForm({ ...form, title: e.target.value })}
                  placeholder="예: 백엔드 개발자 채용"
                  className="input-field w-full"
                />
              </div>

              {/* 회사명 + 근무지 (2열) */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1.5">
                    회사명 <span className="text-[var(--danger)]">*</span>
                  </label>
                  <input
                    type="text"
                    value={form.company}
                    onChange={e => setForm({ ...form, company: e.target.value })}
                    placeholder="예: (주)테크컴퍼니"
                    className="input-field w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">근무지</label>
                  <input
                    type="text"
                    value={form.location}
                    onChange={e => setForm({ ...form, location: e.target.value })}
                    placeholder="예: 서울 강남구"
                    className="input-field w-full"
                  />
                </div>
              </div>

              {/* 직무 분야 + 경력 수준 (2열) */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1.5">직무 분야</label>
                  <select
                    value={form.job_category}
                    onChange={e => setForm({ ...form, job_category: e.target.value })}
                    className="input-field w-full"
                  >
                    <option value="">선택 안 함</option>
                    {CATEGORY_OPTIONS.filter(c => c.value).map(c => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">경력 수준</label>
                  <select
                    value={form.experience_level}
                    onChange={e => setForm({ ...form, experience_level: e.target.value })}
                    className="input-field w-full"
                  >
                    <option value="">선택 안 함</option>
                    {EXPERIENCE_OPTIONS.filter(o => o.value).map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* 급여 정보 + 마감일 (2열) */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1.5">급여 정보</label>
                  <input
                    type="text"
                    value={form.salary_info}
                    onChange={e => setForm({ ...form, salary_info: e.target.value })}
                    placeholder="예: 4,000만 ~ 6,000만원"
                    className="input-field w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">마감일</label>
                  <input
                    type="date"
                    value={form.deadline}
                    onChange={e => setForm({ ...form, deadline: e.target.value })}
                    className="input-field w-full"
                  />
                </div>
              </div>

              {/* 상세 내용 */}
              <div>
                <label className="block text-sm font-medium mb-1.5">
                  상세 내용 <span className="text-[var(--danger)]">*</span>
                </label>
                <textarea
                  value={form.description}
                  onChange={e => setForm({ ...form, description: e.target.value })}
                  placeholder={"직무 설명, 자격 요건, 우대 사항, 복리후생 등을 작성해주세요.\n\n예:\n[주요 업무]\n- FastAPI 기반 백엔드 개발\n- PostgreSQL 데이터베이스 설계\n\n[자격 요건]\n- Python 3년 이상 경력\n- REST API 설계 경험"}
                  rows={8}
                  className="input-field w-full resize-none"
                />
              </div>

              {/* 에러 메시지 */}
              {formError && (
                <p className="text-sm text-[var(--danger)] flex items-center gap-1">
                  <AlertCircle size={14} /> {formError}
                </p>
              )}

              {/* 버튼 */}
              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setShowModal(false)}
                  className="px-5 py-2.5 text-sm rounded-xl border border-[rgba(255,255,255,0.1)] hover:bg-[rgba(255,255,255,0.05)] transition"
                >
                  취소
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="btn-gradient flex items-center gap-2 !py-2.5 !px-6 rounded-xl disabled:opacity-50"
                >
                  {saving ? <Loader2 size={16} className="animate-spin" /> : null}
                  {editingId ? "수정 완료" : "공고 등록"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ════════════ 삭제 확인 모달 ════════════ */}
      {deleteTarget !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onMouseDown={e => { overlayMouseDownTarget.current = e.target; }}
          onClick={e => {
            if (e.target === e.currentTarget && overlayMouseDownTarget.current === e.currentTarget) {
              setDeleteTarget(null);
            }
          }}
        >
          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby={deleteModalTitleId}
            className="glass-card w-full max-w-md border border-[rgba(255,82,82,0.3)]"
          >
            <h3 id={deleteModalTitleId} className="text-lg font-bold mb-3">공고 삭제 확인</h3>
            <p className="text-sm text-[var(--text-secondary)] mb-6">
              이 공고를 삭제하시겠습니까? 삭제된 공고는 복구할 수 없습니다.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteTarget(null)}
                className="px-5 py-2.5 text-sm rounded-xl border border-[rgba(255,255,255,0.1)] hover:bg-[rgba(255,255,255,0.05)] transition"
              >
                취소
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-2 px-5 py-2.5 text-sm rounded-xl bg-[rgba(255,82,82,0.2)] text-[var(--danger)] border border-[rgba(255,82,82,0.3)] hover:bg-[rgba(255,82,82,0.3)] transition disabled:opacity-50"
              >
                {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                삭제
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
