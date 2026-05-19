<script setup>
/**
 * 图片管理页（学生演示项目）
 *
 * 三个页签：我的图片（上传、列表）、文搜图（关键词 searchImages({ query })）、图搜图（选文件 searchImages({ file })）。
 * 要点：切回「我的图片」时重新拉取列表；文搜图/图搜图结果独立存放；图搜图取消选择时不清空已选文件。
 */
import { onMounted, ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { myImages, uploadMyImage, searchImages } from '../services/api'
import emptyDataIcon from '../assets/image/empty-data.svg'
import imageSearchEmptyIcon from '../assets/image/image-search-empty.svg'
import uploadIcon from '../assets/image/upload.svg'
import menuMyImageIcon from '../assets/image/menu-my-image.svg'

// ---------- 页签 ----------
/** 当前页签：'images' | 'textSearch' | 'imageSearch' */
const mainTab = ref('images')

// ---------- 我的图片 ----------
/** 我的图片列表 */
const myImagesList = ref([])
/** 我的图片列表是否加载中（用于空态展示） */
const isMyImagesLoading = ref(false)
/** 是否正在上传图片 */
const isUploading = ref(false)
/** 待上传的文件（用户选择后触发上传） */
const pendingUploadFile = ref(null)
/** 上传用隐藏 input 的引用 */
const fileInputRef = ref(null)

/** 拉取「我的图片」列表 */
const fetchMyImagesList = async () => {
  try {
    isMyImagesLoading.value = true
    const { data } = await myImages()
    myImagesList.value = data.data || []
  } catch (err) {
    ElMessage.error(err?.message || '查询失败')
  } finally {
    isMyImagesLoading.value = false
  }
}

onMounted(fetchMyImagesList)

// 切回「我的图片」时重新拉取，保证数据最新
watch(mainTab, (tab) => {
  if (tab === 'images') fetchMyImagesList()
})

/** 用户选择文件后触发，有文件则立即上传 */
const handleUploadFile = (e) => {
  const input = e.target
  const file = input.files?.item(0) || null
  pendingUploadFile.value = file
  if (file) performImageUpload()
}

/** 执行上传并刷新「我的图片」列表 */
const performImageUpload = async () => {
  if (!pendingUploadFile.value) return
  try {
    isUploading.value = true
    await uploadMyImage(pendingUploadFile.value)
    pendingUploadFile.value = null
    if (fileInputRef.value) fileInputRef.value.value = ''
    await fetchMyImagesList()
  } catch (err) {
    ElMessage.error(err?.message || '上传失败')
  } finally {
    isUploading.value = false
  }
}

/** 列表项图片地址（ossUrl / url） */
const getImageUrl = (item) => item?.ossUrl || item?.url || item?.filePath || ''

/** 去掉常见图片后缀，用于列表/检索结果名称展示 */
const imageExtRe = /\.(png|jpg|jpeg|gif|webp|svg|bmp|ico)(\?.*)?$/i
const getDisplayFileName = (name) => {
  if (!name) return ''
  return name.replace(imageExtRe, '')
}

// ---------- 文搜图 / 图搜图 ----------
const searchQuery = ref('')           // 文搜图关键词
const searchImageFile = ref(null)     // 图搜图选中的文件
const imageSearchInputRef = ref(null) // 图搜图隐藏 input 的引用
/** 文搜图/图搜图检索是否请求中 */
const isSearchLoading = ref(false)
const textSearchResult = ref(null)   // 文搜图结果（与图搜图独立）
const imageSearchResult = ref(null)  // 图搜图结果

/** 兼容检索接口返回：优先数组（新结构），其次读取 results（旧结构） */
const normalizeSearchResults = (payload) => {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.results)) return payload.results
  return []
}

/** 检索结果名称：新接口优先展示图片描述，旧接口继续展示文件名。 */
const getSearchResultName = (item) => {
  return item?.description || item?.fileName || item?.raw_instruction || '相似图片'
}

/** 图搜图已选文件的预览 URL（用于下方缩略图展示） */
const searchImagePreviewUrl = computed(() =>
  searchImageFile.value ? URL.createObjectURL(searchImageFile.value) : ''
)

const canSubmitTextSearch = computed(() => !!searchQuery.value?.trim())
const canSubmitImageSearch = computed(() => !!searchImageFile.value)

// 文搜图：清空输入时清空结果
watch(searchQuery, (val) => {
  if (!val?.trim()) textSearchResult.value = null
})
// 图搜图：更换或清空已选图片时清空结果
watch(searchImageFile, () => {
  imageSearchResult.value = null
})

/** 图搜图文件选择：仅在实际选中文件时更新，取消弹框不清空原图 */
const onSearchFileChange = (e) => {
  const target = e.target
  const file = target.files?.[0] ?? null
  if (file) searchImageFile.value = file
  target.value = ''
}

/** 文搜图提交：无结果时 toast 提示，报错时 error toast */
const submitTextSearch = async () => {
  if (!canSubmitTextSearch.value) return
  try {
    isSearchLoading.value = true
    const { data } = await searchImages({ query: searchQuery.value.trim() })
    const results = normalizeSearchResults(data?.data)
    textSearchResult.value = results
    if (!results.length) ElMessage.warning('暂无相关数据')
  } catch (err) {
    ElMessage.error(err?.response?.data?.message || err?.message || '请求失败')
  } finally {
    isSearchLoading.value = false
  }
}

/** 图搜图提交：无结果时 toast 提示，报错时 error toast */
const submitImageSearch = async () => {
  if (!canSubmitImageSearch.value) return
  try {
    isSearchLoading.value = true
    const { data } = await searchImages({ file: searchImageFile.value })
    const results = normalizeSearchResults(data?.data)
    imageSearchResult.value = results
    if (!results.length) ElMessage.warning('暂无相关数据')
  } catch (err) {
    const msg = err?.response?.data?.message || err?.message || '请求失败'
    ElMessage.error(msg)
  } finally {
    isSearchLoading.value = false
  }
}
</script>

<template>
  <div class="card ui-card">
    <!-- 顶部：左侧三个页签，右侧随页签切换为「上传图片」/「文搜图输入+搜索」/「图搜图选择+搜索」 -->
    <header class="page-header">
      <div class="main-tabs">
        <!-- 页签按钮 -->
        <button
          type="button"
          class="main-tab"
          :class="{ active: mainTab === 'images' }"
          @click="mainTab = 'images'"
        >
          我的图片
        </button>
        <button
          type="button"
          class="main-tab"
          :class="{ active: mainTab === 'textSearch' }"
          @click="mainTab = 'textSearch'"
        >
          文搜图
        </button>
        <button
          type="button"
          class="main-tab"
          :class="{ active: mainTab === 'imageSearch' }"
          @click="mainTab = 'imageSearch'"
        >
          图搜图
        </button>
        <!-- 我的图片：隐藏 file input + 上传按钮 -->
        <template v-if="mainTab === 'images'">
          <input
            ref="fileInputRef"
            type="file"
            accept="image/*"
            class="file-input-hidden"
            @change="handleUploadFile"
          />
          <button
            type="button"
            class="upload-top-btn"
            :disabled="isUploading"
            @click="fileInputRef?.click()"
          >
            <img :src="uploadIcon" alt="" class="upload-top-icon" />
            {{ isUploading ? '上传中…' : '上传图片' }}
          </button>
        </template>
        <!-- 文搜图：输入框 + 搜索按钮 -->
        <template v-else-if="mainTab === 'textSearch'">
          <div class="text-search-wrap">
            <el-input
              v-model="searchQuery"
              class="text-search-input"
              placeholder="请输入查询内容"
              clearable
              @keyup.enter="submitTextSearch"
            />
            <button
              type="button"
              class="text-search-btn"
              :disabled="isSearchLoading || !canSubmitTextSearch"
              @click="submitTextSearch"
            >
              {{ isSearchLoading ? '搜索中…' : '搜索' }}
            </button>
          </div>
        </template>
        <!-- 图搜图：隐藏 file input + 选择区（占位/文件名 + 图标）+ 搜索按钮 -->
        <template v-else-if="mainTab === 'imageSearch'">
          <input
            ref="imageSearchInputRef"
            type="file"
            accept="image/*"
            class="file-input-hidden"
            @change="onSearchFileChange"
          />
          <div class="image-search-actions">
            <div
              class="image-search-select-wrap"
              :class="{ 'has-file': searchImageFile }"
              role="button"
              tabindex="0"
              @click="imageSearchInputRef?.click()"
              @keydown.enter.space.prevent="imageSearchInputRef?.click()"
            >
              <span class="image-search-select-text">{{ (searchImageFile?.name && getDisplayFileName(searchImageFile.name)) || '请选择图片' }}</span>
              <img :src="menuMyImageIcon" alt="" class="image-search-select-icon" />
            </div>
            <button
              type="button"
              class="image-search-btn"
              :disabled="isSearchLoading || !canSubmitImageSearch"
              @click="submitImageSearch"
            >
              {{ isSearchLoading ? '搜索中…' : '搜索' }}
            </button>
          </div>
        </template>
      </div>
    </header>

    <!-- 我的图片：网格列表 + 无数据时缺省图 -->
    <div v-show="mainTab === 'images'" class="tab-content tab-content-images">
      <div class="grid">
        <div v-for="img in myImagesList" :key="img.id" class="item">
          <div class="item-img-wrap">
            <el-image
              :src="getImageUrl(img)"
              fit="cover"
              class="item-img"
              :preview-src-list="[getImageUrl(img)]"
              preview-teleported
            />
          </div>
          <div class="item-name">
            <span class="item-name-text">{{ getDisplayFileName(img.fileName) }}</span>
          </div>
        </div>
      </div>
      <div v-if="!myImagesList.length && !isMyImagesLoading" class="empty-state">
        <img :src="emptyDataIcon" alt="" class="empty-state-img" />
        <p class="empty-state-text">暂无图片，快去上传吧~</p>
      </div>
    </div>

    <!-- 文搜图：有结果展示网格，无结果展示缺省图 -->
    <div v-show="mainTab === 'textSearch'" class="tab-content tab-content-images">
      <template v-if="textSearchResult?.length">
        <div class="grid">
          <div v-for="(item, index) in textSearchResult" :key="item.id || getImageUrl(item) || index" class="item">
            <div class="item-img-wrap">
              <el-image
                :src="getImageUrl(item)"
                fit="cover"
                class="item-img"
                :preview-src-list="[getImageUrl(item)]"
                preview-teleported
              />
            </div>
            <div class="item-name">
              <span class="item-name-text">{{ getDisplayFileName(getSearchResultName(item)) }}</span>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="empty-state">
        <img :src="imageSearchEmptyIcon" alt="" class="empty-state-img" />
        <p class="empty-state-text">找找看，这里有你的素材~</p>
      </div>
    </div>

    <!-- 图搜图：已选图片缩略图 → 横条 → 相似图片列表 / 缺省图 -->
    <div v-show="mainTab === 'imageSearch'" class="tab-content tab-content-images">
      <!-- 已选图片预览 -->
      <div v-if="searchImagePreviewUrl" class="image-search-selected-wrap">
        <div class="image-search-selected-label">已选图片</div>
        <div class="image-search-selected-preview">
          <el-image
            :src="searchImagePreviewUrl"
            fit="cover"
            class="image-search-selected-img"
            :preview-src-list="[searchImagePreviewUrl]"
            preview-teleported
          />
        </div>
      </div>
      <!-- 有结果：横条 + 标题 + 网格；无结果：缺省图 -->
      <template v-if="imageSearchResult?.length">
        <div class="image-search-divider"></div>
        <h3 class="image-search-result-title">相似图片</h3>
        <div class="grid">
          <div v-for="(item, index) in imageSearchResult" :key="item.id || getImageUrl(item) || index" class="item">
            <div class="item-img-wrap">
              <el-image
                :src="getImageUrl(item)"
                fit="cover"
                class="item-img"
                :preview-src-list="[getImageUrl(item)]"
                preview-teleported
              />
            </div>
            <div class="item-name">
              <span class="item-name-text">{{ getDisplayFileName(getSearchResultName(item)) }}</span>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="empty-state">
        <img :src="imageSearchEmptyIcon" alt="" class="empty-state-img" />
        <p class="empty-state-text">找找看，这里有你的素材~</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ---------- 布局 ---------- */
.card {
  padding: 20px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 0;
}
/* ---------- 我的图片：上传按钮 ---------- */
.upload-top-btn {
  width: 110px;
  height: 40px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: linear-gradient(90deg, #884BFF 0%, #7530FE 100%);
  color: #fff;
  border: none;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.2s;
}
.upload-top-icon {
  width: 18px;
  height: 18px;
  display: block;
  object-fit: contain;
}
.upload-top-btn:hover:not(:disabled) {
  opacity: 0.92;
}
.upload-top-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* ---------- 页签 ---------- */
.main-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  align-items: center;
  flex-wrap: wrap;
  width: 100%;
}
.main-tabs .upload-top-btn {
  margin-left: auto;
}

/* ---------- 文搜图：输入 + 搜索按钮 ---------- */
.text-search-wrap {
  margin-left: auto;
  display: flex;
  align-items: stretch;
  gap: 0;
}
.text-search-input {
  width: 370px;
}
.text-search-input :deep(.el-input__wrapper) {
  height: 40px;
  padding: 0 12px;
  border-radius: 8px 0 0 8px;
  box-shadow: 0 0 0 1px #E5E7EB inset;
  font-size: 14px;
  transition: box-shadow 0.2s;
}
.text-search-input :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #884BFF inset;
}
.text-search-input :deep(.el-input.is-focus .el-input__wrapper) {
  box-shadow: 0 0 0 1px #884BFF inset;
}
.text-search-input :deep(.el-input__inner::placeholder) {
  color: #9CA3AF;
}
.text-search-btn {
  width: 95px;
  height: 40px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(90deg, #884BFF 0%, #7530FE 100%);
  color: #fff;
  border: none;
  border-radius: 0 8px 8px 0;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.2s;
  margin-left: -1px;
}
.text-search-btn:hover:not(:disabled) {
  opacity: 0.92;
}
.text-search-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* ---------- 图搜图：选择区 + 搜索按钮 ---------- */
.image-search-actions {
  margin-left: auto;
  display: flex;
  align-items: stretch;
  gap: 0;
}
.image-search-select-wrap {
  width: 370px;
  height: 40px;
  padding: 0 12px;
  border-radius: 8px 0 0 8px;
  box-shadow: 0 0 0 1px #E5E7EB inset;
  background: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: box-shadow 0.2s;
}
.image-search-select-wrap:hover {
  box-shadow: 0 0 0 1px #884BFF inset;
}
.image-search-select-text {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  color: #9CA3AF;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.image-search-select-wrap.has-file .image-search-select-text {
  color: #333;
}
.image-search-select-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  opacity: 0.7;
}
.image-search-btn {
  width: 95px;
  height: 40px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(90deg, #884BFF 0%, #7530FE 100%);
  color: #fff;
  border: none;
  border-radius: 0 8px 8px 0;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.2s;
  margin-left: -1px;
}
.image-search-btn:hover:not(:disabled) {
  opacity: 0.92;
}
.image-search-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* ---------- 图搜图：已选图片缩略图 ---------- */
.image-search-selected-wrap {
  margin-bottom: 20px;
}
.image-search-selected-label {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  margin-bottom: 10px;
}
.image-search-selected-preview {
  width: 100px;
  height: 132px;
  border-radius: 10px;
  overflow: hidden;
  background: #D8D8D8;
}
.image-search-selected-img {
  width: 100%;
  height: 100%;
  display: block;
}
.image-search-selected-preview :deep(.el-image) {
  width: 100%;
  height: 100%;
}
.image-search-selected-preview :deep(.el-image__inner) {
  object-fit: cover;
}

/* ---------- 图搜图：相似图片区域横条与标题 ---------- */
.image-search-divider {
  height: 6px;
  background: #F9FAFB;
  border-radius: 0;
  width: 100%;
  margin-bottom: 0;
  margin-top: 10px;
}
.image-search-result-title {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  /* margin: 0 0 12px 0; */
  margin-top: 20px;
  margin-bottom: 0;
}

/* ---------- 页签按钮样式 ---------- */
.main-tab {
  height: 38px;
  padding: 0 24px;
  border: none;
  border-radius: 8px;
  background: #FFFFFF;
  color: #666666;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.main-tab:hover:not(.active) {
  background: #F9FAFB;
  color: #666666;
  border-radius: 30px;
}
.main-tab.active {
  width: 90px;
  height: 38px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(132, 70, 255, 0.2);
  border-radius: 30px;
  color: #8446FF;
  border-color: transparent;
  box-shadow: none;
}

/* ---------- Tab 内容区 ---------- */
.tab-content {
  margin-top: 12px;
}
.tab-content-images {
  display: flex;
  flex-direction: column;
  min-height: 60vh;
}
.tab-content-images .empty-state {
  flex: 1;
}

/* ---------- 隐藏 file input（上传/图搜图选择） ---------- */
.file-input-hidden {
  position: absolute;
  width: 0.1px;
  height: 0.1px;
  opacity: 0;
  overflow: hidden;
  z-index: -1;
}

/* ---------- 图片网格（我的图片 / 文搜图 / 图搜图结果） ---------- */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, 194px);
  gap: 20px;
  margin-top: 12px;
  justify-content: start;
}
.item {
  width: 194px;
  height: 298px;
  border-radius: 11px;
  border: 1px solid #E5E7EB;
  overflow: hidden;
  background: #fff;
  display: flex;
  flex-direction: column;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-radius 0.2s ease;
}
.item:hover {
  transform: scale(1.05);
  box-shadow: 0 0 12px 2px rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  border: 1px solid #E5E7EB;
}
.item-img-wrap {
  width: 194px;
  height: 259px;
  flex-shrink: 0;
  overflow: hidden;
  border-radius: 0;
}
.item-img {
  width: 100%;
  height: 100%;
  display: block;
  cursor: pointer;
}
.item-img :deep(.el-image__inner) {
  width: 100% !important;
  height: 100% !important;
  object-fit: cover;
}
.item-name {
  flex: 1;
  min-width: 0;
  min-height: 40px;
  padding: 0 12px;
  font-weight: 400;
  font-size: 16px;
  color: #222222;
  display: flex;
  align-items: center;
  justify-content: flex-start;
}
.item-name-text {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---------- 缺省态（暂无数据 / 找找看） ---------- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px 0;
}
.empty-state-img {
  width: 315px;
  height: 169px;
  object-fit: contain;
  display: block;
}
.empty-state-text {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
}
</style>
