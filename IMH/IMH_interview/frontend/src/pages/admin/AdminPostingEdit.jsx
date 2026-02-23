import React, { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { jobsApi } from '../../services/api'

export default function AdminPostingEdit() {
    const { postingId } = useParams()
    const navigate = useNavigate()
    const [form, setForm] = useState(null)
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState('')

    useEffect(() => {
        jobsApi.get(postingId)
            .then(res => {
                const j = res.data
                setForm({
                    title: j.title || '',
                    description: j.description || '',
                    location: j.location || '',
                    headcount: j.headcount || '',
                    deadline: j.deadline || '',
                    tags: Array.isArray(j.tags) ? j.tags.join(', ') : '',
                })
            })
            .catch(() => navigate('/admin/postings'))
            .finally(() => setLoading(false))
    }, [postingId])

    function handleChange(e) {
        const { name, value } = e.target
        setForm(f => ({ ...f, [name]: value }))
    }

    async function handleSubmit(e) {
        e.preventDefault()
        setSaving(true)
        setError('')
        try {
            await jobsApi.update(postingId, {
                ...form,
                headcount: form.headcount ? parseInt(form.headcount) : null,
                tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
            })
            navigate(`/admin/postings/${postingId}`)
        } catch (err) {
            setError(err.response?.data?.detail || '수정 중 오류가 발생했습니다.')
        } finally {
            setSaving(false)
        }
    }

    async function handleAction(action) {
        if (!window.confirm(action === 'PUBLISH' ? '공고를 게시하시겠습니까?' : '공고를 조기 마감하시겠습니까?')) return
        setSaving(true)
        try {
            await jobsApi.update(postingId, { action })
            navigate(`/admin/postings/${postingId}`)
        } catch (err) {
            setError(err.response?.data?.detail || '오류가 발생했습니다.')
        } finally {
            setSaving(false)
        }
    }

    if (loading || !form) return <div className="loading"><div className="spinner" /></div>

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">공고 수정</h1>
                <p className="page-subtitle">채용 공고 정보를 수정합니다.</p>
            </div>

            <div style={{ maxWidth: 600 }}>
                <form onSubmit={handleSubmit} className="card">
                    {error && <div className="alert alert-error">{error}</div>}

                    <div className="form-group">
                        <label className="form-label">공고 제목</label>
                        <input name="title" className="form-input" value={form.title} onChange={handleChange} />
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">근무지</label>
                            <input name="location" className="form-input" value={form.location} onChange={handleChange} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">채용 인원</label>
                            <input name="headcount" className="form-input" type="number" value={form.headcount} onChange={handleChange} />
                        </div>
                    </div>

                    <div className="form-group">
                        <label className="form-label">마감일</label>
                        <input name="deadline" className="form-input" type="date" value={form.deadline} onChange={handleChange} />
                    </div>

                    <div className="form-group">
                        <label className="form-label">공고 설명</label>
                        <textarea name="description" className="form-input" style={{ minHeight: 120, resize: 'vertical' }} value={form.description} onChange={handleChange} />
                    </div>

                    <div className="form-group">
                        <label className="form-label">태그</label>
                        <input name="tags" className="form-input" value={form.tags} onChange={handleChange} />
                    </div>

                    <div className="flex gap-4" style={{ marginBottom: 16 }}>
                        <button type="button" className="btn btn-secondary flex-1" onClick={() => navigate(`/admin/postings/${postingId}`)}>취소</button>
                        <button type="submit" className="btn btn-primary flex-1" disabled={saving}>{saving ? '저장 중...' : '저장'}</button>
                    </div>
                </form>

                <div className="card" style={{ marginTop: 16 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, color: 'var(--text-secondary)' }}>공고 상태 변경</div>
                    <div className="flex gap-4">
                        <button className="btn btn-success flex-1" onClick={() => handleAction('PUBLISH')} disabled={saving}>
                            ✅ 게시 (PUBLISH)
                        </button>
                        <button className="btn btn-danger flex-1" onClick={() => handleAction('CLOSE')} disabled={saving}>
                            🔒 조기 마감 (CLOSE)
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
