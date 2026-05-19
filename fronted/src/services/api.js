/**
 * 后端接口封装（学生演示项目）
 *
 * 供页面直接调用，不在此处写业务参数含义，由调用方传参。
 * - 登录：sendCode（发验证码）、auth（登录/注册）、logout（退出）。
 * - 图片：uploadMyImage（上传）、myImages（我的图片列表）、editImage（单图编辑）、mergeImages（双图合并）、searchImages（文搜图/图搜图）。
 * - 记录：myRecords（历史记录列表）。
 */
import http from './http'

const JSON_HEADERS = { 'Content-Type': 'application/json' }
const PYTHON_TIMEOUT = 300000

// ---------- 登录 ----------
export function sendCode(email) {
  return http.post('/user/send-code', { email })
}

export function auth(payload) {
  return http.post('/user/auth', payload)
}

export function logout(token) {
  if (token) {
    return http.post('/user/logout', null, {
      headers: { Authorization: `Bearer ${token}` },
    })
  }
  return http.post('/user/logout')
}

// ---------- 图片 ----------
export function uploadMyImage(file) {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/file/upload/image', fd)
}

export function editImage(params) {
  return http.post('/file/edit', params, {
    headers: JSON_HEADERS,
    timeout: PYTHON_TIMEOUT,
  })
}

export function mergeImages(params) {
  return http.post('/file/merge', params, {
    headers: JSON_HEADERS,
    timeout: PYTHON_TIMEOUT,
  })
}

/** 文搜图走 /file/search/text；图搜图走 /file/search/image */
export function searchImages(params) {
  if (params.file) {
    const fd = new FormData()
    fd.append('file', params.file)
    fd.append('topK', String(params.topK || 10))
    return http.post('/file/search/image', fd)
  }
  return http.post('/file/search/text', {
    query: params.query?.trim() || '',
    topK: params.topK || 10,
  }, {
    headers: JSON_HEADERS,
  })
}

export function myImages() {
  return http.get('/file/my-images')
}

// ---------- 记录 ----------
export function myRecords() {
  return http.get('/record/my')
}

// ---------- RAG 穿搭问答 ----------
export function ragStatus() {
  return http.get('/rag/status')
}

export function ragChat(params) {
  return http.post('/rag/chat', params, {
    headers: JSON_HEADERS,
    timeout: PYTHON_TIMEOUT,
  })
}

export function ragChatStreamUrl() {
  return '/api/rag/chat/stream'
}

export function ragConversations() {
  return http.get('/rag/conversations')
}

export function ragConversationMessages(conversationId) {
  return http.get(`/rag/conversations/${conversationId}/messages`)
}

export function deleteRagConversation(conversationId) {
  return http.delete(`/rag/conversations/${conversationId}`)
}
