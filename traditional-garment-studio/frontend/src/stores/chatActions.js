/** Request lifecycle used by the Pinia store and controlled transport tests. */
export function createChatState() {
  return {
    messages: [], // { id, role: 'user'|'assistant'|'error', text, image, time }
    task: {
      running: false,
      taskId: null,
      stage: '', // queued|parsing|projecting|pattern|rendering
      progress: 0,
    },
    lastInput: null, // 失败重试用 { text, image }
    proposalInput: null, // Original image/text/scope retained until confirmation completes.
    lastOutcome: 'idle',
    retryMessageId: null,
    resumeTaskId: null,
    suggestedComponent: null,
    suggestedRequest: null,
    imageProposalId: null,
    openingChoices: [],
    openingChoiceName: null,
    skirtChoices: [],
    innerwearChoices: [],
    quickTags: [],
    imageScope: 'outfit',
  }
}

export function createChatActions({ api, getDesignStore }) {
  return {
    async loadVocab() {
      try {
        const v = await api.getVocab()
        this.quickTags = v.quick_tags || []
      } catch {
        /* 词表接口失败不影响主流程 */
      }
    },

    pushMessage(msg) {
      const entry = {
        id: Date.now() + Math.random(),
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        ...msg,
      }
      this.messages.push(entry)
      return entry
    },

    // 发起解析（自动路由 mode: auto）
    async submit({ text, image, imageFile = null, imageProposalId = null, imageReference = null, scope = null, openingChoice = null, skirtChoice = null, innerwearChoice = null, displayText = null, requestId = null }) {
      if (this.task.running || getDesignStore().patternUpdating) {
        this.pushMessage({ role: 'error', text: '正在生成中，请稍候…' })
        return
      }
      if (!text && !image) return

      scope = scope || this.imageScope
      this.imageScope = scope
      if (!imageProposalId) this.proposalInput = null
      requestId = requestId || crypto.randomUUID()
      this.lastInput = { text, image, imageFile, imageProposalId, imageReference, scope, openingChoice, skirtChoice, innerwearChoice, displayText, requestId }
      this.lastOutcome = 'running'
      this.retryMessageId = null
      this.resumeTaskId = null
      this.suggestedComponent = null
      this.suggestedRequest = null
      this.imageProposalId = null
      this.openingChoices = []
      this.openingChoiceName = null
      this.skirtChoices = []
      this.innerwearChoices = []
      this.pushMessage({ role: 'user', text: displayText || text || '（图片输入）', image })

      this.task = { running: true, taskId: null, stage: 'queued', progress: 0 }
      try {
        if (!imageReference && imageFile) {
          const uploaded = await api.uploadImage(imageFile)
          imageReference = uploaded.image_id || uploaded.url || uploaded.path
        } else if (!imageReference && image && !image.startsWith('blob:')) {
          imageReference = image
        }
        this.lastInput.imageReference = imageReference
        const { task_id } = await api.parse(
          { mode: 'auto', text, image: imageReference, image_proposal_id: imageProposalId, scope,
            request_id: requestId,
            ...(openingChoice ? { opening_choice:openingChoice } : {}),
            ...(skirtChoice ? { skirt_choice:skirtChoice } : {}),
            ...(innerwearChoice ? { innerwear_choice:innerwearChoice } : {}) },
          {
            onProgress: ({ stage, progress }) => {
              this.task.stage = stage
              this.task.progress = progress
            },
            onMessage: ({ content }) => {
              this.pushMessage({ role: 'assistant', text: content })
            },
            onResult: (result) => this.handleResult(result),
            onError: (error) => this.handleError(error),
          }
        )
        this.task.taskId = task_id
      } catch (e) {
        this.handleError(e)
      }
    },

    handleResult(result) {
      const input = this.lastInput
      this.resumeTaskId = null
      this.task.running = false
      this.task.progress = 100
      this.suggestedComponent = result.suggested_name || null
      this.suggestedRequest = result.suggested_text || result.suggested_name || null
      this.imageProposalId = result.image_proposal_id || null
      this.openingChoices = result.opening_choices || []
      this.openingChoiceName = result.opening_choice_name || null
      this.skirtChoices = result.skirt_choices || []
      this.innerwearChoices = result.innerwear_choices || []
      this.lastOutcome = result.status === 'generated' ? 'generated'
        : this.imageProposalId && this.suggestedComponent ? 'awaiting_confirmation' : 'needs_input'
      if (this.imageProposalId && input?.image) {
        this.proposalInput = { ...input, imageProposalId: null }
      } else if (result.status === 'generated') {
        this.proposalInput = null
      }
      const message = this.pushMessage({ role: 'assistant', text: result.reply })
      this.retryMessageId = result.image_retry_available && this.lastInput ? message.id : null
      if (this.retryMessageId) this.lastInput.requestId = null
      if (this.retryMessageId) message.retryLabel = '重新识别这张图片'
      if (!this.retryMessageId) this.lastInput = null
      // 语义标签随消息展示
      if (result.design_list?.length) {
        this.pushMessage({ role: 'assistant', text: '制作内容：' + result.design_list.join('、') })
      }
      // RAG 溯源资料（rag-plan.md §3.6）
      if (result.rag_sources?.length) {
        this.pushMessage({ role: 'assistant', type: 'sources', sources: result.rag_sources })
      }
      // 通知设计/版型状态更新
      const design = getDesignStore()
      design.applyParseResult(result)
    },

    async confirmComponent(openingChoice = null, skirtChoice = null, innerwearChoice = null) {
      if (!this.suggestedComponent || this.task.running || getDesignStore().patternUpdating) return
      if (this.openingChoices.length && !this.openingChoices.some(c => c.id === openingChoice)) return
      if (this.skirtChoices.length && !this.skirtChoices.some(c => c.id === skirtChoice)) return
      if (this.innerwearChoices?.length && !this.innerwearChoices.some(c => c.id === innerwearChoice)) return
      if (!this.imageProposalId) {
        this.handleError({ code: 'invalid_image_proposal', message: '图片建议已失效，请重新识别后确认。' })
        return
      }
      const name = this.suggestedRequest || this.suggestedComponent
      const chosen = this.innerwearChoices?.find(c => c.id === innerwearChoice) || this.skirtChoices.find(c => c.id === skirtChoice) || this.openingChoices.find(c => c.id === openingChoice)
      // The server's suggested_text preserves original dimensions and style.
      await this.submit({text:name,image:null,imageProposalId:this.imageProposalId,
        scope:this.proposalInput?.scope || this.imageScope,openingChoice,skirtChoice,innerwearChoice,
        displayText:chosen ? `选择：${chosen.label}` : null})
    },

    handleError(error) {
      this.task.running = false
      this.lastOutcome = 'error'
      const code = error?.code
      const message = typeof error === 'string' ? error : error?.message || '请求失败'
      let retryLabel = '重试'
      this.resumeTaskId = null
      if (['network_error', 'task_timeout', 'server_error'].includes(code) && this.task.taskId && this.lastInput
          && typeof api.resumeTask === 'function') {
        this.resumeTaskId = this.task.taskId
        retryLabel = '继续查看本次结果'
      }
      if (code === 'task_not_found' && this.proposalInput) {
        this.lastInput = { ...this.proposalInput, imageProposalId: null, requestId: null }
        this.proposalInput = null
        retryLabel = '重新识别这张图片'
      }
      if (code === 'invalid_image_proposal') {
        this.lastInput = this.proposalInput ? { ...this.proposalInput, imageProposalId: null, requestId: null } : null
        this.proposalInput = null
        retryLabel = '重新识别这张图片'
      }
      if (code === 'image_not_found' && this.lastInput) {
        this.lastInput = this.lastInput.imageFile ? { ...this.lastInput, imageReference: null, requestId: null } : null
        retryLabel = '重新上传并识别'
      }
      this.suggestedComponent = null
      this.suggestedRequest = null
      this.imageProposalId = null
      this.openingChoices = []
      this.openingChoiceName = null
      this.skirtChoices = []
      this.innerwearChoices = []
      const entry = this.pushMessage({ role: 'error', text: message, retryLabel })
      if (this.lastInput && !['network_error', 'task_timeout'].includes(code)) this.lastInput.requestId = null
      this.retryMessageId = this.lastInput ? entry.id : null
    },

    // Restoring a saved design invalidates any pending image confirmation.
    onDesignRestored() {
      this.lastInput = null
      this.proposalInput = null
      this.retryMessageId = null
      this.resumeTaskId = null
      this.suggestedComponent = null
      this.suggestedRequest = null
      this.imageProposalId = null
      this.openingChoices = []
      this.openingChoiceName = null
      this.skirtChoices = []
      this.innerwearChoices = []
      this.lastOutcome = 'generated'
      this.pushMessage({ role: 'assistant', text: '已恢复所选纸样、款式参数和人体尺寸；参考图仍以纸样区为准。' })
    },

    // 失败重试
    async retry() {
      if (!this.lastInput || this.task.running || getDesignStore().patternUpdating) return
      if (this.resumeTaskId && typeof api.resumeTask === 'function') {
        const taskId = this.resumeTaskId
        this.resumeTaskId = null
        this.retryMessageId = null
        this.lastOutcome = 'running'
        this.task = { ...this.task, running: true, taskId }
        this.pushMessage({ role: 'assistant', text: '继续查看本次生成结果，无需重新提交图片。' })
        try {
          await api.resumeTask(taskId, {
            onProgress: ({ stage, progress }) => { this.task.stage = stage; this.task.progress = progress },
            onResult: result => this.handleResult(result),
            onError: error => this.handleError(error),
          })
        } catch (error) { this.handleError(error) }
        return
      }
      const { text, image, imageFile, imageProposalId, imageReference, scope, openingChoice, skirtChoice, innerwearChoice, displayText, requestId } = this.lastInput
      this.lastInput = null
      await this.submit({ text, image, imageFile, imageProposalId, imageReference, scope, openingChoice, skirtChoice, innerwearChoice, displayText, requestId })
    },
  }
}
