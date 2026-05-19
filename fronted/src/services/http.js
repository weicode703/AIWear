/**
 * Axios 封装（学生演示项目）
 *
 * - baseURL 统一为 '/api'，开发时通过 Vite 代理转发到后端
 * - 请求拦截：自动携带登录 token
 * - 响应拦截：统一把后端/网络错误转换成中文提示
 */
import axios from 'axios'
import { useAuthStore } from '../store/auth'
import router from '../router'

const BASE_URL = '/api'
const DEFAULT_TIMEOUT = 60000

const http = axios.create({
  baseURL: BASE_URL,
  timeout: DEFAULT_TIMEOUT,
})

/**
 * 统一把后端错误和网络错误转换成中文提示，
 * 这样页面上就不会直接显示英文报错。
 */
function getFriendlyErrorMessage(error) {
  const responseData = error?.response?.data
  const detail = responseData?.detail
  const backendMessage =
    (typeof responseData?.message === 'string' && responseData.message) ||
    (typeof detail === 'string' && detail) ||
    (typeof detail?.error === 'string' && detail.error) ||
    error?.message

  const status = error?.response?.status

  if (status === 400) return backendMessage || '请求参数有误，请检查后重试'
  if (status === 401) return backendMessage || '当前登录状态已失效，请重新登录'
  if (status === 403) return backendMessage || '当前操作没有权限'
  if (status === 404) return '请求的接口不存在，请检查后端服务是否已启动'
  if (status === 422) return '提交的信息格式不正确，请检查输入内容'
  if (status === 500) return backendMessage || '服务器开小差了，请稍后重试'
  if (error?.code === 'ECONNABORTED') return '请求超时，请稍后重试'
  if (backendMessage === 'Network Error') {
    return '网络连接失败，请确认前后端服务是否都已启动'
  }

  return backendMessage || '请求失败，请稍后重试'
}

/** 请求拦截：为需要登录的接口自动带上 token */
http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth?.token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

/** 响应拦截：统一处理业务错误与网络错误 */
http.interceptors.response.use(
  (resp) => {
    const data = resp.data
    if (data && typeof data.code === 'number' && data.code !== 200) {
      const message = typeof data.message === 'string' ? data.message : ''
      const isJwtExpired =
        (data.code === 401 && message === 'JWT无效或已过期') ||
        (data.code === 500 && /jwt\s*expired/i.test(message)) ||
        (/jwt/i.test(message) && /(expired|过期)/i.test(message))

      if (isJwtExpired) {
        const auth = useAuthStore()
        auth.clear()
        if (router.currentRoute?.value?.name !== 'login') {
          router.replace({ name: 'login' })
        }
      }

      const err = new Error(message || '请求出错')
      err.response = resp
      return Promise.reject(err)
    }
    return resp
  },
  (error) => {
    const msg = getFriendlyErrorMessage(error)
    error.message = msg

    const responseData = error?.response?.data
    const message = typeof responseData?.message === 'string' ? responseData.message : msg
    const isJwtExpired =
      (typeof responseData?.code === 'number' &&
        responseData.code === 401 &&
        message === 'JWT无效或已过期') ||
      /jwt\s*expired/i.test(message) ||
      (/jwt/i.test(message) && /(expired|过期)/i.test(message))

    if (isJwtExpired) {
      const auth = useAuthStore()
      auth.clear()
      if (router.currentRoute?.value?.name !== 'login') {
        router.replace({ name: 'login' })
      }
    }

    return Promise.reject(error)
  }
)

export default http
