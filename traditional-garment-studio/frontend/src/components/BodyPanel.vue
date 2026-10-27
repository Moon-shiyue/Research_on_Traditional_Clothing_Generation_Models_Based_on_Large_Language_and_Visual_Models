<script setup>
import { computed } from 'vue'
import { useDesignStore } from '../stores/design'
import { useChatStore } from '../stores/chat'
import { paramLabel, valueLabel } from '../utils/labels'
import CommittedNumber from './CommittedNumber.vue'

const design = useDesignStore()
const chat = useChatStore()
const editingDisabled = computed(() => design.patternUpdating || chat.task.running)
const commonKeys = ['height', 'bust', 'waist', 'hips', 'shoulder_w', 'arm_length', 'neck_w', 'waist_line', 'hips_line']
const commonFields = computed(() => commonKeys.filter(key => key in (design.bodyParams?.params || {})))
const advancedFields = computed(() => Object.keys(design.bodyParams?.params || {}).filter(key => !commonKeys.includes(key)))

function fmtLabel(key) {
  const name = paramLabel(key)
  const unit = key.includes('angle') || key.includes('inclination') || key.endsWith('shoulder_incl') ? '°' : 'cm'
  return `${name}（${unit}${key.startsWith('_') ? '，派生' : ''}）`
}

function onChange(key, val) {
  design.updateBodyParam([key], val)
}
</script>

<template>
  <div class="body-panel" v-if="design.bodyParams">
    <div class="actions">
      <span class="body-id">当前体型：{{ valueLabel(design.bodyParams.body_id) }}</span>
    </div>

    <div class="body-fields">
    <p class="body-hint">先调整常用尺寸。标为固定厘米长度的衣长和袖长会保持不变。</p>
    <div class="fields">
      <div v-for="key in commonFields" :key="key + ':' + design.editRevision" class="field">
        <div class="field-label">{{ fmtLabel(key) }}</div>
        <div v-if="design.bodyParams.parameter_sources?.[key]" class="field-source">{{ design.bodyParams.parameter_sources[key] === 'text' ? '文字指定' : '手动设置' }}</div>
        <CommittedNumber
          :model-value="design.bodyParams.params[key]"
          :precision="2"
          :step="0.5"
          size="small"
          :aria-label="fmtLabel(key)"
          :disabled="editingDisabled"
          controls-position="right"
          @change="(v) => onChange(key, v)"
        />
      </div>
    </div>
    <details class="advanced-fields">
      <summary>更多尺寸与派生值</summary>
      <div class="fields">
        <div v-for="key in advancedFields" :key="key + ':' + design.editRevision" class="field">
          <div class="field-label">{{ fmtLabel(key) }}</div>
          <CommittedNumber
            :model-value="design.bodyParams.params[key]"
            :precision="2" :step="0.5" size="small"
            :aria-label="fmtLabel(key)"
            :disabled="key.startsWith('_') || editingDisabled"
            controls-position="right" @change="(v) => onChange(key, v)"
          />
        </div>
      </div>
    </details>
    </div>
  </div>
  <div v-else class="loading-holder" v-loading="true" element-loading-text="加载体型数据…"></div>
</template>

<style scoped>
.body-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.actions {
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.body-id {
  font-size: 12px;
  color: #909399;
}
.body-fields {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
.body-hint {
  margin: 0 12px 12px;
  color: #78716c;
  font-size: 12px;
  line-height: 1.6;
}
.fields {
  padding: 0 12px 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-content: start;
}
.advanced-fields summary {
  cursor: pointer;
  padding: 4px 12px 12px;
  font-size: 12px;
  color: #57534e;
}
.field-label {
  font-size: 12px;
  color: #78716c;
  margin-bottom: 4px;
}
.field-source { font-size: 11px; color: #929a9f; margin: -2px 0 3px; }
.loading-holder {
  height: 100%;
}
</style>
