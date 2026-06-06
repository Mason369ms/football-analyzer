import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const message = error.response?.data?.error || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export default api

// API 函数
export const matchesApi = {
  getList: (date?: string, limit = 100) =>
    api.get('/api/matches', { params: { date, limit } }),

  getDetail: (id: string) =>
    api.get(`/api/match/${id}`),
}

export const analysesApi = {
  getList: (matchId?: string, limit = 50) =>
    api.get('/api/analyses', { params: { match_id: matchId, limit } }),

  getDetail: (id: string) =>
    api.get(`/api/analysis/${id}`),

  clear: () =>
    api.post('/api/analyses/clear'),
}

export const jobsApi = {
  start: (action: string, matchId?: string) =>
    api.get('/api/run', { params: { action, match_id: matchId } }),

  getStatus: (jobId: string) =>
    api.get(`/api/jobs/${jobId}`),
}

export const configApi = {
  get: () =>
    api.get('/api/config'),

  save: (data: any) =>
    api.post('/api/config', data),
}

export const statsApi = {
  getSystem: () =>
    api.get('/api/stats'),

  getHealth: () =>
    api.get('/health'),

  getDetailedHealth: () =>
    api.get('/health/detailed'),

  getMetrics: () =>
    axios.get('/metrics').then(res => res.data),
}

export const exportApi = {
  pdf: (analysisId: number) =>
    api.get(`/api/export/pdf/${analysisId}`, { responseType: 'blob' }),

  excel: (limit = 100) =>
    api.get('/api/export/excel', { params: { limit }, responseType: 'blob' }),
}

export const cacheApi = {
  getStats: () =>
    api.get('/api/cache/stats'),

  clear: () =>
    api.post('/api/cache/clear'),
}
