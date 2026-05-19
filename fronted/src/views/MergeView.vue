<script setup>
/**
 * 合并两张图片页（学生演示项目）
 *
 * 布局与编辑页类似：顶部默认图/加载/结果图，底部为两个独立图片槽 + 指令 + 提交/重置。
 * 要点：两个图片槽互不影响；点击槽位直接从本地上传图片，提交时校验两张图已选且不相同。
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { mergeImages, uploadMyImage } from '../services/api'
import mergeDefaultImg from '../assets/image/merge-default.png'
import submitIcon from '../assets/image/submit.svg'
import deleteImageIcon from '../assets/image/delete-image.svg'
import loadingGrey from '../assets/image/loading-grey.gif'

// ---------- 状态 ----------
const selectedUrl1 = ref('')
const selectedUrl2 = ref('')
/** 两个隐藏的文件选择框，用来触发本地上传 */
const fileInput1 = ref(null)
const fileInput2 = ref(null)
/** 当前正在上传的槽位：0 表示没有上传，1/2 表示对应图片槽上传中 */
const uploadingSlot = ref(0)
/** 合并指令（用户输入的描述） */
const mergeInstruction = ref('')
/** 合并接口是否请求中 */
const isMergeLoading = ref(false)
/** 合并接口返回的结果（后端可能返回 saveUrl / saved_oss_url / url） */
const mergeResult = ref(null)

/** 用于展示的合并结果图地址（优先持久化到业务 OSS 的 saveUrl） */
const mergeResultImageUrl = computed(() => {
  const r = mergeResult.value
  if (!r) return ''
  return r.saveUrl || r.saved_oss_url || r.url || ''
})

/** 点击图片槽位时，打开本地文件选择窗口 */
const openLocalFilePicker = (slot) => {
  if (isMergeLoading.value || mergeResult.value || uploadingSlot.value) return
  if (slot === 1) fileInput1.value?.click()
  else fileInput2.value?.click()
}

/** 本地图片选中后，先上传到后端/OSS，再把返回的图片地址放进对应槽位 */
const onLocalFileChange = async (slot, event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.type?.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }

  try {
    uploadingSlot.value = slot
    const { data } = await uploadMyImage(file)
    const imageInfo = data.data || {}
    const imageUrl = imageInfo.ossUrl || imageInfo.url || imageInfo.filePath
    if (!imageUrl) throw new Error('上传成功，但后端没有返回图片地址')

    if (slot === 1) selectedUrl1.value = imageUrl
    else selectedUrl2.value = imageUrl
    ElMessage.success(`图片${slot}上传成功`)
  } catch (err) {
    ElMessage.error(err?.message || `图片${slot}上传失败`)
  } finally {
    uploadingSlot.value = 0
  }
}

/** 提交合并请求 */
const submitMerge = async () => {
  if (!selectedUrl1.value || !selectedUrl2.value) {
    ElMessage.warning('请先上传两张图片')
    return
  }
  if (selectedUrl1.value === selectedUrl2.value) {
    ElMessage.warning('两张图片不能相同')
    return
  }
  if (!mergeInstruction.value?.trim()) {
    ElMessage.warning('请输入合并指令')
    return
  }
  try {
    isMergeLoading.value = true
    const { data } = await mergeImages({
      image1: selectedUrl1.value,
      image2: selectedUrl2.value,
      instruction: mergeInstruction.value,
    })
    mergeResult.value = data.data
  } catch (err) {
    ElMessage.error(err?.message || '请求失败')
  } finally {
    isMergeLoading.value = false
  }
}

/** 重置：清空合并结果、两张已选图与指令输入框 */
const resetMergeForm = () => {
  mergeResult.value = null
  selectedUrl1.value = ''
  selectedUrl2.value = ''
  mergeInstruction.value = ''
}
</script>

<template>
  <div class="card ui-card">
    <!-- 顶部展示区：加载中 | 默认占位图(729×323) | 合并结果图 -->
    <div v-if="isMergeLoading" class="merge-hero">
      <h2 class="page-title-result">处理结果</h2>
      <div class="loading-wrap">
        <img :src="loadingGrey" alt="" class="loading-img" />
        <p class="loading-message">AI计算中...</p>
      </div>
    </div>
    <div v-else-if="mergeResult"  class="result-preview">
      <h2 class="page-title-result">处理结果</h2>
      <el-image
        :src="mergeResultImageUrl"
        fit="cover"
        class="merge-result-img"
        :preview-src-list="mergeResultImageUrl ? [mergeResultImageUrl] : []"
        preview-teleported
      />
    </div>
    <div v-else class="merge-hero">
      <h2 class="page-title">合并2张图片</h2>
      <img :src="mergeDefaultImg" alt="" class="merge-default-img" />
    </div>

    <!-- 底部表单：图片1槽 + 图片2槽 + 指令输入 + 提交/重置 -->
    <div class="merge-form-box">
      <input
        ref="fileInput1"
        class="merge-file-input"
        type="file"
        accept="image/*"
        @change="onLocalFileChange(1, $event)"
      />
      <input
        ref="fileInput2"
        class="merge-file-input"
        type="file"
        accept="image/*"
        @change="onLocalFileChange(2, $event)"
      />
      <div class="merge-form-top">
        <!-- 两个独立的图片槽，互不影响：每次只选一张，各自可单独删除 -->
        <div class="merge-slots">
          <div class="merge-image-slot">
            <template v-if="!selectedUrl1">
              <button
                type="button"
                class="merge-select-btn"
                :disabled="!!uploadingSlot"
                @click="openLocalFilePicker(1)"
              >
                <span class="merge-select-icon">+</span>
                <span class="merge-select-label">{{ uploadingSlot === 1 ? '上传中' : '图片1' }}</span>
              </button>
            </template>
            <template v-else>
              <div class="merge-selected-wrap">
                <div class="merge-selected-img-wrap">
                  <el-image
                    :src="selectedUrl1"
                    fit="cover"
                    class="merge-selected-img"
                    :preview-src-list="[selectedUrl1]"
                    preview-teleported
                  />
                </div>
                <span class="merge-slot-num">1</span>
                <button
                  v-if="!isMergeLoading && !mergeResult"
                  type="button"
                  class="merge-delete-btn"
                  aria-label="删除图片1"
                  @click.stop="selectedUrl1 = ''"
                >
                  <img :src="deleteImageIcon" alt="" class="merge-delete-icon" />
                </button>
              </div>
            </template>
          </div>
          <div class="merge-image-slot">
            <template v-if="!selectedUrl2">
              <button
                type="button"
                class="merge-select-btn"
                :disabled="!!uploadingSlot"
                @click="openLocalFilePicker(2)"
              >
                <span class="merge-select-icon">+</span>
                <span class="merge-select-label">{{ uploadingSlot === 2 ? '上传中' : '图片2' }}</span>
              </button>
            </template>
            <template v-else>
              <div class="merge-selected-wrap">
                <div class="merge-selected-img-wrap">
                  <el-image
                    :src="selectedUrl2"
                    fit="cover"
                    class="merge-selected-img"
                    :preview-src-list="[selectedUrl2]"
                    preview-teleported
                  />
                </div>
                <span class="merge-slot-num">2</span>
                <button
                  v-if="!isMergeLoading && !mergeResult"
                  type="button"
                  class="merge-delete-btn"
                  aria-label="删除图片2"
                  @click.stop="selectedUrl2 = ''"
                >
                  <img :src="deleteImageIcon" alt="" class="merge-delete-icon" />
                </button>
              </div>
            </template>
          </div>
        </div>
        <!-- 合并指令输入框，请求中或已有结果时禁用 -->
        <textarea
          :disabled="isMergeLoading || !!mergeResult"
          class="merge-textarea"
          v-model="mergeInstruction"
          rows="3"
          placeholder="描述您想呈现的画面，例如：给图2的人物换上图1的衣服"
        ></textarea>
      </div>
      <!-- 有结果时显示「重置」，否则显示「提交」（需两张图且已输入指令才可点） -->
      <div class="merge-form-actions">
        <template v-if="mergeResult">
          <button type="button" class="merge-submit-btn" @click="resetMergeForm">重置</button>
        </template>
        <template v-else>
          <button
            type="button"
            class="merge-submit-btn"
            :disabled="isMergeLoading || !selectedUrl1 || !selectedUrl2 || !mergeInstruction.trim()"
            @click="submitMerge"
          >
            <img :src="submitIcon" alt="" class="merge-submit-icon" />
            {{ isMergeLoading ? '提交中…' : '提交' }}
          </button>
        </template>
      </div>
    </div>

  </div>
</template>

<style scoped>
/* ---------- 卡片与标题 ---------- */
.card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.page-title {
  text-align: center;
  width: 100%;
}
.page-title-result {
  font-weight: 400;
  font-size: 14px;
  color: #9CA3AF;
}

/* ---------- 顶部展示区：默认图 729×323 / 加载中 / 结果图 ---------- */
.merge-hero {
  margin-top: 16px;
}
.merge-default-img {
  width: 729px;
  max-width: 100%;
  height: 323px;
  display: block;
  object-fit: contain;
  border-radius: 12px;
}
.loading-wrap {
  width: 300px;
  height: 400px;
  background: #F5F7FD;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.loading-img {
  width: 16px;
  height: 16px;
}
.loading-message {
  font-weight: 400;
  font-size: 14px;
  color: #9CA3AF;
  animation: loading-pulse 1.2s ease-in-out infinite;
}
@keyframes loading-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.result-preview {
  margin-top: 16px;
}
.merge-result-img {
  width: 300px;
  height: 400px;
  border-radius: 0;
}
.merge-result-img :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
  object-fit: cover;
  /* 结果图是竖图时，优先展示人物头部和上半身，避免默认居中裁掉头部。 */
  object-position: center top;
}

/* ---------- 底部表单框 ---------- */
.merge-form-box {
  margin-top: 20px;
  padding: 20px;
  width: 710px;
  max-width: 100%;
  min-height: 207px;
  box-sizing: border-box;
  background: #FFFFFF;
  border: 1px solid #EAEAEA;
  border-radius: 12px;
  box-shadow: 0px 4px 10px 0px rgba(0, 0, 0, 0.05);
}
.merge-file-input {
  display: none;
}
.merge-form-top {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 两个图片槽并排，互不影响 */
.merge-slots {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.merge-image-slot {
  width: 80px;
  height: 80px;
  flex-shrink: 0;
}
.merge-selected-wrap {
  position: relative;
  width: 80px;
  height: 80px;
  overflow: visible;
  cursor: pointer;
}
/* 图片左下角序号角标 */
.merge-slot-num {
  position: absolute;
  left: 0;
  bottom: 0;
  z-index: 2;
  min-width: 18px;
  height: 18px;
  padding: 0 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  border-radius: 4px;
  pointer-events: none;
}
.merge-selected-img-wrap {
  width: 100%;
  height: 100%;
  border-radius: 4px;
  overflow: hidden;
  background: #F5F7FD;
}
.merge-selected-img {
  width: 100%;
  height: 100%;
  display: block;
}
.merge-selected-img :deep(.el-image__inner) {
  width: 100% !important;
  height: 100% !important;
  object-fit: cover;
  /* 小图预览也优先显示上半身，和结果图保持一致。 */
  object-position: center top;
}
.merge-delete-btn {
  position: absolute;
  top: -8px;
  right: -8px;
  z-index: 2;
  width: 16px;
  height: 16px;
  padding: 0;
  border: none;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}
.merge-delete-btn:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.55);
}
.merge-delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}
.merge-delete-icon {
  width: 16px;
  height: 16px;
  object-fit: contain;
}
.merge-select-btn {
  flex-shrink: 0;
  width: 80px;
  height: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: #F5F7FD;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: opacity 0.2s;
  padding: 0;
}
.merge-select-btn:hover {
  opacity: 0.9;
}
.merge-select-btn:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}
.merge-select-icon {
  font-size: 24px;
  font-weight: 300;
  color: #9CA3AF;
  line-height: 1;
}
.merge-select-label {
  font-size: 13px;
  color: #9CA3AF;
}

/* 指令输入框 */
.merge-textarea {
  width: 100%;
  min-width: 0;
  padding: 8px 0;
  border: none;
  border-radius: 0;
  outline: none;
  font-size: 14px;
  line-height: 1.5;
  resize: vertical;
  font-family: inherit;
  background: transparent;
  box-sizing: border-box;
}
.merge-textarea::placeholder {
  color: rgba(16, 24, 40, 0.4);
}
.merge-textarea:focus {
  box-shadow: none;
}

/* 提交/重置按钮区 */
.merge-form-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.merge-submit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 88px;
  height: 36px;
  padding: 0;
  background: linear-gradient(90deg, #884BFF 0%, #7530FE 100%);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.2s;
}
.merge-submit-btn:hover:not(:disabled) {
  opacity: 0.92;
}
.merge-submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
.merge-submit-icon {
  width: 14px;
  height: 14px;
  display: block;
  object-fit: contain;
}
</style>
