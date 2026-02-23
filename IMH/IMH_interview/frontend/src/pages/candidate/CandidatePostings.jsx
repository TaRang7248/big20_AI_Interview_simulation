import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { jobsApi, interviewsApi } from '../../services/api'

function StatusBadge({ status }) {
    const map = {
        PUBLISHED: { label: '모집중', cls: 'badge-published' },
        DRAFT: { label: '준비중', cls: 'badge-draft' },
        CLOSED: { label: '마감', cls: 'badge-closed' },
    }
    const { label, cls } = map[status] || { label: status, cls: '' }
    return <span className={`badge ${cls}`}>{label}</span>
}

export default function CandidatePostings() {
    const [jobs, setJobs] = useState([])
    const [loading, setLoading] = useState(true)
    const [applying, setApplying] = useState(null)
    const navigate = useNavigate()

    useEffect(() => {
        jobsApi.list()
            .then(res => setJobs(res.data))
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [])

    async function handleApply(job) {
        if (job.status !== 'PUBLISHED') return
        setApplying(job.job_id)
        try {
            const res = await interviewsApi.create(job.job_id)
            const { session_id } = res.data
            navigate(`/candidate/device-check?sessionId=${session_id}`)
        } catch (err) {
            alert(err.response?.data?.detail || '면접 신청 중 오류가 발생했습니다.')
        } finally {
            setApplying(null)
        }
    }

    if (loading) {
        return <div className="loading"><div className="spinner" />공고 불러오는 중...</div>
    }

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">채용 공고</h1>
                <p className="page-subtitle">현재 모집 중인 채용 공고를 확인하고 면접을 신청하세요.</p>
            </div>

            {jobs.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-icon">📋</div>
                    <p>현재 등록된 공고가 없습니다.</p>
                </div>
            ) : (
                <div className="card-grid">
                    {jobs.map(job => (
                        <div key={job.job_id} className="card" style={{ cursor: 'default' }}>
                            <div className="flex justify-between items-center mb-4">
                                <StatusBadge status={job.status} />
                                {job.deadline && (
                                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                                        ~{job.deadline}
                                    </span>
                                )}
                            </div>

                            <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>{job.title}</h3>
                            {job.company && (
                                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 4 }}>🏢 {job.company}</div>
                            )}
                            {job.location && (
                                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 4 }}>📍 {job.location}</div>
                            )}
                            {job.headcount && (
                                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>👥 {job.headcount}명 채용</div>
                            )}

                            {job.description && (
                                <p style={{
                                    fontSize: 13,
                                    color: 'var(--text-secondary)',
                                    marginBottom: 16,
                                    display: '-webkit-box',
                                    WebkitLineClamp: 3,
                                    WebkitBoxOrient: 'vertical',
                                    overflow: 'hidden',
                                }}>
                                    {job.description}
                                </p>
                            )}

                            {job.tags && job.tags.length > 0 && (
                                <div className="flex gap-2" style={{ flexWrap: 'wrap', marginBottom: 16 }}>
                                    {job.tags.map(tag => (
                                        <span key={tag} style={{
                                            fontSize: 11, padding: '3px 8px',
                                            background: 'var(--glass)',
                                            border: '1px solid var(--glass-border)',
                                            borderRadius: 100,
                                            color: 'var(--text-muted)',
                                        }}>
                                            {tag}
                                        </span>
                                    ))}
                                </div>
                            )}

                            <button
                                className={`btn btn-full ${job.status === 'PUBLISHED' ? 'btn-primary' : 'btn-secondary'}`}
                                disabled={job.status !== 'PUBLISHED' || applying === job.job_id}
                                onClick={() => handleApply(job)}
                            >
                                {applying === job.job_id ? '신청 중...' :
                                    job.status === 'PUBLISHED' ? '면접 신청' :
                                        job.status === 'CLOSED' ? '마감된 공고' : '모집 전'}
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
