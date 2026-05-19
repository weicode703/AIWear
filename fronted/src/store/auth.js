/**
 * 登录态 Store（Pinia）（学生演示项目）
 *
 * 作用：集中存放 token 与用户信息，并持久化到 localStorage，刷新页面不丢失。
 * - state.token：请求头 Authorization 会用到（见 services/http.js 拦截器）。
 * - state.user：如 userId、username、email，可用于顶栏展示。
 * - setAuth(token, user)：登录成功后由 LoginView 调用，写入 state 并同步到 localStorage。
 * - clear()：退出登录时由 AppHeader 调用，清空 state 与 localStorage。
 */
import { defineStore } from 'pinia'

const TOKEN_KEY = 'mengtu_token'
const USER_KEY = 'mengtu_user'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: (() => {
      const raw = localStorage.getItem(USER_KEY)
      try {
        return raw ? JSON.parse(raw) : null
      } catch {
        return null
      }
    })(),
  }),
  getters: {
    /** 是否已登录（路由守卫与顶栏根据此判断） */
    isLoggedIn: (state) => !!state.token,
  },
  actions: {
    /** 登录成功：写入 token 与 user，并持久化 */
    setAuth(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    },
    /** 退出登录：清空内存与 localStorage */
    clear() {
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    },
  },
})

