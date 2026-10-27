<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { api } from '../api'
const opened = ref(false)
const busy = ref(false)
const message = ref('')
const configured = ref(false)
const source = ref('chatgpt_plan')
const plan = ref({ connected: false, accounts: [], pending: false })
const account = ref('')
const models = ref([])
const planModel = ref('')
let timer
const form = reactive({ base_url: 'https://api.openai.com/v1', model: 'gpt-6.1-sol', api_key: '', protocol: 'responses' })
async function refreshPlan() {
  plan.value = await api.getChatGPTStatus()
  if (!account.value && plan.value.active_account) account.value = plan.value.active_account
  if (plan.value.model) planModel.value = plan.value.model
  return plan.value
}
onMounted(async () => {
  try {
    const state = await api.getVisionConfig()
    source.value = state.source || 'chatgpt_plan'
    plan.value = state.chatgpt || plan.value
  } catch { /* Settings shows connection errors when opened. */ }
})
onUnmounted(() => clearTimeout(timer))
async function loadModels() {
  busy.value = true
  try {
    models.value = (await api.getChatGPTModels()).models
    if (!models.value.some(m => m.slug === planModel.value)) {
      planModel.value = models.value.some(m => m.slug === 'gpt-6.1-sol') ? 'gpt-6.1-sol' : (models.value[0]?.slug || '')
    }
    message.value = models.value.length ? '已读取账号可用模型。请选择支持图片的模型并保存；尚未进行真实识图测试。' : '此账号暂未返回可用模型，请检查套餐与授权。'
  } catch (error) { message.value = error.message || '无法读取模型。' }
  finally { busy.value = false }
}
async function changeSource(value) {
  try { await api.selectVisionSource(value); message.value = '' }
  catch (error) { message.value = error.message || '切换未完成。' }
}
async function pollLogin() {
  try {
    const state = await refreshPlan()
    message.value = state.message
    if (state.pending) { timer = setTimeout(pollLogin, 2000); return }
    if (state.connected) {
      await changeSource('chatgpt_plan')
      source.value = 'chatgpt_plan'
      const key = 'garment-plan-welcome-' + state.active_account
      if (!localStorage.getItem(key)) {
        await ElMessageBox.alert('本应用的图片识别将使用你的 ChatGPT 套餐额度，并与 Codex 等用量共用。你可以在 ChatGPT 用量设置中管理本应用限额。', '正在使用 ChatGPT 套餐', { confirmButtonText: '知道了' })
        localStorage.setItem(key, 'seen')
      }
      await loadModels()
    }
  } catch (error) { message.value = error.message || '无法确认登录，请稍后刷新状态。' }
}
async function login() {
  // Create the tab within the click gesture, before the network request.
  const tab = window.open('about:blank', '_blank')
  if (!tab) { message.value = '浏览器阻止了登录窗口，请允许本网站打开弹窗后重试。'; return }
  busy.value = true
  try {
    const result = await api.loginChatGPT(account.value || null)
    tab.opener = null
    tab.location.href = result.authorization_url
    message.value = '请在官方窗口登录，并允许本应用使用 ChatGPT 套餐。'
    await refreshPlan()
    clearTimeout(timer)
    timer = setTimeout(pollLogin, 2000)
  } catch (error) { tab.close(); message.value = error.message || '无法打开登录。' }
  finally { busy.value = false }
}
async function cancelLogin() {
  clearTimeout(timer)
  plan.value = await api.cancelChatGPTLogin()
  message.value = plan.value.message
}
async function logout() {
  busy.value = true
  try {
    clearTimeout(timer)
    plan.value = await api.signOutChatGPT()
    models.value = []
    planModel.value = ''
    message.value = plan.value.message
  } catch (error) { message.value = error.message || '退出未完成。' }
  finally { busy.value = false }
}
async function open() {
  opened.value = true
  message.value = ''
  form.api_key = ''
  try {
    const state = await api.getVisionConfig()
    form.base_url = state.base_url
    form.model = state.model
    form.protocol = state.protocol
    configured.value = state.key_present
    source.value = state.source || 'chatgpt_plan'
    await refreshPlan()
    if (plan.value.pending) { clearTimeout(timer); timer = setTimeout(pollLogin, 2000) }
  } catch (error) { message.value = error.message || '无法读取配置。' }
}
async function save() {
  busy.value = true
  try {
    if (source.value === 'chatgpt_plan') {
      plan.value = await api.selectChatGPTModel(planModel.value)
      message.value = '已启用 ChatGPT 套餐识图。发送图片后才消耗额度；尚未验证真实图片效果。'
      return
    }
    const state = await api.configureVision({ ...form })
    configured.value = state.key_present
    form.api_key = ''
    message.value = '配置已保存到本次后端进程。尚未调用接口；发送图片后才进行识别。'
  } catch (error) { message.value = error.message || '配置未保存。' }
  finally { busy.value = false }
}
async function clear() {
  try {
    await api.clearVisionConfig()
    form.api_key = ''
    configured.value = false
    message.value = '已清除本次进程的 API Key。'
  } catch (error) { message.value = error.message || '清除未完成。' }
}
</script>
<template>
  <div class="vision-settings">
    <span v-if="source === 'chatgpt_plan' && plan.connected" class="plan-label">使用 ChatGPT 套餐</span>
    <el-button size="small" @click="open">云端视觉设置</el-button>
    <el-dialog v-model="opened" title="云端视觉识别" width="560px" @closed="form.api_key = ''">
      <el-radio-group v-model="source" @change="changeSource">
        <el-radio-button value="chatgpt_plan">ChatGPT 套餐额度</el-radio-button>
        <el-radio-button value="api_key">API Key（单独计费）</el-radio-button>
      </el-radio-group>
      <template v-if="source === 'chatgpt_plan'">
        <p class="notice">通过 OpenAI 官方窗口登录并授权。图片识别使用账号套餐额度，与 Codex 共用；不会自动切换到付费 API。</p>
        <el-form label-position="top">
          <el-form-item label="ChatGPT 账号">
            <el-select v-model="account" placeholder="新账号登录，或选择已保存账号" style="width:100%">
              <el-option label="添加新的 ChatGPT 账号" value="" />
              <el-option v-for="item in plan.accounts" :key="item.id" :label="item.label" :value="item.id" />
            </el-select>
          </el-form-item>
        </el-form>
        <p v-if="plan.connected">已登录：{{ plan.accounts.find(a => a.id === plan.active_account)?.label }}</p>
        <div class="actions">
          <el-button :loading="busy" :disabled="plan.pending" @click="login">Continue with ChatGPT</el-button>
          <el-button v-if="plan.pending" @click="cancelLogin">取消登录</el-button>
          <el-button v-if="plan.connected" :disabled="busy" @click="logout">退出登录</el-button>
        </div>
        <el-form v-if="plan.connected" label-position="top">
          <el-form-item label="账号可用模型（请选择支持图片的模型）">
            <el-select v-model="planModel" :placeholder="plan.model || '先读取可用模型'" style="width:100%">
              <el-option v-for="m in models" :key="m.slug" :label="m.display_name" :value="m.slug" />
            </el-select>
          </el-form-item>
          <el-button :loading="busy" @click="loadModels">读取可用模型</el-button>
        </el-form>
        <p class="notice">登录凭据在本机后端受保护保存，不写入浏览器存储或导出包。登录和读取模型不发起图片识别。</p>
        <a href="https://chatgpt.com/settings/usage" target="_blank" rel="noopener noreferrer">管理 ChatGPT 用量与本应用限额</a>
      </template>
      <el-form v-else label-position="top">
        <p class="notice">发送图片时会传给配置的服务商，并按其 API 规则单独计费。</p>
        <el-form-item label="接口基础地址（HTTPS）"><el-input v-model="form.base_url" /></el-form-item>
        <el-form-item label="模型名称"><el-input v-model="form.model" /></el-form-item>
        <el-form-item label="接口协议">
          <el-select v-model="form.protocol">
            <el-option label="OpenAI Responses（官方 GPT 推荐）" value="responses" />
            <el-option label="Chat Completions（兼容服务商）" value="chat_completions" />
          </el-select>
        </el-form-item>
        <el-form-item :label="configured ? 'API Key（已配置，留空沿用）' : 'API Key'">
          <el-input v-model="form.api_key" type="password" autocomplete="off" placeholder="只在此处填写，不要发到聊天中" />
        </el-form-item>
      </el-form>
      <p v-if="source === 'api_key'" class="notice">Key 仅保存在后端内存，后端重启后需重新填写。</p>
      <p v-if="message" role="status">{{ message }}</p>
      <template #footer>
        <el-button v-if="source === 'api_key'" @click="clear">清除 Key</el-button>
        <el-button type="primary" :loading="busy" :disabled="source === 'chatgpt_plan' && (!plan.connected || !planModel)" @click="save">{{ source === 'chatgpt_plan' ? '使用套餐识图' : '保存 API 配置' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<style scoped>
.vision-settings { display: flex; align-items: center; gap: 12px; justify-content: flex-end; }
.plan-label { color: #246d57; font-size: 12px; }
.actions { display: flex; gap: 8px; margin: 14px 0; }
.notice { color: #66717e; font-size: 13px; line-height: 1.7; }
</style>
