// API service layer – communicates with FastAPI backend
import axios from 'axios'

const api = axios.create({
    baseURL: '/api/v1',
    headers: { 'Content-Type': 'application/json' },
})

// Attach token from localStorage on every request
api.interceptors.request.use(config => {
    const token = localStorage.getItem('imh_token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Auto-handle 401
api.interceptors.response.use(
    res => res,
    err => {
        if (err.response?.status === 401) {
            localStorage.removeItem('imh_token')
            localStorage.removeItem('imh_user')
            window.location.href = '/login'
        }
        return Promise.reject(err)
    }
)

// --- Auth ---
export const authApi = {
    login: (data) => api.post('/auth/login', data),
    signup: (data) => api.post('/auth/signup', data),
    checkUsername: (username) => api.get('/auth/check-username', { params: { username } }),
    getMe: () => api.get('/auth/me'),
    updateAccount: (data) => api.patch('/auth/account', data),
}

// --- Jobs ---
export const jobsApi = {
    list: (status) => api.get('/jobs', { params: status ? { status } : undefined }),
    get: (jobId) => api.get(`/jobs/${jobId}`),
    create: (data) => api.post('/jobs', data),
    update: (jobId, data) => api.patch(`/jobs/${jobId}`, data),
    listCandidates: (jobId) => api.get(`/jobs/${jobId}/candidates`),
    getCandidateDetail: (jobId, userId) => api.get(`/jobs/${jobId}/candidates/${userId}`),
}

// --- Interviews ---
export const interviewsApi = {
    list: () => api.get('/interviews'),
    create: (jobId) => api.post('/interviews', { job_id: jobId }),
    get: (id) => api.get(`/interviews/${id}`),
    getChat: (id) => api.get(`/interviews/${id}/chat`),
    sendChat: (id, content) => api.post(`/interviews/${id}/chat`, { content }),
    getResult: (id) => api.get(`/interviews/${id}/result`),
}

// --- Resume ---
export const resumeApi = {
    get: () => api.get('/resume'),
    upload: (file) => {
        const form = new FormData()
        form.append('file', file)
        return api.post('/resume/upload', form, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
    },
}

export default api
