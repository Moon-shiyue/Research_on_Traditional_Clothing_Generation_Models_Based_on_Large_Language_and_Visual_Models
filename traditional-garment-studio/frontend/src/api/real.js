/**
 * Real API 实现 —— 对齐 docs/api-v0.2.md 本地组件制版契约
 * 联调时启用（.env: VITE_API_MODE=real），经 vite proxy 转发到 FastAPI
 */
import axios from 'axios'
import { prepareImageUpload } from '../utils/imageUpload'
import { pollTask } from './taskPolling'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// 会话头（Session 状态保存在服务端）
const sessionId = (() => {
  const KEY = 'd2g_session_id'
  let id = localStorage.getItem(KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(KEY, id)
  }
  return id
})()

http.interceptors.request.use((config) => {
  config.headers['X-Session-Id'] = sessionId
  return config
})

// 统一错误提取：{ code, message }
function wrapError(e) {
  const data = e.response?.data?.error
  const serverFailure = e.response?.status >= 500
  return {
    code: data?.code || (serverFailure ? 'server_error' : 'network_error'),
    message: data?.message || (serverFailure ? '后台处理未完成，请稍后重试；已有纸样已保留。'
      : e.response?.status === 404 ? '任务或资源已失效，请重新生成。' : '后端暂时未连接，请启动制版服务后重试。'),
  }
}

export function createRealApi() {
  return {
    mode: 'real',

    async getVisionConfig() {
      const { data } = await http.get('/vision/config').catch((e) => { throw wrapError(e) })
      return data
    },

    async configureVision(config) {
      const { data } = await http.put('/vision/config', config).catch((e) => { throw wrapError(e) })
      return data
    },

    async clearVisionConfig() {
      const { data } = await http.delete('/vision/config').catch((e) => { throw wrapError(e) })
      return data
    },

    async selectVisionSource(source) {
      return (await http.put('/vision/source', { source }).catch((e) => { throw wrapError(e) })).data
    },
    async getChatGPTStatus() {
      return (await http.get('/vision/chatgpt').catch((e) => { throw wrapError(e) })).data
    },
    async loginChatGPT(account_id = null) {
      return (await http.post('/vision/chatgpt/login', { account_id }, { timeout: 60000 }).catch((e) => { throw wrapError(e) })).data
    },
    async cancelChatGPTLogin() {
      return (await http.delete('/vision/chatgpt/login').catch((e) => { throw wrapError(e) })).data
    },
    async signOutChatGPT() {
      return (await http.delete('/vision/chatgpt', { timeout: 60000 }).catch((e) => { throw wrapError(e) })).data
    },
    async getChatGPTModels() {
      return (await http.get('/vision/chatgpt/models', { timeout: 60000 }).catch((e) => { throw wrapError(e) })).data
    },
    async selectChatGPTModel(model) {
      return (await http.put('/vision/chatgpt/model', { model }, { timeout: 60000 }).catch((e) => { throw wrapError(e) })).data
    },

    async uploadImage(file) {
      const form = new FormData()
      form.append('file', await prepareImageUpload(file))
      const { data } = await http.post('/upload/image', form).catch((e) => {
        throw wrapError(e)
      })
      return data
    },

    // POST /parse → 携带会话头的有界轮询
    async parse({ mode = 'auto', text = '', image = null, image_proposal_id = null, scope = 'outfit', opening_choice = null, skirt_choice = null, innerwear_choice = null, request_id = null }, handlers = {}) {
      const { data } = await http
        .post('/parse', { mode, text, image, image_proposal_id, scope, opening_choice, skirt_choice, innerwear_choice, request_id })
        .catch((e) => {
          throw wrapError(e)
        })
      subscribeTask(data.task_id, handlers)
      return data
    },

    async getTask(taskId) {
      const { data } = await http.get(`/tasks/${taskId}`).catch((e) => {
        throw wrapError(e)
      })
      return data
    },

    async resumeTask(taskId, handlers = {}) {
      // Only resume reading the already accepted task; do not submit /parse.
      subscribeTask(taskId, handlers)
      return { task_id: taskId }
    },

    async getDesignParams() {
      const { data } = await http.get('/design/params').catch((e) => {
        throw wrapError(e)
      })
      return data
    },

    async getDesignHistory() {
      return (await http.get('/design/history').catch(e => { throw wrapError(e) })).data
    },

    async restoreDesign(design_id) {
      return (await http.post('/design/restore', { design_id }).catch(e => { throw wrapError(e) })).data
    },

    async updateDesignParam(path, value, unit = 'native') {
      const { data } = await http.put('/design/params', { path, value, unit }).catch((e) => {
        throw wrapError(e)
      })
      return data
    },

    async randomDesign() {
      const { data } = await http.post('/design/random').catch((e) => {
        throw wrapError(e)
      })
      return data
    },

    async defaultDesign() {
      const { data } = await http.post('/design/default').catch((e) => {
        throw wrapError(e)
      })
      return data
    },

    async getBodyParams() {
      const { data } = await http.get('/body/params').catch((e) => {
        throw wrapError(e)
      })
      return data
    },

    async updateBodyParam(path, value) {
      const { data } = await http.put('/body/params', { path, value }).catch((e) => {
        throw wrapError(e)
      })
      return data
    },

    async getPattern() {
      const { data } = await http.get('/pattern').catch((e) => {
        throw wrapError(e)
      })
      return data
    },

    async download() {
      const res = await http
        .post('/download/link')
        .catch((e) => {
          throw wrapError(e)
        })
      const a = document.createElement('a')
      a.href = res.data.url
      a.download = res.data.filename
      document.body.appendChild(a)
      a.click()
      a.remove()
    },

    async getPrintPlan() {
      return (await http.get('/print/plan').catch(e => { throw wrapError(e) })).data
    },

    async downloadPrint(pattern_url) {
      const { data } = await http.post('/print/link', { pattern_url }, { timeout: 120000 }).catch(e => { throw wrapError(e) })
      const a = document.createElement('a')
      a.href = data.url
      a.download = data.filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      return data
    },

    async getVocab() {
      const { data } = await http.get('/vocab').catch((e) => {
        throw wrapError(e)
      })
      return data
    },
  }
}

// Bounded sequential polling uses the same session-aware HTTP client.
function subscribeTask(taskId, handlers) {
  pollTask({ readTask: async () => (await http.get(`/tasks/${taskId}`)).data, handlers, wrapError })
    .catch(() => handlers.onError?.({ code: 'task_display_error', message: '任务已响应，但页面更新未完成，请刷新检查当前纸样。' }))
}
