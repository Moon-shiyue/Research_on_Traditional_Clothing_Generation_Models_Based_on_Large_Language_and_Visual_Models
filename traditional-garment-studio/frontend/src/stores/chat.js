/**
 * 聊天与任务状态
 * 消息仅前端自持（契约 §0.4），设计状态在 design store / 服务端
 */
import { defineStore } from 'pinia'
import { api } from '../api'
import { createChatActions, createChatState } from './chatActions.js'
import { useDesignStore } from './design'

export const useChatStore = defineStore('chat', {
  state: createChatState,

  getters: {
    stageLabel: (s) => {
      const map = {
        queued: '已入队',
        parsing: 'AI 解析设计意图',
        projecting: '生成制版参数',
        pattern: '组装版型',
        rendering: '渲染裁片',
      }
      return map[s.task.stage] || '处理中'
    },
  },

  actions: createChatActions({ api, getDesignStore: useDesignStore }),
})
