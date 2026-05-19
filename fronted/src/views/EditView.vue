<script setup>
/**
 * 单张图片编辑页（学生演示项目）
 *
 * 布局：上方标题 + 占位图/加载态/结果图，底部表单（选择图片、编辑指令、提交/重置）。
 * 要点：点击图片槽直接从本地上传图片；提交前校验已选图与指令；成功后展示结果图并可重置。
 */
import { ref } from 'vue'
import { editImage, uploadMyImage } from '../services/api'
import editDefaultImg from '../assets/image/edit-default.png'
import loadingGrey from '../assets/image/loading-grey.gif'
import submitIcon from '../assets/image/submit.svg'
import deleteImageIcon from '../assets/image/delete-image.svg'

// ---------- 状态 ----------
/** 当前选中的图片 URL，提交时传给编辑接口 */
const selectedUrl = ref('')
/** 隐藏的文件选择框，用来触发本地上传 */
const fileInput = ref(null)
/** 当前是否正在上传本地图片 */
const isUploadLoading = ref(false)
/** 用户输入的编辑指令 */
const editInstruction = ref('')
/** 是否正在请求编辑接口（提交中） */
const isEditLoading = ref(false)
/** 校验或接口报错时的提示文案 */
const editMessage = ref('')
/** 编辑成功后的结果（含 saved_oss_url 等），有值则展示结果图 */
const editResult = ref(null)

/** 点击图片槽时，打开本地文件选择窗口 */
const openLocalFilePicker = () => {
  if (isEditLoading.value || editResult.value || isUploadLoading.value) return
  fileInput.value?.click()
}

/** 本地图片选中后，先上传到后端/OSS，再把返回的图片地址作为编辑源图 */
const onLocalFileChange = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.type?.startsWith('image/')) {
    editMessage.value = '请选择图片文件'
    return
  }

  try {
    isUploadLoading.value = true
    editMessage.value = ''
    const { data } = await uploadMyImage(file)
    const imageInfo = data.data || {}
    const imageUrl = imageInfo.ossUrl || imageInfo.url || imageInfo.filePath
    if (!imageUrl) throw new Error('上传成功，但后端没有返回图片地址')

    selectedUrl.value = imageUrl
    editMessage.value = '图片上传成功'
  } catch (err) {
    editMessage.value = err?.message || '图片上传失败'
  } finally {
    isUploadLoading.value = false
  }
}

/** 提交编辑：校验已选图与指令后调用 editImage，成功则写入 editResult */
const submitEdit = async () => {
  if (!selectedUrl.value) {
    editMessage.value = '请先上传一张图片'
    return
  }
  if (!editInstruction.value?.trim()) {
    editMessage.value = '请输入编辑指令'
    return
  }
  try {
    isEditLoading.value = true
    editMessage.value = ''
    const { data } = await editImage({
      image: selectedUrl.value,
      instruction: editInstruction.value,
    })
    editResult.value = data.data
    editMessage.value = data.message
  } catch (err) {
    editMessage.value = err?.message || '请求失败'
  } finally {
    isEditLoading.value = false
  }
}

/** 重置：清空编辑结果、提示文案、已选图片与输入框，可再次提交 */
const resetEditForm = () => {
  editResult.value = null
  editMessage.value = ''
  selectedUrl.value = ''
  editInstruction.value = ''
}
</script>

<template>
  <div class="card ui-card">
    <!-- 顶部展示区：加载中 | 默认占位图 | 编辑结果图 -->
    <div v-if="isEditLoading" class="edit-hero">
      <h2 class="page-title-result">处理结果</h2>
      <div class="loading-wrap">
        <img :src="loadingGrey" alt="" class="loading-img" />
        <p class="loading-message">AI计算中...</p>
      </div>
    </div>
    <div v-else-if="editResult" class="result-preview">
      <h2 class="page-title-result">处理结果</h2>
      <el-image
        :src="editResult.saved_oss_url || editResult.url"
        fit="cover"
        class="edit-result-img"
        :preview-src-list="[editResult.saved_oss_url || editResult.url]"
        preview-teleported
      />
    </div>
    <div v-else class="edit-hero">
      <h2 class="page-title">单张图片编辑</h2>
      <img :src="editDefaultImg" alt="" class="edit-default-img" />
    </div>

    <!-- 底部表单：选择图片槽 + 编辑指令输入框 + 提交/重置 -->
    <div class="edit-form-box">
      <input
        ref="fileInput"
        class="edit-file-input"
        type="file"
        accept="image/*"
        @change="onLocalFileChange"
      />
      <div class="edit-form-top">
        <!-- 图片槽：未选显示「选择图片」按钮，已选显示缩略图与删除按钮 -->
        <div class="edit-image-slot">
          <template v-if="!selectedUrl">
            <button
              type="button"
              class="edit-select-btn"
              :disabled="isUploadLoading"
              @click="openLocalFilePicker"
            >
              <span class="edit-select-icon">+</span>
              <span class="edit-select-label">{{ isUploadLoading ? '上传中' : '图片' }}</span>
            </button>
          </template>
          <template v-else>
            <div class="edit-selected-wrap">
              <div class="edit-selected-img-wrap">
                <el-image
                  :src="selectedUrl"
                  fit="cover"
                  class="edit-selected-img"
                  :preview-src-list="[selectedUrl]"
                  preview-teleported
                />
              </div>
              <button
                v-if="!isEditLoading && !editResult"
                type="button"
                class="edit-delete-btn"
                aria-label="删除图片"
                @click.stop="selectedUrl = ''"
              >
                <img :src="deleteImageIcon" alt="" class="edit-delete-icon" />
              </button>
            </div>
          </template>
        </div>
        <!-- 编辑指令输入框 -->
        <textarea
          class="edit-textarea"
          v-model="editInstruction"
          rows="3"
          placeholder="描述您想呈现的画面，例如：把人物的上衣换成粉色的"
          :disabled="isEditLoading || !!editResult"
        ></textarea>
      </div>
      <!-- 有结果时显示「重置」，否则显示「提交」（需已选图且已输入指令才可点，请求中显示「提交中…」） -->
      <div class="edit-form-actions">
        <template v-if="editResult">
          <button type="button" class="edit-submit-btn" @click="resetEditForm">重置</button>
        </template>
        <template v-else>
          <button type="button" class="edit-submit-btn" :disabled="isEditLoading || !selectedUrl || !editInstruction.trim()" @click="submitEdit">
            <img :src="submitIcon" alt="" class="edit-submit-icon" />
            {{ isEditLoading ? '提交中…' : '提交' }}
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
.edit-result-img {
  width: 300px;
  height: 400px;
  border-radius: 0;
}
.edit-hero {
  margin-top: 16px;
}
.result-preview {
  margin-top: 16px;
}
.edit-default-img {
  width: 483px;
  height: 323px;
  display: block;
  object-fit: contain;
  border-radius: 12px;
}
/* 提交后展示的「AI计算中」加载态（与 MergeView 一致） */
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

/* ---------- 底部表单框 ---------- */
.edit-form-box {
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
.edit-file-input {
  display: none;
}
.edit-form-top {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 选择图片槽：80x80 占位按钮 / 已选缩略图 + 删除按钮 */
.edit-image-slot {
  width: 80px;
  height: 80px;
  flex-shrink: 0;
}
.edit-selected-wrap {
  position: relative;
  width: 80px;
  height: 80px;
  overflow: visible;
  cursor: pointer;
}
.edit-selected-img-wrap {
  width: 100%;
  height: 100%;
  border-radius: 4px;
  overflow: hidden;
  background: #F5F7FD;
}
.edit-selected-img {
  width: 100%;
  height: 100%;
  display: block;
}
.edit-selected-img :deep(.el-image__inner) {
  width: 100% !important;
  height: 100% !important;
  object-fit: cover;
}
.edit-delete-btn {
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
.edit-delete-btn:hover {
  background: rgba(0, 0, 0, 0.55);
}
.edit-delete-icon {
  width: 16px;
  height: 16px;
  object-fit: contain;
}
.edit-select-btn {
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
.edit-select-btn:hover {
  opacity: 0.9;
}
.edit-select-btn:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}
.edit-select-icon {
  font-size: 24px;
  font-weight: 300;
  color: #9CA3AF;
  line-height: 1;
}
.edit-select-label {
  font-size: 13px;
  color: #9CA3AF;
}
.edit-textarea {
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
.edit-textarea::placeholder {
  color: rgba(16, 24, 40, 0.4);
}
.edit-textarea:focus {
  box-shadow: none;
}
.edit-form-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.edit-submit-btn {
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
.edit-submit-btn:hover:not(:disabled) {
  opacity: 0.92;
}
.edit-submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
.edit-submit-icon {
  width: 14px;
  height: 14px;
  display: block;
  object-fit: contain;
}
.msg {
  margin-top: 12px;
  color: var(--danger);
  font-weight: 600;
  text-align: center;
  width: 100%;
}
.result {
  margin-top: 18px;
  margin-left: auto;
  margin-right: auto;
  padding: 16px;
  width: 100%;
  max-width: 560px;
  box-sizing: border-box;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--card-solid);
}
.links {
  display: flex;
  flex-direction: column;
  gap: 6px;
  word-break: break-all;
}
.preview {
  margin-top: 12px;
}
.preview img {
  max-width: 100%;
  border-radius: 12px;
  box-shadow: 0 10px 24px rgba(16, 24, 40, 0.12);
}
</style>
