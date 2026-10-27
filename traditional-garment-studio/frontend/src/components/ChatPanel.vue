<script setup>
import { nextTick, ref, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import { useDesignStore } from '../stores/design'
import VisionSettings from './VisionSettings.vue'

const chat = useChatStore()
const design = useDesignStore()
const inputText = ref('')
const pendingImage = ref(null) // { url, file }
const fileInput = ref(null)
const msgList = ref(null)

// 消息更新自动滚到底部
watch(
  () => chat.messages.length,
  async () => {
    await nextTick()
    if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
  }
)

function send() {
  if (chat.task.running || design.patternUpdating) return
  const text = inputText.value.trim()
  const image = pendingImage.value?.url || null
  if (!text && !image) return
  chat.submit({ text, image, imageFile: pendingImage.value?.file || null })
  inputText.value = ''
  pendingImage.value = null
}

function onEnter(event) {
  // Chinese IME uses Enter to choose a candidate; only a completed keystroke sends.
  if (event.isComposing || event.keyCode === 229 || event.repeat) return
  event.preventDefault()
  send()
}

// 选图 → 预览待发送（图文一起发的交互：先打字再传图，与 NiceGUI 行为一致）
function onFileChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  clearPending()
  pendingImage.value = { url: URL.createObjectURL(file), file }
  e.target.value = ''
}

function uploadNow() {
  if (pendingImage.value) send()
}

function clearPending() {
  if (pendingImage.value?.url) URL.revokeObjectURL(pendingImage.value.url)
  pendingImage.value = null
}

function addTag(tag) {
  inputText.value = (inputText.value ? inputText.value + ' ' : '') + tag
}
</script>

<template>
  <div class="chat-panel">
    <VisionSettings />
    <div class="image-scope">
      <el-switch :model-value="chat.imageScope === 'outfit'" active-text="完整服饰识图"
        aria-label="图片识别整套服饰" :disabled="chat.task.running || design.patternUpdating"
        @update:model-value="v => chat.imageScope = v ? 'outfit' : 'component'" />
      <span v-if="chat.imageScope === 'outfit'">整件袍衫或上衣＋下裙，可配直领对襟上衣、褙子、半臂、对襟比甲、云肩或直幅披帛。</span>
      <span v-else>单件/局部识图：可单独制作领片或袖片。</span>
    </div>
    <!-- 对话流 -->
    <div ref="msgList" class="msg-list">
      <div v-if="!chat.messages.length && design.pattern" class="empty-hint">
        已恢复上次纸样，可继续调整尺寸或下载<br />
        <span class="hint-sub">原参考图可点“本次参考图”查看；新上传的图片会先核对整套衣物，再请求确认。</span>
      </div>
      <div v-else-if="!chat.messages.length" class="empty-hint">
        描述你想要的服装，或上传参考图开始设计<br />
        <span class="hint-sub">支持交领、圆领、立领整件袍衫；交领等上衣可配马面裙或襦裙下裳。完整识图默认开启；独立领片、袖片请切换局部识图。</span>
      </div>

      <div v-for="m in chat.messages" :key="m.id" class="msg-row" :class="m.role">
        <div class="bubble" :class="m.role">
          <img v-if="m.image" :src="m.image" class="msg-img" alt="参考图" />
          <div v-if="m.text" class="msg-text">{{ m.text }}</div>
          <!-- RAG 溯源卡片（rag-plan.md §3.6） -->
          <div v-if="m.type === 'sources'" class="rag-sources">
            <div class="rag-title">
              <el-icon><Document /></el-icon>&nbsp;参考资料
            </div>
            <div v-for="(s, i) in m.sources" :key="i" class="rag-item">
              <div class="rag-item-head">
                <span class="rag-name">{{ s.title }}</span>
                <span class="rag-score">{{ (s.score * 100).toFixed(0) }}%</span>
              </div>
              <div class="rag-snippet">{{ s.snippet }}</div>
            </div>
          </div>
          <div class="msg-time">{{ m.time }}</div>
          <el-button
            v-if="m.id === chat.retryMessageId && chat.lastInput"
            size="small"
            text
            type="primary"
            class="retry-btn"
            :disabled="chat.task.running || design.patternUpdating"
            @click="chat.retry()"
          >
            {{ m.retryLabel || (m.role === 'error' ? '重试' : '重新识别这张图片') }}
          </el-button>
        </div>
      </div>

      <!-- 任务进度（运行中） -->
      <div v-if="chat.task.running" class="task-progress">
        <div class="stage-label">
          <el-icon class="rotating"><Loading /></el-icon>
          {{ chat.stageLabel }}…
        </div>
        <el-progress :percentage="chat.task.progress" :stroke-width="8" />
      </div>
    </div>

    <!-- 快捷标签 -->
    <div v-if="chat.suggestedComponent && chat.innerwearChoices?.length" class="opening-choices">
      <el-button v-for="choice in chat.innerwearChoices" :key="choice.id" type="primary" plain
        :disabled="design.patternUpdating || chat.task.running" @click="chat.confirmComponent(null, null, choice.id)">
        {{ choice.label }}，继续
      </el-button>
    </div>
    <div v-else-if="chat.suggestedComponent && chat.skirtChoices?.length" class="opening-choices">
      <el-button v-for="choice in chat.skirtChoices" :key="choice.id" type="primary" plain
        :disabled="design.patternUpdating || chat.task.running" @click="chat.confirmComponent(null, choice.id)">
        {{ choice.label }}，继续
      </el-button>
    </div>
    <div v-else-if="chat.suggestedComponent && chat.openingChoices?.length" class="opening-choices">
      <span v-if="chat.openingChoiceName">{{ chat.openingChoiceName }}的开襟</span>
      <el-button v-for="choice in chat.openingChoices" :key="choice.id" type="primary" plain
        :disabled="design.patternUpdating || chat.task.running" @click="chat.confirmComponent(choice.id)">
        选择{{ choice.label }}，继续
      </el-button>
    </div>
    <el-button v-else-if="chat.suggestedComponent" type="primary" plain :disabled="design.patternUpdating || chat.task.running" @click="chat.confirmComponent()">
      确认制作{{ chat.suggestedComponent }}（使用建议参数）
    </el-button>
    <div v-if="chat.quickTags.length" class="quick-tags" role="group" aria-label="款式示例">
      <el-tag
        v-for="t in chat.quickTags"
        :key="t"
        class="qtag"
        effect="plain"
        @click="addTag(t)"
      >
        {{ t }}
      </el-tag>
    </div>

    <!-- 待发送图片预览 -->
    <div v-if="pendingImage" class="pending-img">
      <img :src="pendingImage.url" alt="待发送" />
      <div class="pending-actions">
        <el-button size="small" type="primary" :disabled="design.patternUpdating || chat.task.running" @click="uploadNow">发送图片</el-button>
        <el-button size="small" text @click="clearPending">移除</el-button>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-row">
      <el-tooltip content="上传参考图" placement="top">
        <el-button circle text aria-label="上传参考图" @click="fileInput.click()">
          <el-icon><PictureFilled /></el-icon>
        </el-button>
      </el-tooltip>
      <input ref="fileInput" type="file" accept="image/*" hidden @change="onFileChange" />
      <el-input
        v-model="inputText"
        placeholder="描述你的设计或上传参考图…"
        :disabled="chat.task.running || design.patternUpdating"
        @keydown.enter="onEnter"
      />
      <el-button type="primary" :loading="chat.task.running" :disabled="design.patternUpdating" @click="send">
        <el-icon v-if="!chat.task.running"><Promotion /></el-icon>&nbsp;发送
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.opening-choices { display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 10px; flex-shrink: 0; }
.opening-choices .el-button { margin-left: 0; flex: 1 1 auto; }
.image-scope { padding: 0 12px 6px; font-size: 11px; color: #8a929c; display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; }
.chat-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 12px;
  gap: 8px;
}
.msg-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px;
}
.empty-hint {
  text-align: center;
  color: #909399;
  margin-top: 80px;
  line-height: 1.8;
}
.hint-sub {
  font-size: 12px;
  opacity: 0.7;
}
.msg-row {
  display: flex;
  margin-bottom: 10px;
}
.msg-row.user {
  justify-content: flex-end;
}
.msg-row.assistant {
  justify-content: flex-start;
}
.msg-row.error {
  justify-content: center;
}
.bubble {
  max-width: 82%;
  padding: 8px 12px;
  border-radius: 10px;
  position: relative;
}
.bubble.user {
  background: var(--el-color-primary);
  color: #fff;
}
.bubble.assistant {
  background: #f4f4f5;
  color: #303133;
}
.bubble.error {
  background: #fef0f0;
  color: var(--el-color-danger);
  border: 1px solid #fbc4c4;
  font-size: 13px;
}
.msg-text {
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-time {
  font-size: 10px;
  opacity: 0.6;
  margin-top: 2px;
  text-align: right;
}
.msg-img {
  max-width: 180px;
  border-radius: 6px;
  margin-bottom: 6px;
  display: block;
}
.retry-btn {
  margin-top: 4px;
  padding: 2px 0;
}
.task-progress {
  background: #f9fafc;
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  padding: 10px 12px;
}
.stage-label {
  font-size: 13px;
  color: var(--el-color-primary);
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.rotating {
  animation: rotate 1.2s linear infinite;
}
@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
.quick-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex-shrink: 0;
  max-height: 62px;
  overflow: auto;
}
.qtag {
  cursor: pointer;
  flex-shrink: 0;
}
.qtag:hover {
  opacity: 0.8;
}
.pending-img {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}
.pending-img img {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: 6px;
}
.pending-actions {
  display: flex;
  gap: 4px;
}
.rag-sources {
  margin-top: 6px;
  padding: 8px 10px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}
.rag-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
}
.rag-item {
  padding: 6px 0;
  border-top: 1px dashed #ebeef5;
}
.rag-item:first-of-type {
  border-top: none;
}
.rag-item-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}
.rag-name {
  font-weight: 600;
  color: #303133;
}
.rag-score {
  color: var(--el-color-primary);
}
.rag-snippet {
  font-size: 12px;
  color: #606266;
  margin-top: 3px;
  line-height: 1.5;
}
.input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
@media (max-width: 800px) {
  .quick-tags { flex-wrap: nowrap; max-height: none; padding-bottom: 5px; }
  .empty-hint { margin-top: 18px; }
}
</style>
