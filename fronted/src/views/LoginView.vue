<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { auth, sendCode } from '../services/api'
import { useAuthStore } from '../store/auth'
import banner1 from '../assets/image/login-banner1.png'
import banner2 from '../assets/image/login-banner2.png'

// 当前登录方式：验证码登录 / 密码登录
const loginMethod = ref('code')

// 登录表单数据
const loginForm = reactive({
  account: '',
  password: '',
  verificationCode: '',
})

// 表单引用，用于触发校验
const loginFormRef = ref(null)

// 请求状态
const isLoginLoading = ref(false)
const isSendCodeLoading = ref(false)

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 左侧轮播图数据
const loginBannerItems = computed(() => [
  { key: 'banner1', title: '图片编辑', img: banner1 },
  { key: 'banner2', title: '图片合并', img: banner2 },
])

const bannerCarouselIndex = ref(0)
let bannerCarouselTimer = null

onMounted(() => {
  bannerCarouselTimer = setInterval(() => {
    bannerCarouselIndex.value = (bannerCarouselIndex.value + 1) % loginBannerItems.value.length
  }, 5000)
})

onUnmounted(() => {
  if (bannerCarouselTimer) clearInterval(bannerCarouselTimer)
})

// 根据登录方式切换校验规则
const formRules = computed(() =>
  loginMethod.value === 'code'
    ? {
        account: [
          { required: true, message: '请输入邮箱', trigger: 'blur' },
          {
            validator: (_rule, value, callback) => {
              const text = value?.trim()
              if (!text) return callback()
              if (!text.includes('@')) {
                callback(new Error('请输入正确的邮箱'))
              } else {
                callback()
              }
            },
            trigger: 'blur',
          },
        ],
        verificationCode: [
          { required: true, message: '请输入验证码', trigger: 'blur' },
        ],
      }
    : {
        account: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
        password: [
          { required: true, message: '请输入密码', trigger: 'blur' },
          { min: 6, message: '密码至少 6 位', trigger: 'blur' },
        ],
      }
)

// 切换登录方式时清空表单
watch(loginMethod, () => {
  loginForm.account = ''
  loginForm.password = ''
  loginForm.verificationCode = ''
  loginFormRef.value?.clearValidate()
})

// 发送邮箱验证码
const sendVerificationCode = async () => {
  try {
    await loginFormRef.value?.validateField('account')
  } catch {
    return
  }

  if (!loginForm.account.trim().includes('@')) {
    ElMessage.warning('请先输入正确的邮箱')
    return
  }

  try {
    isSendCodeLoading.value = true
    await sendCode(loginForm.account.trim())
    ElMessage.success('验证码已发送，请检查邮箱')
  } catch (error) {
    ElMessage.error(error?.message || '验证码发送失败')
  } finally {
    isSendCodeLoading.value = false
  }
}

// 提交登录 / 注册
const submitLogin = async () => {
  try {
    await loginFormRef.value?.validate()
  } catch {
    return
  }

  const accountVal = loginForm.account.trim()
  const passwordVal = loginForm.password.trim()
  const codeVal = loginForm.verificationCode.trim()

  try {
    isLoginLoading.value = true
    const { data } = await auth({
      account: accountVal,
      password: loginMethod.value === 'password' ? passwordVal : undefined,
      // FastAPI 后端使用下划线字段名
      verification_code: loginMethod.value === 'code' ? codeVal : undefined,
    })

    const res = data.data
    authStore.setAuth(res.token, {
      userId: res.userId,
      username: res.username,
      email: res.email,
    })

    const redirect = route.query.redirect ? String(route.query.redirect) : '/edit'
    ElMessage.success('登录成功')
    router.push(redirect)
  } catch (error) {
    ElMessage.error(error?.message || '登录失败')
  } finally {
    isLoginLoading.value = false
  }
}
</script>

<template>
  <div class="login">
    <div class="login-card">
      <section class="preview">
        <div class="preview-stage">
          <div class="preview-stage-sizer" aria-hidden="true" />
          <div
            v-for="(item, idx) in loginBannerItems"
            :key="item.key"
            class="preview-hero preview-hero--layer"
            :class="{ 'preview-hero--active': idx === bannerCarouselIndex }"
            :style="{ backgroundImage: `url(${item.img})` }"
            role="img"
            :aria-hidden="idx !== bannerCarouselIndex"
            :aria-label="item.title"
          />
        </div>

        <div class="preview-dots" role="tablist" aria-label="登录页轮播切换">
          <button
            v-for="(item, idx) in loginBannerItems"
            :key="item.key"
            type="button"
            class="dot"
            :class="{ 'dot--active': idx === bannerCarouselIndex }"
            @click="bannerCarouselIndex = idx"
            :aria-label="`切换到${item.title}`"
          />
        </div>
      </section>

      <section class="panel">
        <header class="brand">
          <p class="brand-subtitle">登录后即可继续使用编辑、合并与推荐功能</p>
        </header>

        <nav class="tabs" aria-label="登录方式">
          <button
            type="button"
            class="tab"
            :class="{ active: loginMethod === 'code' }"
            @click="loginMethod = 'code'"
          >
            验证码登录
          </button>
          <button
            type="button"
            class="tab"
            :class="{ active: loginMethod === 'password' }"
            @click="loginMethod = 'password'"
          >
            密码登录
          </button>
          <span
            class="tabs-underline"
            :class="{ 'tabs-underline--right': loginMethod === 'password' }"
          />
        </nav>

        <div class="form">
          <el-form
            ref="loginFormRef"
            :model="loginForm"
            :rules="formRules"
            label-position="top"
            class="form-el"
          >
            <div v-if="loginMethod === 'code'" class="form-content">
              <el-form-item prop="account" class="form-item-custom">
                <template #label>
                  <span class="field-label">邮箱</span>
                </template>
                <el-input
                  v-model="loginForm.account"
                  type="email"
                  placeholder="请输入邮箱"
                  clearable
                  maxlength="50"
                  class="input"
                />
              </el-form-item>

              <el-form-item prop="verificationCode" class="form-item-custom">
                <template #label>
                  <span class="field-label">验证码</span>
                </template>
                <el-input
                  v-model="loginForm.verificationCode"
                  placeholder="请输入验证码"
                  clearable
                  maxlength="6"
                  class="input input-with-suffix"
                >
                  <template #suffix>
                    <button
                      type="button"
                      class="send-link send-link-suffix"
                      :disabled="isSendCodeLoading"
                      @click="sendVerificationCode"
                    >
                      {{ isSendCodeLoading ? '发送中...' : '获取验证码' }}
                    </button>
                  </template>
                </el-input>
              </el-form-item>
            </div>

            <div v-else class="form-content">
              <el-form-item prop="account" class="form-item-custom">
                <template #label>
                  <span class="field-label">用户名</span>
                </template>
                <el-input
                  v-model="loginForm.account"
                  placeholder="请输入用户名"
                  clearable
                  maxlength="32"
                  class="input"
                />
              </el-form-item>

              <el-form-item prop="password" class="form-item-custom">
                <template #label>
                  <span class="field-label">密码</span>
                </template>
                <el-input
                  v-model="loginForm.password"
                  type="password"
                  placeholder="请输入密码"
                  show-password
                  clearable
                  maxlength="20"
                  class="input"
                />
              </el-form-item>
            </div>

            <button
              type="submit"
              class="submit"
              :disabled="isLoginLoading"
              @click.prevent="submitLogin"
            >
              {{ isLoginLoading ? '登录中...' : '登录 / 注册' }}
            </button>
          </el-form>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.login {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(1200px 680px at 70% 35%, rgba(150, 186, 255, 0.45), rgba(150, 186, 255, 0) 60%),
    radial-gradient(900px 520px at 25% 70%, rgba(205, 172, 255, 0.55), rgba(205, 172, 255, 0) 62%),
    linear-gradient(135deg, #eef3ff 0%, #f2eeff 42%, #eaf6ff 100%);
  padding: 56px 20px;
}

.login-card {
  width: min(980px, 100%);
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  box-shadow: 0 18px 60px rgba(28, 39, 56, 0.12);
  backdrop-filter: blur(10px);
  display: grid;
  grid-template-columns: 430px 1fr;
  gap: 44px;
  padding: 34px 38px;
  padding-left: 20px;
}

.preview {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 520px;
}

.preview-stage {
  position: relative;
  width: 100%;
  padding: 0 0 20px;
  border-radius: 14px;
  background: #ffffff;
  overflow: hidden;
  display: grid;
}

.preview-stage > * {
  grid-area: 1 / 1;
}

.preview-stage-sizer {
  width: 100%;
  max-height: 500px;
  aspect-ratio: 920 / 1100;
  visibility: hidden;
  pointer-events: none;
}

.preview-hero {
  width: 100%;
  height: auto;
  max-height: 500px;
  aspect-ratio: 920 / 1100;
  border-radius: 12px;
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
  display: flex;
  align-items: flex-end;
  overflow: hidden;
  position: relative;
}

.preview-hero--layer {
  align-self: stretch;
  justify-self: stretch;
  width: 100%;
  height: 100%;
  max-height: 500px;
  opacity: 0;
  transition: opacity 1s ease-in-out;
  pointer-events: none;
}

.preview-hero--active {
  opacity: 1;
  pointer-events: auto;
}

.preview-dots {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 4px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  border: none;
  background: rgba(119, 83, 255, 0.28);
  cursor: pointer;
  transition: width 0.18s ease, background-color 0.18s ease;
}

.dot--active {
  width: 18px;
  background: rgba(119, 83, 255, 0.85);
}

.panel {
  display: flex;
  flex-direction: column;
  padding-right: 8px;
}

.brand {
  text-align: center;
}

.brand-subtitle {
  margin-top: 60px;
  font-size: 13px;
  color: rgba(16, 24, 40, 0.48);
}

.tabs {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin: 14px auto 18px;
  width: min(420px, 100%);
  border-bottom: 1px solid rgba(16, 24, 40, 0.08);
  margin-top: 42px;
}

.tab {
  appearance: none;
  border: none;
  background: transparent;
  padding: 12px 0 14px;
  font-size: 14px;
  color: rgba(16, 24, 40, 0.45);
  cursor: pointer;
  transition: color 0.16s ease;
}

.tab:hover {
  color: rgba(16, 24, 40, 0.8);
}

.tab.active {
  color: rgba(16, 24, 40, 0.9);
  font-weight: 700;
}

.tabs-underline {
  position: absolute;
  bottom: -1px;
  left: 50%;
  width: 50%;
  height: 2px;
  transform: translateX(-100%);
  background: #7b55ff;
  border-radius: 999px;
  transition: transform 0.22s ease;
}

.tabs-underline--right {
  transform: translateX(0);
}

.form {
  width: min(420px, 100%);
  margin: 0 auto;
}

.form-el {
  margin-bottom: 0;
}

.form-item-custom :deep(.el-form-item__label) {
  height: auto;
  line-height: 1.4;
  padding-bottom: 10px;
}

.form-item-custom :deep(.el-form-item__content) {
  line-height: 1.4;
}

.form-item-custom :deep(.el-form-item__error) {
  padding-top: 4px;
}

.form-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-label {
  font-size: 13px;
  font-weight: 700;
  color: rgba(16, 24, 40, 0.76);
}

.input {
  width: 100%;
}

.input :deep(.el-input__wrapper) {
  height: 40px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid rgba(16, 24, 40, 0.14);
  background: rgba(255, 255, 255, 0.85);
  font-size: 14px;
  color: rgba(16, 24, 40, 0.88);
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background-color 0.18s ease;
  box-shadow: none;
}

.input :deep(.el-input__wrapper:hover),
.input :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(123, 85, 255, 0.9);
  box-shadow: 0 0 0 3px rgba(123, 85, 255, 0.14);
  background: rgba(255, 255, 255, 1);
}

.input :deep(.el-input__inner::placeholder) {
  color: rgba(16, 24, 40, 0.32);
}

.send-link {
  appearance: none;
  border: none;
  background: transparent;
  padding: 0;
  font-size: 12px;
  color: rgba(123, 85, 255, 0.95);
  cursor: pointer;
  font-weight: 700;
  white-space: nowrap;
  flex-shrink: 0;
}

.send-link:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-with-suffix :deep(.el-input__suffix) {
  padding-right: 4px;
}

.send-link-suffix {
  margin-left: 4px;
  padding: 0 4px;
  height: 24px;
  line-height: 24px;
}

.submit {
  margin-top: 18px;
  width: 100%;
  height: 44px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(180deg, #7b55ff, #6b3cff);
  color: #ffffff;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.5px;
  cursor: pointer;
  transition: transform 0.1s ease, filter 0.18s ease, opacity 0.18s ease;
}

.submit:hover:not(:disabled) {
  filter: brightness(1.03);
}

.submit:active:not(:disabled) {
  transform: translateY(1px);
}

.submit:disabled {
  opacity: 0.75;
  cursor: not-allowed;
}

@media (max-width: 980px) {
  .login-card {
    grid-template-columns: 1fr;
    gap: 26px;
    padding: 26px 20px;
  }

  .preview {
    min-height: auto;
  }

  .preview-stage {
    padding: 16px;
  }

  .preview-stage-sizer {
    height: 280px;
    max-height: none;
  }

  .preview-hero,
  .preview-hero--layer {
    height: 280px;
    max-height: none;
  }
}

</style>
