<template>
  <el-container class="layout-container">
    <!-- 移动端菜单按钮 -->
    <div class="mobile-header" v-if="isMobile">
      <el-button :icon="Menu" @click="drawerVisible = true" text />
      <span class="mobile-title">Football Analyzer</span>
    </div>

    <!-- 侧边栏 -->
    <el-aside :width="isMobile ? '0px' : '220px'" class="sidebar" :class="{ 'mobile-sidebar': isMobile }">
      <div class="logo">
        <span class="logo-icon">⚽</span>
        <span class="logo-text" v-if="!isMobile">Football Analyzer</span>
      </div>

      <el-menu
        :default-active="currentRoute"
        :collapse="isMobile"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <template #title>赛事列表</template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer" v-if="!isMobile">
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-icon><User /></el-icon>
            <span>{{ username }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-aside>

    <!-- 移动端抽屉菜单 -->
    <el-drawer
      v-model="drawerVisible"
      direction="ltr"
      size="220px"
      :show-close="false"
      v-if="isMobile"
    >
      <template #header>
        <div class="drawer-header">
          <span class="logo-icon">⚽</span>
          <span>Football Analyzer</span>
        </div>
      </template>
      <el-menu
        :default-active="currentRoute"
        router
        @select="drawerVisible = false"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <template #title>赛事列表</template>
        </el-menu-item>
      </el-menu>
      <template #footer>
        <el-button type="danger" @click="handleLogout" style="width: 100%">
          退出登录
        </el-button>
      </template>
    </el-drawer>

    <!-- 主内容区 -->
    <el-main class="main-content">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { HomeFilled, DataAnalysis, Setting, User, Menu } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const isMobile = ref(false)
const drawerVisible = ref(false)
const username = ref('admin')

const currentRoute = computed(() => route.path)

const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

const handleCommand = (command: string) => {
  if (command === 'logout') {
    handleLogout()
  }
}

const handleLogout = () => {
  localStorage.removeItem('football_session')
  router.push('/login')
}
</script>

<style scoped lang="scss">
.layout-container {
  height: 100vh;
}

.mobile-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 50px;
  background: #172033;
  color: #fff;
  display: flex;
  align-items: center;
  padding: 0 16px;
  z-index: 1000;
  gap: 12px;

  .mobile-title {
    font-size: 16px;
    font-weight: 600;
  }
}

.sidebar {
  background: #172033;
  color: #fff;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
  overflow: hidden;

  &.mobile-sidebar {
    display: none;
  }
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);

  .logo-icon {
    font-size: 24px;
  }

  .logo-text {
    font-size: 18px;
    font-weight: 700;
    white-space: nowrap;
  }
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  background: transparent;

  :deep(.el-menu-item) {
    color: #cbd5e1;

    &:hover {
      background: rgba(255, 255, 255, 0.1);
      color: #fff;
    }

    &.is-active {
      background: var(--primary-color);
      color: #fff;
    }
  }
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #cbd5e1;
  cursor: pointer;

  &:hover {
    color: #fff;
  }
}

.main-content {
  background: var(--bg-color);
  padding: 20px;
  overflow-y: auto;

  @media (max-width: 768px) {
    padding: 60px 12px 12px;
  }
}

.drawer-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;

  .logo-icon {
    font-size: 24px;
  }
}
</style>
