<script setup>
/**
 * RAG 穿搭问答页。
 *
 * 支持多会话、短期记忆和删除会话；用户界面保持和现有页面一致的简洁风格。
 */
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '../store/auth'
import {
  deleteRagConversation,
  ragChatStreamUrl,
  ragConversationMessages,
  ragConversations,
} from '../services/api'
import submitIcon from '../assets/image/submit.svg'

const question = ref('')
const conversations = ref([])
const activeConversationId = ref(null)
const messages = ref([])
const isLoading = ref(false)
const isStreaming = ref(false)
const thinkingExpanded = ref(true)
const currentThinkingStep = ref(0)
const auth = useAuthStore()
let thinkingTimer = null
let answerTimer = null

const thinkingSteps = [
  '理解你的穿搭需求',
  '匹配相关穿搭知识',
  '整理适合的单品和风格',
  '生成可直接参考的建议',
]

const exampleQuestions = [
  '男生苹果型身材，夏天怎么穿显瘦？',
  '女生梨形身材，通勤怎么穿更利落？',
  '约会想穿得干净自然，有什么搭配建议？',
]

const clearThinkingTimer = () => {
  if (thinkingTimer) {
    clearInterval(thinkingTimer)
    thinkingTimer = null
  }
}

const clearAnswerTimer = () => {
  if (answerTimer) {
    clearInterval(answerTimer)
    answerTimer = null
  }
}

const startThinkingProgress = () => {
  clearThinkingTimer()
  thinkingExpanded.value = true
  currentThinkingStep.value = 0
  thinkingTimer = setInterval(() => {
    if (currentThinkingStep.value < thinkingSteps.length - 1) {
      currentThinkingStep.value += 1
    }
  }, 1200)
}

const streamAssistantMessage = (messageItem, text) => {
  clearAnswerTimer()
  messageItem.content = ''
  isStreaming.value = true
  const cleanText = normalizeAnswerText(text)

  let index = 0
  answerTimer = setInterval(() => {
    messageItem.content = cleanText.slice(0, index + 1)
    index += 1
    if (index >= cleanText.length) {
      clearAnswerTimer()
      isStreaming.value = false
    }
  }, 18)
}

/** 把模型常见 Markdown 符号清理成更适合聊天气泡展示的文本。 */
const normalizeAnswerText = (text) => {
  return String(text || '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/^\s*[-*]\s+/gm, '• ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

const parseSseBlock = (block) => {
  const dataLine = block.split('\n').find((line) => line.startsWith('data:'))
  if (!dataLine) return null
  const jsonText = dataLine.replace(/^data:\s*/, '').trim()
  return jsonText ? JSON.parse(jsonText) : null
}

const readRagStream = async (payload, assistantMessage) => {
  const response = await fetch(ragChatStreamUrl(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${auth.token}`,
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok || !response.body) {
    throw new Error('问答请求失败，请稍后再试')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let pendingText = ''
  let frameId = null

  // 真正的流式输出：收到后端 SSE 的 delta 后，下一帧直接追加到页面。
  const flushPendingText = () => {
    if (pendingText) {
      assistantMessage.content = `${assistantMessage.content}${pendingText}`
      pendingText = ''
    }
    frameId = null
  }

  const appendStreamText = (text) => {
    if (!text) return
    pendingText += text
    if (frameId !== null) return
    frameId = requestAnimationFrame(flushPendingText)
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''

    for (const block of blocks) {
      const event = parseSseBlock(block)
      if (!event) continue

      if (event.type === 'start') {
        activeConversationId.value = event.conversationId || activeConversationId.value
      }

      if (event.type === 'progress') {
        currentThinkingStep.value = Math.min(currentThinkingStep.value + 1, thinkingSteps.length - 1)
      }

      if (event.type === 'delta') {
        appendStreamText(event.text || '')
      }

      if (event.type === 'done') {
        activeConversationId.value = event.conversationId || activeConversationId.value
      }

      if (event.type === 'error') {
        throw new Error(event.message || '生成回答失败')
      }
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    const event = parseSseBlock(buffer)
    if (event?.type === 'delta') {
      appendStreamText(event.text || '')
    }
  }
  if (frameId !== null) {
    cancelAnimationFrame(frameId)
  }
  flushPendingText()
  assistantMessage.content = normalizeAnswerText(assistantMessage.content)
}

const fetchConversations = async () => {
  try {
    const { data } = await ragConversations()
    conversations.value = data.data || []
  } catch (err) {
    ElMessage.error(err?.message || '加载会话失败')
  }
}

const loadConversationMessages = async (conversationId) => {
  if (!conversationId) return
  try {
    activeConversationId.value = conversationId
    clearAnswerTimer()
    const { data } = await ragConversationMessages(conversationId)
    messages.value = data.data || []
  } catch (err) {
    ElMessage.error(err?.message || '加载聊天记录失败')
  }
}

const startNewConversation = () => {
  activeConversationId.value = null
  messages.value = []
  question.value = ''
  clearAnswerTimer()
  clearThinkingTimer()
}

const removeConversation = async (conversationId) => {
  try {
    await ElMessageBox.confirm('确定删除这个会话吗？', '删除会话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteRagConversation(conversationId)
    if (activeConversationId.value === conversationId) startNewConversation()
    await fetchConversations()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err?.message || '删除会话失败')
  }
}

const submitQuestion = async () => {
  const text = question.value.trim()
  if (!text) {
    ElMessage.warning('请输入穿搭问题')
    return
  }

  const userMessage = {
    id: `local-user-${Date.now()}`,
    role: 'user',
    content: text,
  }
  messages.value.push(userMessage)
  question.value = ''

  try {
    isLoading.value = true
    isStreaming.value = false
    startThinkingProgress()
    const { data } = await ragChat({
      message: text,
      conversationId: activeConversationId.value,
      topK: 5,
    })
    const result = data.data || {}
    const answer = result.answer || ''
    if (!answer) {
      ElMessage.warning('后端没有返回回答内容')
      return
    }

    activeConversationId.value = result.conversationId || activeConversationId.value
    clearThinkingTimer()
    currentThinkingStep.value = thinkingSteps.length - 1

    const assistantMessage = {
      id: `local-assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
    }
    messages.value.push(assistantMessage)
    streamAssistantMessage(assistantMessage, answer)
    await fetchConversations()
  } catch (err) {
    clearThinkingTimer()
    clearAnswerTimer()
    ElMessage.error(err?.message || '问答请求失败')
  } finally {
    isLoading.value = false
  }
}

const submitQuestionStream = async () => {
  const text = question.value.trim()
  if (!text) {
    ElMessage.warning('请输入穿搭问题')
    return
  }

  const userMessage = {
    id: `local-user-${Date.now()}`,
    role: 'user',
    content: text,
  }
  const assistantMessage = {
    id: `local-assistant-${Date.now()}`,
    role: 'assistant',
    content: '',
  }
  messages.value.push(userMessage)
  messages.value.push(assistantMessage)
  question.value = ''

  try {
    isLoading.value = true
    isStreaming.value = true
    startThinkingProgress()
    await readRagStream({
      message: text,
      conversationId: activeConversationId.value,
      topK: 5,
    }, assistantMessage)
    clearThinkingTimer()
    currentThinkingStep.value = thinkingSteps.length - 1
    await fetchConversations()
  } catch (err) {
    clearThinkingTimer()
    clearAnswerTimer()
    messages.value = messages.value.filter((item) => item.id !== assistantMessage.id)
    ElMessage.error(err?.message || '问答请求失败')
  } finally {
    isLoading.value = false
    isStreaming.value = false
  }
}

const useExampleQuestion = (text) => {
  question.value = text
}

onMounted(fetchConversations)
</script>

<template>
  <div class="card ui-card rag-page">
    <section class="rag-layout">
      <aside class="conversation-panel">
        <button type="button" class="new-chat-btn" @click="startNewConversation">
          <span class="new-chat-plus">+</span>
          <span>新对话</span>
        </button>
        <div class="conversation-list">
          <button
            v-for="item in conversations"
            :key="item.id"
            type="button"
            class="conversation-item"
            :class="{ active: item.id === activeConversationId }"
            @click="loadConversationMessages(item.id)"
          >
            <span class="conversation-title">{{ item.title }}</span>
            <span class="conversation-delete" @click.stop="removeConversation(item.id)">删除</span>
          </button>
        </div>
      </aside>

      <main class="chat-panel">
        <div class="rag-header">
          <h2 class="rag-title">穿搭问答</h2>
        </div>

        <div class="message-list">
          <div v-if="!messages.length && !isLoading" class="chat-empty">
            <h3 class="chat-empty-title">今天想怎么搭？</h3>
            <div class="rag-examples">
              <button
                v-for="item in exampleQuestions"
                :key="item"
                type="button"
                class="rag-example-btn"
                @click="useExampleQuestion(item)"
              >
                {{ item }}
              </button>
            </div>
          </div>

          <div
            v-for="item in messages"
            :key="item.id"
            class="message-row"
            :class="item.role === 'user' ? 'message-row--user' : 'message-row--assistant'"
          >
            <div class="message-bubble">{{ item.content }}</div>
          </div>

          <div v-if="isLoading" class="rag-answer-box rag-answer-box--loading">
            <div class="thinking-head">
              <span>思考中...</span>
              <button type="button" class="thinking-toggle" @click="thinkingExpanded = !thinkingExpanded">
                {{ thinkingExpanded ? '收起' : '展开' }}
              </button>
            </div>
            <div v-if="thinkingExpanded" class="thinking-steps">
              <div
                v-for="(step, index) in thinkingSteps"
                :key="step"
                class="thinking-step"
                :class="{ active: index <= currentThinkingStep }"
              >
                <span class="thinking-dot"></span>
                <span>{{ step }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="composer-wrap">
          <div class="rag-input-box">
            <textarea
              v-model="question"
              class="rag-textarea"
              rows="3"
              placeholder="输入你的穿搭问题"
              :disabled="isLoading || isStreaming"
            ></textarea>
            <button
              type="button"
              class="rag-submit-btn"
              :disabled="isLoading || isStreaming || !question.trim()"
              @click="submitQuestionStream"
            >
              <img :src="submitIcon" alt="" class="rag-submit-icon" />
              <span>{{ isLoading || isStreaming ? '生成中' : '发送' }}</span>
            </button>
          </div>
        </div>
      </main>
    </section>
  </div>
</template>

<style scoped>
.rag-page {
  padding: 0;
  min-height: calc(100vh - 64px - 18px - 28px - 40px);
}

.rag-layout {
  width: 100%;
  min-height: calc(100vh - 64px - 18px - 28px - 40px);
  margin: 0 auto;
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  background: #FFFFFF;
}

.conversation-panel,
.rag-answer-box {
  background: #FFFFFF;
}

.conversation-panel {
  padding: 18px 12px;
  border-right: 1px solid rgba(16, 24, 40, 0.08);
  background: linear-gradient(180deg, #f7f8fc 0%, #fbfaff 52%, #ffffff 100%);
}

.new-chat-btn {
  width: 100%;
  height: 40px;
  border: 1px solid rgba(123, 85, 255, 0.18);
  border-radius: 8px;
  background: rgba(123, 85, 255, 0.08);
  color: rgba(16, 24, 40, 0.86);
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.new-chat-btn:hover {
  background: rgba(123, 85, 255, 0.13);
}

.new-chat-plus {
  font-size: 20px;
  line-height: 1;
  color: #7530FE;
}

.conversation-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.conversation-item {
  width: 100%;
  border: none;
  background: transparent;
  border-radius: 8px;
  padding: 10px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: rgba(16, 24, 40, 0.72);
  cursor: pointer;
}

.conversation-item.active {
  background: rgba(123, 85, 255, 0.12);
  color: rgba(16, 24, 40, 0.88);
}

.conversation-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.conversation-delete {
  flex-shrink: 0;
  color: #9CA3AF;
  font-size: 12px;
}

.conversation-delete:hover {
  color: #EF4444;
}

.chat-panel {
  min-width: 0;
  min-height: inherit;
  padding: 22px 28px;
  display: flex;
  flex-direction: column;
}

.chat-panel {
  background: #FFFFFF;
}

.rag-header {
  margin-bottom: 8px;
}

.rag-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #111827;
}

.rag-examples {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 18px;
}

.rag-example-btn {
  border: 1px solid #EAEAEA;
  background: #FFFFFF;
  color: rgba(16, 24, 40, 0.72);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  cursor: pointer;
}

.rag-example-btn:hover {
  background: rgba(123, 85, 255, 0.08);
}

.message-list {
  flex: 1;
  min-height: 300px;
  padding: 16px 0 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.chat-empty {
  min-height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.chat-empty-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #111827;
}

.message-row {
  display: flex;
}

.message-row--user {
  justify-content: flex-end;
}

.message-row--assistant {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 76%;
  padding: 12px 14px;
  border-radius: 8px;
  white-space: pre-wrap;
  line-height: 1.8;
  font-size: 14px;
}

.message-row--user .message-bubble {
  background: rgba(123, 85, 255, 0.12);
  color: #111827;
}

.message-row--assistant .message-bubble {
  background: #F7F8FC;
  color: #111827;
}

.composer-wrap {
  display: flex;
  justify-content: center;
  padding-top: 12px;
}

.rag-input-box {
  width: 720px;
  max-width: 100%;
  min-height: 76px;
  padding: 12px 12px 12px 16px;
  border: 1px solid #EAEAEA;
  border-radius: 12px;
  background: #FFFFFF;
  box-shadow: 0px 8px 22px 0px rgba(16, 24, 40, 0.08);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 12px;
}

.rag-textarea {
  width: 100%;
  min-width: 0;
  border: none;
  outline: none;
  resize: vertical;
  font-size: 14px;
  line-height: 1.6;
  font-family: inherit;
  box-sizing: border-box;
  max-height: 140px;
}

.rag-textarea::placeholder {
  color: rgba(16, 24, 40, 0.4);
}

.rag-submit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 78px;
  height: 34px;
  padding: 0;
  background: linear-gradient(90deg, #884BFF 0%, #7530FE 100%);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.rag-submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.rag-submit-icon {
  width: 14px;
  height: 14px;
  display: block;
}

.rag-answer-box {
  padding: 14px 16px;
  border: 1px solid #EAEAEA;
  border-radius: 12px;
  box-shadow: none;
}

.rag-answer-box--loading {
  color: #9CA3AF;
}

.thinking-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #111827;
  font-size: 15px;
  font-weight: 600;
}

.thinking-toggle {
  border: none;
  background: transparent;
  color: #7530FE;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}

.thinking-steps {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.thinking-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #9CA3AF;
}

.thinking-step.active {
  color: rgba(16, 24, 40, 0.82);
}

.thinking-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #D1D5DB;
}

.thinking-step.active .thinking-dot {
  background: #7530FE;
}

@media (max-width: 900px) {
  .rag-layout {
    grid-template-columns: 1fr;
  }
}
</style>
