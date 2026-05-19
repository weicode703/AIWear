<script setup>
/**
 * 根组件 App.vue（学生演示项目）
 *
 * 根据是否在「登录页」切换两种布局：
 * - 登录页：全屏展示 LoginView，无侧栏/顶栏。
 * - 已登录：后台壳布局 —— 左侧 AppSidebar、顶部 AppHeader、中间为 RouterView（编辑/合并/图片/记录等页）。
 * 这样登录页可以独立设计，登录后的页面共用一套导航。
 */
import { RouterView } from 'vue-router'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './components/AppSidebar.vue'
import AppHeader from './components/AppHeader.vue'

const route = useRoute()
/** 当前是否为登录页，用于切换整页布局 */
const isLoginPage = computed(() => route.name === 'login' || route.path === '/login')
</script>

<template>
  <!-- 登录页用独立背景/布局 -->
  <RouterView v-if="isLoginPage" />

  <!-- 登录后：后台壳布局（侧边栏 + 顶栏 + 内容区） -->
  <div v-else class="shell">
    <AppSidebar />

    <div class="main">
      <AppHeader />
      <main class="content">
        <div class="content-inner">
          <RouterView />
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 152px minmax(0, 1fr);
  background:
    radial-gradient(900px 400px at 12% 0%, rgba(47, 107, 255, 0.18), transparent 55%),
    radial-gradient(900px 400px at 85% 10%, rgba(56, 189, 248, 0.12), transparent 55%),
    var(--bg);
}

.main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.content {
  flex: 1;
  padding: 18px 22px 28px;
  background: var(--bg);
}
.content-inner {
  width: 100%;
}

@media (max-width: 980px) {
  .shell {
    grid-template-columns: 1fr;
  }
}
</style>
