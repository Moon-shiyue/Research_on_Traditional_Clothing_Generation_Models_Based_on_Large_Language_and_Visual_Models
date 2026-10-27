/**
 * 设计参数 / 人体尺寸 / 版型状态
 * schema 驱动：params.*.* = { v, type, range }（契约 §1.2）
 */
import { defineStore } from 'pinia'
import { api } from '../api'
import { loadDesignState, applyDesignResult } from './designLoading.js'

export const useDesignStore = defineStore('design', {
  state: () => ({
    designParams: null, // { body_id, is_sectioned, params }
    bodyParams: null, // { body_id, available_bodies, params }
    pattern: null, // GET /pattern 响应
    patternUpdating: false,
    designList: [],
    loaded: false,
    loadError: '',
    editRevision: 0,
    loadRevision: 0,
  }),

  getters: {
    sections: (s) => {
      if (!s.designParams?.params) return []
      return Object.keys(s.designParams.params)
    },
  },

  actions: {
    async loadAll() {
      return loadDesignState(this, api)
    },

    // 单参数更新（path: ['left','sleeve','length']）
    async updateParam(path, value, unit = 'native') {
      this.patternUpdating = true
      try {
        await api.updateDesignParam(path, value, unit)
        await this.loadAll()
      } catch (error) {
        this.loadError = error.message || '参数更新未完成。'
        this.editRevision++
      } finally {
        this.patternUpdating = false
      }
    },

    async updateBodyParam(path, value) {
      this.patternUpdating = true
      try {
        await api.updateBodyParam(path, value)
        await this.loadAll()
      } catch (error) {
        this.loadError = error.message || '人体尺寸更新未完成。'
        this.editRevision++
      } finally {
        this.patternUpdating = false
      }
    },

    async randomDesign() {
      this.patternUpdating = true
      try {
        await api.randomDesign()
        await this.loadAll()
      } catch (error) {
        this.loadError = error.message || '随机设计未完成。'
      } finally {
        this.patternUpdating = false
      }
    },

    async defaultDesign() {
      this.patternUpdating = true
      try {
        await api.defaultDesign()
        await this.loadAll()
      } catch (error) {
        this.loadError = error.message || '恢复默认未完成。'
      } finally {
        this.patternUpdating = false
      }
    },

    async restoreDesign(designId) {
      if (this.patternUpdating) return false
      this.patternUpdating = true
      this.loadError = ''
      try {
        const result = await api.restoreDesign(designId)
        this.applyParseResult(result)
        this.loaded = true
        this.editRevision++
        return true
      } catch (error) {
        this.loadError = error.message || '恢复纸样未完成，当前结果已保留。'
        return false
      } finally {
        this.patternUpdating = false
      }
    },

    // parse 成功后应用结果（design_params 全量 + pattern + design_list）
    applyParseResult(result) {
      applyDesignResult(this, result)
    },

    async download() {
      try { await api.download() } catch (error) { this.loadError = error.message || '下载未完成。' }
    },
  },
})
