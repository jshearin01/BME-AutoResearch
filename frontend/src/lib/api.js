import axios from 'axios'
const api = axios.create({ baseURL: '' })
export const listProjects = () => api.get('/api/projects').then(r => r.data)
export const createProject = (b) => api.post('/api/projects', b).then(r => r.data)
export const updateProject = (id, b) => api.patch(`/api/projects/${id}`, b).then(r => r.data)
export const research = (b) => api.post('/api/research/search', b).then(r => r.data)
export const makeSpec = (b) => api.post('/api/design/spec', b).then(r => r.data)
export const safetyCheck = (b) => api.post('/api/safety/check', b).then(r => r.data)
export const genCad = (b) => api.post('/api/cad/generate', b).then(r => r.data)
export const printPacket = (b) => api.post('/api/printing/packet', b).then(r => r.data)
export const agentRun = (b) => api.post('/api/agent/run', b).then(r => r.data)
export const listRuns = (pid) => api.get('/api/runs', { params: { project_id: pid } }).then(r => r.data)
export default api
