<script setup>
/**
 * 顶栏组件（学生演示项目）：展示当前页标题、未登录时「去登录」、已登录时用户信息与退出。
 * 退出时调用 logout 接口并 authStore.clear()，再跳转登录页。
 */
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'
import { logout } from '../services/api'
import { computed, ref } from 'vue'
import headIcon from '../assets/image/head.svg'
import logoutIcon from '../assets/image/logout.svg'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const dropdownVisible = ref(false)

const pageTitle = computed(() =>
  route.meta?.title || (route.name ? String(route.name) : '') || '控制台'
)

const handleLogout = async () => {
  if (!auth.isLoggedIn) return
  loading.value = true
  // 不阻塞页面跳转：退出失败也不提示，直接回登录页
  const tokenSnapshot = auth.token
  logout(tokenSnapshot).catch(() => {})
  auth.clear()
  router.push({ name: 'login' })
  loading.value = false
}
</script>

<template>
  <header class="app-header">
    <div class="app-header-title">{{ pageTitle }}</div>
    <div class="app-header-actions">
      <el-dropdown
        v-if="auth.isLoggedIn"
        trigger="hover"
        placement="bottom-end"
        popper-class="app-header-dropdown"
        @visible-change="(v) => (dropdownVisible = v)"
        @command="(cmd) => cmd === 'logout' && handleLogout()"
      >
        <span class="app-header-trigger">
          <img :src="headIcon" alt="" class="app-header-avatar-img" />
          <span class="app-header-username">{{ auth.user?.username || auth.user?.email || '用户' }}</span>
          <span class="app-header-arrow" :class="{ 'is-open': dropdownVisible }" />
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout" :disabled="loading">
              <span class="app-header-logout-item">
                <img :src="logoutIcon" alt="" class="app-header-logout-icon" />
                {{ loading ? '退出中…' : '退出登录' }}
              </span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <RouterLink v-else to="/login" class="ui-btn ui-btn-primary">去登录</RouterLink>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 10;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  background: rgba(255, 255, 255, 0.92);
  border-bottom: 1px solid rgba(16, 24, 40, 0.08);
  backdrop-filter: blur(10px);
}
.app-header-title {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.2px;
  color: rgba(16, 24, 40, 0.9);
}
.app-header-actions {
  display: flex;
  align-items: center;
}
.app-header-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  cursor: pointer;
  outline: none;
  border: none;
  box-shadow: none;
}
.app-header-trigger:hover,
.app-header-trigger:focus,
.app-header-trigger:focus-visible {
  outline: none;
  border: none;
  box-shadow: none;
}
/* 去掉 el-dropdown 触发层自带的悬停/聚焦边框 */
:deep(.el-dropdown__trigger) {
  outline: none !important;
  border: none !important;
  box-shadow: none !important;
}
:deep(.el-dropdown__trigger:hover),
:deep(.el-dropdown__trigger:focus),
:deep(.el-dropdown__trigger:focus-visible) {
  outline: none !important;
  border: none !important;
  box-shadow: none !important;
}
.app-header-avatar-img {
  width: 24px;
  height: 24px;
  display: block;
  object-fit: contain;
  flex-shrink: 0;
}
.app-header-username {
  font-size: 14px;
  font-weight: 600;
  color: rgba(16, 24, 40, 0.88);
}
.app-header-arrow {
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 5px solid #222222;
  margin-left: 2px;
  transition: transform 0.2s ease;
}
.app-header-arrow.is-open {
  transform: rotate(180deg);
}

.app-header-logout-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.app-header-logout-icon {
  width: 14px;
  height: 14px;
  display: block;
  object-fit: contain;
  flex-shrink: 0;
}
</style>

<style>
/* 退出登录下拉：悬停无背景、文字颜色不变（popper 在 body 下，需非 scoped） */
.app-header-dropdown .el-dropdown-menu__item,
.app-header-dropdown .el-dropdown-menu__item:hover,
.app-header-dropdown .el-dropdown-menu__item:focus {
  background: transparent !important;
  color: #606266 !important;
}
</style>
