<template>
  <div class="login-container">
    <div class="login-aside">
      <div class="brand">
        <span class="brand-icon">⚽</span>
        <h1>Football Analyzer</h1>
        <p>足球赛事数据分析与 LLM 智能预测系统</p>
      </div>
      <ul class="features">
        <li>赛事数据实时抓取</li>
        <li>赔率深度分析</li>
        <li>LLM 智能预测</li>
        <li>命中率统计追踪</li>
      </ul>
    </div>

    <div class="login-main">
      <el-card class="login-card">
        <template #header>
          <h2>{{ isRegister ? '注册账号' : '账号登录' }}</h2>
          <p>{{ isRegister ? '创建后会自动进入个人工作区' : '请输入管理员或已创建用户的账号密码' }}</p>
        </template>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          @submit.prevent="handleSubmit"
          label-position="top"
        >
          <el-form-item label="账号" prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入账号"
              prefix-icon="User"
              size="large"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              prefix-icon="Lock"
              size="large"
              show-password
            />
          </el-form-item>

          <el-form-item v-if="isRegister" label="确认密码" prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="请再次输入密码"
              prefix-icon="Lock"
              size="large"
              show-password
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              @click="handleSubmit"
              style="width: 100%"
            >
              {{ isRegister ? '注册' : '登录' }}
            </el-button>
          </el-form-item>

          <div class="form-footer">
            <el-link v-if="isRegister" @click="isRegister = false">
              已有账号？返回登录
            </el-link>
            <el-link v-else @click="isRegister = true">
              还没有账号？注册新账号
            </el-link>
          </div>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const isRegister = ref(false)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: ''
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入账号', trigger: 'blur' },
    { min: 3, max: 20, message: '账号长度在 3 到 20 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (rule: any, value: string, callback: Function) => {
        if (value !== form.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const handleSubmit = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true

  try {
    const url = isRegister.value ? '/register' : '/login'
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: `username=${encodeURIComponent(form.username)}&password=${encodeURIComponent(form.password)}`
    })

    if (response.ok) {
      localStorage.setItem('football_session', 'true')
      ElMessage.success(isRegister.value ? '注册成功' : '登录成功')
      router.push('/')
    } else {
      const text = await response.text()
      ElMessage.error(text || '操作失败')
    }
  } catch (error) {
    ElMessage.error('网络错误')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-container {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(280px, 0.88fr) minmax(340px, 1fr);

  @media (max-width: 820px) {
    grid-template-columns: 1fr;
  }
}

.login-aside {
  background: #172033;
  color: #fff;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 54px;

  @media (max-width: 820px) {
    padding: 30px 22px;
    min-height: auto;
  }
}

.brand {
  margin-bottom: 40px;

  .brand-icon {
    font-size: 46px;
    display: block;
    margin-bottom: 16px;
  }

  h1 {
    font-size: 30px;
    margin-bottom: 12px;

    @media (max-width: 820px) {
      font-size: 24px;
    }
  }

  p {
    color: #cbd5e1;
    line-height: 1.7;
  }
}

.features {
  list-style: none;
  padding: 0;
  color: #e2e8f0;

  @media (max-width: 820px) {
    display: none;
  }

  li {
    padding: 8px 0;
    display: flex;
    align-items: center;
    gap: 10px;

    &::before {
      content: '';
      width: 8px;
      height: 8px;
      background: #34d399;
      border-radius: 50%;
    }
  }
}

.login-main {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 36px 22px;
}

.login-card {
  width: 100%;
  max-width: 420px;

  :deep(.el-card__header) {
    border-bottom: none;
    padding-bottom: 0;

    h2 {
      font-size: 24px;
      margin-bottom: 8px;
    }

    p {
      color: var(--text-muted);
      font-size: 14px;
    }
  }
}

.form-footer {
  text-align: center;
}
</style>
