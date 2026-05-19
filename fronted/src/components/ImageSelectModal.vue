<script setup>
/**
 * 选择图片弹框（学生演示项目）
 *
 * 支持单选（mode="single"）与双选（mode="double"），通过 v-model 控制显隐，@confirm 回传选中 url 或 [url1, url2]。
 * 要点：打开时用 watch 同步 props.selected 到 tempSelected；确认时校验已选再 emit；图片列表由父组件传入。
 */
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import closeIcon from '../assets/image/close.svg'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  images: { type: Array, default: () => [] },
  /** 当前已选：单选为 url 字符串，多选为 [url1, url2] */
  selected: { type: [String, Array], default: '' },
  /** 'single' 选一张 | 'double' 选两张 */
  mode: { type: String, default: 'single' },
})
const emit = defineEmits(['update:modelValue', 'confirm'])

const getImageUrl = (item) => item?.ossUrl || item?.url || ''
const imageExtRe = /\.(png|jpg|jpeg|gif|webp|svg|bmp|ico)(\?.*)?$/i
const getImageLabel = (item) => {
  const name = item?.fileName || '模特名称'
  return name.replace(imageExtRe, '')
}

const tempSelected = ref([])
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      const s = props.selected
      tempSelected.value = Array.isArray(s) ? [...(s || [])] : s ? [s] : []
    }
  },
  { immediate: true }
)

const tempIsSelected = (url) => tempSelected.value.includes(url)

const select = (url) => {
  if (props.mode === 'single') {
    tempSelected.value = [url]
    return
  }
  const idx = tempSelected.value.indexOf(url)
  if (idx >= 0) {
    tempSelected.value = tempSelected.value.filter((u) => u !== url)
    return
  }
  if (tempSelected.value.length >= 2) return
  tempSelected.value = [...tempSelected.value, url]
}

const handleConfirm = () => {
  const hasSelection = props.mode === 'single'
    ? !!tempSelected.value[0]
    : tempSelected.value.length > 0
  if (!hasSelection) {
    ElMessage.warning('请选择图片')
    return
  }
  if (props.mode === 'single') {
    emit('confirm', tempSelected.value[0] || '')
  } else {
    emit('confirm', [...tempSelected.value])
  }
  emit('update:modelValue', false)
}

const handleClose = () => {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    width="900px"
    align-center
    class="image-select-dialog"
    :show-close="false"
    destroy-on-close
    @update:model-value="(v) => emit('update:modelValue', v)"
    @close="handleClose"
  >
    <template #header>
      <div class="image-select-header-wrap">
        <div class="image-select-header">
          <span class="image-select-title">选择图片</span>
          <button type="button" class="image-select-close" aria-label="关闭" @click="handleClose">
            <img :src="closeIcon" alt="" class="image-select-close-icon" />
          </button>
        </div>
        <div class="image-select-divider" />
      </div>
    </template>

    <div class="image-select-grid">
      <button
        v-for="img in images"
        :key="img.id"
        type="button"
        class="image-select-item"
        :class="{ 'is-selected': tempIsSelected(getImageUrl(img)) }"
        @click="select(getImageUrl(img))"
      >
        <div class="image-select-thumb">
          <img :src="getImageUrl(img)" :alt="getImageLabel(img)" />
        </div>
        <div class="image-select-label">{{ getImageLabel(img) }}</div>
      </button>
    </div>

    <template #footer>
      <div class="image-select-footer">
        <button type="button" class="image-select-confirm-btn" @click="handleConfirm">
          确认
        </button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.image-select-header-wrap {
  height: 46px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  box-sizing: border-box;
  overflow: visible;
}
.image-select-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-right: 8px;
  flex: 0 0 auto;
}
.image-select-divider {
  height: 1px;
  width: 100%;
  background: #E8E8E8;
  margin-top: auto;
  flex-shrink: 0;
  /* 与弹框左右边对齐：抵消 header 内边距 */
  margin-left: -20px;
  margin-right: -20px;
  width: calc(100% + 40px);
}
.image-select-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}
.image-select-close {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
  transition: opacity 0.16s;
}
.image-select-close:hover {
  opacity: 0.88;
}
.image-select-close-icon {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.image-select-grid {
  display: grid;
  grid-template-columns: repeat(7, 110px);
  gap: 14px;
  max-height: 450px;
  overflow-x: visible;
  overflow-y: auto;
  padding: 4px 10px;
}
.image-select-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: 110px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: center;
  overflow: visible;
}
.image-select-thumb {
  width: 110px;
  height: 145px;
  flex-shrink: 0;
  border-radius: 8px;
  overflow: hidden;
  background: rgba(16, 24, 40, 0.06);
  background: white;
  border: 2px solid transparent;
  transition: border-color 0.16s, transform 0.2s ease, box-shadow 0.2s ease, border-radius 0.2s ease;
}
.image-select-item:hover .image-select-thumb {
  transform: scale(1.05);
  box-shadow: 0 0 12px 2px rgba(0, 0, 0, 0.2);
  border-radius: 12px;
}
.image-select-item.is-selected .image-select-thumb {
  border-color: #8446FF;
}
.image-select-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.image-select-label {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 110px;
}

.image-select-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
}
.image-select-confirm-btn {
  width: 98px;
  height: 38px;
  background: linear-gradient(90deg, #884BFF 0%, #7530FE 100%);
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.16s;
}
.image-select-confirm-btn:hover {
  opacity: 0.92;
}
.image-select-confirm-btn:active {
  opacity: 0.88;
}
</style>

<style>
.image-select-dialog .el-dialog__header {
  margin-right: 0;
  padding-bottom: 12px;
  overflow: visible;
}
.image-select-dialog .el-dialog__body {
  padding-top: 0;
  padding-bottom: 16px;
  overflow-x: visible;
}
.image-select-dialog .el-dialog__footer {
  padding-top: 0;
}
.image-select-dialog .el-dialog {
  overflow-x: visible;
  border-radius: 16px;
}
.image-select-dialog.el-dialog {
  overflow-x: visible;
  border-radius: 16px;
}
</style>
