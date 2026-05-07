import axios from 'axios'

// Use environment variable for API URL, fallback to /api for production
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({ baseURL: API_BASE_URL })

export const tenderApi = {
  upload:               (file) => { const fd = new FormData(); fd.append('file', file); return api.post('/tender/upload', fd) },
  getRules:             ()     => api.get('/tender/rules'),
  approveRule:          (id)   => api.put(`/tender/rules/${id}/approve`),
  updateRule:           (id, data) => api.put(`/tender/rules/${id}`, data),
  deleteRule:           (id)   => api.post(`/tender/rules/${id}/delete`),
  approveAll:           ()     => api.post('/tender/approve-all'),
  approveMandatoryOnly: ()     => api.post('/tender/approve-mandatory'),
  addRule:              (data) => api.post('/tender/rules/add', data),
  reset:                ()     => api.delete('/tender/'),
}

export const bidderApi = {
  upload: (name, files) => {
    const fd = new FormData()
    fd.append('bidder_name', name)
    files.forEach(f => fd.append('files', f))
    return api.post('/bidder/upload', fd)
  },
  list:    ()  => api.get('/bidder/list'),
  get:     (id) => api.get(`/bidder/${id}`),
  confirm: (id) => api.post(`/bidder/${id}/confirm`),
  remove:  (id) => api.delete(`/bidder/${id}`),
}

export const evaluateApi = {
  run:      ()                             => api.post('/evaluate/run'),
  latest:   ()                             => api.get('/evaluate/latest'),
  override: (reportId, bidderId, v, note)  => api.post(`/evaluate/override/${reportId}/${bidderId}`, { verdict: v, note }),
  finalize: (reportId)                     => api.post(`/evaluate/finalize/${reportId}`),
}

export const reportApi = {
  latest: ()   => api.get('/report/latest'),
  get:    (id) => api.get(`/report/${id}`),
  pdfUrl: (id) => `${API_BASE_URL}/report/${id}/pdf`,
}
