/**
 * 路由配置（学生演示项目）
 *
 * - 使用 createWebHistory(import.meta.env.BASE_URL)，便于部署到子路径。
 * - meta.auth：为 true 的页面需要登录后才能访问，否则在 beforeEach 里跳转到登录页，并通过 query.redirect 记录原目标，登录后可跳回。
 * - meta.title：用于顶栏/侧栏展示中文标题。
 * - 组件使用 () => import(...) 懒加载，减少首屏体积。
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../store/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/edit' },
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { title: '登录' } },
    { path: '/edit', name: 'edit', component: () => import('../views/EditView.vue'), meta: { auth: true, title: '图片编辑' } },
    { path: '/merge', name: 'merge', component: () => import('../views/MergeView.vue'), meta: { auth: true, title: '图片合并' } },
    { path: '/images', name: 'images', component: () => import('../views/ImagesView.vue'), meta: { auth: true, title: '我的图片' } },
    { path: '/records', name: 'records', component: () => import('../views/RecordsView.vue'), meta: { auth: true, title: '历史记录' } },
    { path: '/rag', name: 'rag', component: () => import('../views/RagView.vue'), meta: { auth: true, title: '穿搭问答' } },
    { path: '/:pathMatch(.*)*', redirect: '/edit' }, // 未匹配路径兜底到编辑页
  ],
})

/**
 * 全局前置守卫：登录校验
 * - 访问需登录页面且未登录 → 跳转登录页，并带上 redirect=当前完整路径，登录成功后可跳回。
 * - 已登录用户访问登录页 → 直接重定向到 /edit，避免重复登录。
 */
router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.isLoggedIn) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else if (to.name === 'login' && auth.isLoggedIn) {
    next({ path: '/edit' })
  } else {
    next()
  }
})

export default router

