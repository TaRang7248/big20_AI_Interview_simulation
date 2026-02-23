import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { jobsApi } from '../../services/api'

export default function AdminPostingNew() {
    const navigate = useNavigate()
    const [form, setForm] = useState({
        title: '', company: '', description: '', location: '',
        headcount: '', deadline: '', tags: '',
        total_question_limit: 10, question_timeout_sec: 120,
        mode: 'ACTUAL',
    })
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    function handleChange(e) {
        const { name, value } = e.target
        setForm(f => ({ ...f, [name]: value }))
    }

    async function handleSubmit(e) {
        e.preventDefault()
        if (!form.title) { setError('공고 제목은 필수입니다.'); return }
        setLoading(true)
        setError('')
        try {
            const payload = {
                ...form,
                headcount: form.headcount ? parseInt(form.headcount) : null,
                total_question_limit: parseInt(form.total_question_limit),
                question_timeout_sec: parseInt(form.question_timeout_sec),
                tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
            }
            await jobsApi.create(payload)
            navigate('/admin/postings')
        } catch (err) {
            setError(err.response?.data?.detail || '공고 등록 중 오류가 발생했습니다.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">신규 공고 등록</h1>
                <p className="page-subtitle">새로운 채용 공고를 작성합니다.</p>
            </div>

            <div style={{ maxWidth: 600 }}>
                <form onSubmit={handleSubmit} className="card">
                    {error && <div className="alert alert-error">{error}</div>}

                    <div className="form-group">
                        <label className="form-label">공고 제목 <span style={{ color: 'var(--danger)' }}>*</span></label>
                        <input name="title" className="form-input" placeholder="직무명/공고 제목" value={form.title} onChange={handleChange} />
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">회사명</label>
                            <input name="company" className="form-input" placeholder="회사명" value={form.company} onChange={handleChange} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">근무지</label>
                            <input name="location" className="form-input" placeholder="서울 강남구" value={form.location} onChange={handleChange} />
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">채용 인원</label>
                            <input name="headcount" className="form-input" type="number" min="1" placeholder="명" value={form.headcount} onChange={handleChange} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">지원 마감일</label>
                            <input name="deadline" className="form-input" type="date" value={form.deadline} onChange={handleChange} />
                        </div>
                    </div>

                    <div className="form-group">
                        <label className="form-label">공고 설명</label>
                        <textarea name="description" className="form-input" style={{ minHeight: 100, resize: 'vertical' }} placeholder="직무 설명, 자격 요건 등" value={form.description} onChange={handleChange} />
                    </div>

                    <div className="form-group">
                        <label className="form-label">태그 (쉼표로 구분)</label>
                        <input name="tags" className="form-input" placeholder="Python, React, 경력 3년" value={form.tags} onChange={handleChange} />
                    </div>

                    <div style={{ borderTop: '1px solid var(--glass-border)', paddingTop: 20, marginTop: 8, marginBottom: 20 }}>
                        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 16, color: 'var(--text-secondary)' }}>면접 설정</div>
                        <div className="form-row">
                            <div className="form-group">
                                <label className="form-label">질문 수</label>
                                <input name="total_question_limit" className="form-input" type="number" min="1" max="20" value={form.total_question_limit} onChange={handleChange} />
                            </div>
                            <div className="form-group">
                                <label className="form-label">답변 제한 시간 (초)</label>
                                <input name="question_timeout_sec" className="form-input" type="number" min="30" value={form.question_timeout_sec} onChange={handleChange} />
                            </div>
                        </div>
                        <div className="form-group">
                            <label className="form-label">면접 모드</label>
                            <select name="mode" className="form-select" value={form.mode} onChange={handleChange}>
                                <option value="ACTUAL">실전 (ACTUAL)</option>
                                <option value="PRACTICE">연습 (PRACTICE)</option>
                            </select>
                        </div>
                    </div>

                    <div className="flex gap-4">
                        <button type="button" className="btn btn-secondary flex-1" onClick={() => navigate('/admin/postings')}>
                            취소
                        </button>
                        <button type="submit" className="btn btn-primary flex-1" disabled={loading}>
                            {loading ? '등록 중...' : '공고 등록'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}
