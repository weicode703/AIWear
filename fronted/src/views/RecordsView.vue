<script setup>
/**
 * 历史记录页（学生演示项目）
 *
 * 表格展示编辑/合并历史，列：序号、类型、图片1、图片2、指令、执行结果。类型列带下拉筛选（全部/图片编辑/图片合并）。
 * 要点：onMounted 拉取 myRecords；filteredRecordsList 根据 recordTypeFilter 过滤。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { myRecords } from '../services/api'
import emptyDataIcon from '../assets/image/empty-data.svg'

/** 历史记录列表（编辑/合并记录） */
const recordsList = ref([])
/** 历史记录列表是否加载中 */
const isRecordsLoading = ref(false)
/** 类型筛选：'' 全部 | 'edit' 图片编辑 | 'merge' 图片合并 */
const recordTypeFilter = ref('')
/** 类型下拉是否展开，用于三角形翻转 */
const typeFilterDropdownVisible = ref(false)

/** 按类型筛选后的记录列表（供表格展示） */
const filteredRecordsList = computed(() => {
  if (!recordTypeFilter.value) return recordsList.value
  return recordsList.value.filter((row) => row.action === recordTypeFilter.value)
})

/** 类型列展示文案 */
const getRecordTypeLabel = (action) => {
  if (action === 'edit') return '图片编辑'
  if (action === 'merge') return '图片合并'
  return action || '-'
}

/** 拉取历史记录列表 */
const fetchRecordsList = async () => {
  try {
    isRecordsLoading.value = true
    const { data } = await myRecords()
    recordsList.value = data.data || []
  } catch (err) {
    ElMessage.error(err?.message || '查询失败')
  } finally {
    isRecordsLoading.value = false
  }
}

onMounted(fetchRecordsList)
</script>

<template>
  <div class="card ui-card">

    <div v-if="recordsList.length" class="table-wrap">
      <el-table
        :data="filteredRecordsList"
        row-key="id"
        style="width: 100%"
        :loading="isRecordsLoading"
        class="records-table"
      >
        <el-table-column type="index" label="序号" width="72" :index="(index) => index + 1" />
        <el-table-column prop="action" label="类型" width="100" align="center">
          <template #header>
            <el-dropdown trigger="click" @command="(cmd) => (recordTypeFilter = cmd)" @visible-change="(v) => (typeFilterDropdownVisible = v)">
              <span class="filter-trigger">
                类型
                <svg class="filter-triangle" :class="{ 'filter-triangle--open': typeFilterDropdownVisible }" viewBox="0 0 8 6" width="8" height="6" fill="#222222">
                  <path d="M4 6L0 0h8L4 6z" />
                </svg>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :command="''">全部记录</el-dropdown-item>
                  <el-dropdown-item :command="'edit'">图片编辑</el-dropdown-item>
                  <el-dropdown-item :command="'merge'">图片合并</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template #default="{ row }">
            <span
              class="action-badge"
              :class="row.action === 'edit' ? 'action-badge--edit' : 'action-badge--merge'"
            >
              {{ getRecordTypeLabel(row.action) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="图片1" min-width="180" align="center">
          <template #default="{ row }">
            <div v-if="row.inputOssUrl1" class="cell-img-wrap">
              <el-image
                :src="row.inputOssUrl1"
                :preview-src-list="[row.inputOssUrl1]"
                fit="cover"
                class="cell-thumb"
                preview-teleported
              />
            </div>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="图片2" min-width="180" align="center">
          <template #default="{ row }">
            <div v-if="row.inputOssUrl2" class="cell-img-wrap">
              <el-image
                :src="row.inputOssUrl2"
                :preview-src-list="[row.inputOssUrl2]"
                fit="cover"
                class="cell-thumb"
                preview-teleported
              />
            </div>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="指令" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.instruction" class="instruction-text">{{ row.instruction }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="执行结果" min-width="180" align="center">
          <template #default="{ row }">
            <div v-if="row.outputOssUrl" class="cell-img-wrap cell-img-wrap--result">
              <el-image
                :src="row.outputOssUrl"
                :preview-src-list="[row.outputOssUrl]"
                fit="cover"
                class="cell-thumb cell-thumb--result"
                preview-teleported
              />
            </div>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div v-else-if="!isRecordsLoading" class="empty-state">
      <img :src="emptyDataIcon" alt="" class="empty-state-img" />
      <p class="empty-state-text">暂无数据</p>
    </div>
  </div>
</template>

<style scoped>
.card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 64px - 18px - 28px - 40px);
}
/* 类型列表头与其它列对齐，内容居中 */
:deep(.records-table .el-table__header th:has(.filter-trigger)) {
  text-align: center;
}
:deep(.records-table .el-table__header th:has(.filter-trigger) .cell) {
  display: flex;
  align-items: center;
  justify-content: center;
}
.filter-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 600;
  color: rgba(16, 24, 40, 0.85);
  cursor: pointer;
}
/* 实心向下三角形，颜色 #222222；展开时旋转 180deg 朝上 */
.filter-triangle {
  flex-shrink: 0;
  display: block;
  transition: transform 0.2s ease;
}
.filter-triangle--open {
  transform: rotate(180deg);
}
.table-wrap {
  flex: 0 0 auto;
  background: #FFFFFF;
  box-shadow: 0px 4px 10px 0px rgba(0, 0, 0, 0.08);
  border-radius: 6px;
  overflow: hidden;
}
:deep(.records-table) {
  --el-table-border-color: transparent;
  --el-table-header-bg-color: #ECF0FD;
}
:deep(.records-table .el-table__header th),
:deep(.records-table .el-table__body td) {
  border: none;
}
:deep(.records-table .el-table__header th) {
  font-weight: 600;
  font-size: 14px;
  color: rgba(16, 24, 40, 0.85);
}
:deep(.records-table .el-table__body td) {
  font-size: 14px;
  vertical-align: middle;
  overflow: visible;
}
:deep(.records-table .el-table__body td .cell) {
  overflow: visible;
}
/* .cell 内内容上下居中；带 is-center 的列保持水平居中 */
:deep(.records-table .el-table__body td .cell) {
  display: flex;
  align-items: center;
}
:deep(.records-table .el-table__body td.is-center .cell) {
  justify-content: center;
}
.action-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}
.action-badge--edit {
  background: rgba(132, 70, 255, 0.15);
  color: #8446FF;
}
.action-badge--merge {
  background: rgba(59, 130, 246, 0.15);
  color: #3B82F6;
}
.cell-img-wrap {
  position: relative;
  display: inline-block;
  width: 130px;
  height: 162px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #E5E7EB;
  background: #FFFFFF;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-radius 0.2s ease;
}
.cell-img-wrap:hover {
  transform: scale(1.05);
  box-shadow: 0 0 12px 2px rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  border: 1px solid #E5E7EB;
}
.cell-thumb {
  width: 100%;
  height: 100%;
  display: block;
}
.cell-thumb :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cell-thumb--result :deep(.el-image__inner) {
  object-position: center top;
}
.instruction-text {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.muted {
  color: var(--muted);
}
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px 0;
  min-height: 280px;
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
