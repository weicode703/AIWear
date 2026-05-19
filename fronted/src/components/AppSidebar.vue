<script setup>
import { RouterLink, useRoute } from 'vue-router'
import iconEdit from '../assets/image/menu-edit.svg'
import iconMerge from '../assets/image/menu-merge.svg'
import iconMyImage from '../assets/image/menu-my-image.svg'
import iconHistory from '../assets/image/menu-history.svg'

const route = useRoute()
</script>

<template>
  <aside class="sider">
    <nav class="menu">
      <RouterLink to="/edit" class="menu-item" :class="{ active: route.path === '/edit' }">
        <span class="mi-ico"><img :src="iconEdit" alt="" /></span>
        <span>图片编辑</span>
      </RouterLink>

      <RouterLink to="/merge" class="menu-item" :class="{ active: route.path === '/merge' }">
        <span class="mi-ico"><img :src="iconMerge" alt="" /></span>
        <span>图片合并</span>
      </RouterLink>

      <RouterLink to="/images" class="menu-item" :class="{ active: route.path === '/images' }">
        <span class="mi-ico"><img :src="iconMyImage" alt="" /></span>
        <span>我的图片</span>
      </RouterLink>

      <RouterLink to="/records" class="menu-item" :class="{ active: route.path === '/records' }">
        <span class="mi-ico"><img :src="iconHistory" alt="" /></span>
        <span>历史记录</span>
      </RouterLink>

      <RouterLink to="/rag" class="menu-item" :class="{ active: route.path === '/rag' }">
        <span class="mi-ico">问</span>
        <span>穿搭问答</span>
      </RouterLink>
    </nav>
  </aside>
</template>

<style scoped>
.sider {
  position: sticky;
  top: 0;
  width: 152px;
  height: 100vh;
  padding: 16px 12px;
  background: linear-gradient(180deg, #f0f2f8 0%, #faf8fc 50%, #ffffff 100%);
  border-right: 1px solid rgba(16, 24, 40, 0.08);
  backdrop-filter: blur(10px);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.menu {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 0 4px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px;
  border-radius: 10px;
  color: rgba(16, 24, 40, 0.72);
  border: none;
  transition: background 0.2s ease, color 0.2s ease;
  text-decoration: none;
  font-size: 14px;
}

.menu-item:hover {
  background: rgba(123, 85, 255, 0.06);
  color: rgba(16, 24, 40, 0.88);
}

.menu-item.active {
  background: rgba(123, 85, 255, 0.12);
  color: rgba(16, 24, 40, 0.88);
}

.mi-ico {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: inherit;
  font-size: 13px;
  font-weight: 600;
}

.menu-item .mi-ico img {
  width: 18px;
  height: 18px;
  object-fit: contain;
  display: block;
}

.menu-item:not(.active) .mi-ico img {
  opacity: 0.6;
}

.menu-item.active .mi-ico img {
  opacity: 1;
}

@media (max-width: 980px) {
  .sider {
    position: relative;
    height: auto;
  }
}
</style>
