<script setup>
import { computed, ref, watch } from 'vue'
import { useDesignStore } from '../stores/design'
import { useChatStore } from '../stores/chat'
import { sectionLabel, groupLabel, paramLabel, valueLabel } from '../utils/labels'
import { parameterControl, wireValue } from '../utils/parameters'
import CommittedNumber from './CommittedNumber.vue'

const design = useDesignStore()
const chat = useChatStore()
const editingDisabled = computed(() => design.patternUpdating || chat.task.running)
const activeSection = ref('meta')

const sectionNames = computed(() => design.sections)
watch(sectionNames, (names) => {
  if (!names.includes(activeSection.value)) activeSection.value = names[0] || ''
}, { immediate: true })

// 兼容两种深度：meta/other 段为「段→参数」扁平结构；left 段为「段→组→参数」嵌套结构
function buildSectionGroups(sectionName, sec) {
  const entries = Object.entries(sec)
  const isFlat = entries.some(([, v]) => v && typeof v === 'object' && 'v' in v)
  if (isFlat) {
    return [
      {
        key: '_all',
        title: sectionLabel(sectionName),
        items: entries
          .filter(([, v]) => 'v' in v)
          .map(([k, v]) => ({ path: [sectionName, k], key: k, ...v })),
      },
    ]
  }
  return entries.map(([groupKey, groupVal]) => ({
    key: groupKey,
    title: groupLabel(groupKey),
    items: Object.entries(groupVal).map(([k, v]) => ({
      path: [sectionName, groupKey, k],
      key: k,
      ...v,
    })),
  }))
}

// 所有分区一次性构建，切换用 v-show（避免组件卸载触发 Element Plus Teleport 的已知崩溃）
const allSections = computed(() => {
  const params = design.designParams?.params
  if (!params) return []
  return Object.entries(params).map(([name, sec]) => ({
    name,
    groups: buildSectionGroups(name, sec),
  }))
})

function fmtLabel(key) {
  return paramLabel(key)
}

function onParamChange(path, val) {
  design.updateParam(path, val)
}

function control(section, item) {
  return parameterControl(section, item, design.bodyParams?.params)
}

function onLengthOrNumberChange(section, item, val) {
  const c = control(section, item)
  if (c.factor !== 1) design.updateParam(item.path, val, 'cm')
  else onParamChange(item.path, wireValue(val, c))
}

function provenance(item) {
  const path = item.path.join('.')
  const source = design.pattern?.parameter_sources?.[path]
  const label = { default: '默认值', text: '文字指定', model: '模型推断', manual: '手动设置',
    image_observation: '图片结构识别', image_style_default: '按图片样式选值', style_default:'按文字样式选值', random: '随机预设', restored_geometry:'从原纸样恢复',user_confirmation:'样式由你确认' }[source]
  if (!label) return ''
  return label + (design.pattern?.absolute_lengths_cm?.[path] != null ? ' · 固定厘米长度' : '')
}
</script>

<template>
  <div class="param-panel" v-if="design.designParams">
    <!-- 顶部操作 -->
    <div class="actions">
      <el-button size="small" @click="design.randomDesign()" :loading="design.patternUpdating" :disabled="chat.task.running">
        随机
      </el-button>
      <el-button size="small" @click="design.defaultDesign()" :disabled="editingDisabled">恢复默认</el-button>
    </div>

    <div class="panel-body">
      <!-- 左：分区导航（仿 NiceGUI 竖向 splitter） -->
      <div class="section-tabs" v-if="design.designParams.is_sectioned">
        <button
          v-for="s in sectionNames"
          :key="s"
          class="section-item"
          type="button"
          :aria-pressed="s === activeSection"
          :class="{ active: s === activeSection }"
          @click="activeSection = s"
        >
          {{ sectionLabel(s) }}
        </button>
      </div>

      <!-- 右：参数组（v-show 切换分区，不卸载组件） -->
      <div class="groups-scroll">
        <div v-for="sec in allSections" :key="sec.name" v-show="sec.name === activeSection">
          <div v-for="g in sec.groups" :key="g.key" class="param-group">
            <div class="group-title">{{ g.title }}</div>

            <div v-for="item in g.items" :key="item.key + ':' + design.editRevision" class="param-item">
              <div class="param-label">{{ (item.type === 'float' || item.type === 'int') ? (control(sec.name, item).label || fmtLabel(item.key)) : fmtLabel(item.key) }}</div>
              <div v-if="provenance(item)" class="param-source">{{ provenance(item) }}</div>
              <div v-if="item.constraint_note" class="param-source">{{ item.constraint_note }}</div>
              <div v-if="['beizi', 'banbi'].includes(sec.name) && item.key === 'sleeve_length'" class="param-source">从人体肩点计，含落肩部分；袖片净长见右图。</div>

              <!-- select -->
              <el-select
                v-if="(item.type || '').startsWith('select')"
                :model-value="item.v"
                size="small"
                :aria-label="fmtLabel(item.key)"
                :disabled="editingDisabled"
                @update:model-value="(val) => onParamChange(item.path, val)"
              >
                <el-option
                  v-for="opt in item.range"
                  :key="String(opt)"
                  :label="item.option_labels?.[opt] || valueLabel(opt)"
                  :value="opt"
                    :disabled="Boolean(item.option_disabled?.[opt])"
                />
              </el-select>

              <!-- bool -->
              <el-switch
                v-else-if="item.type === 'bool'"
                :disabled="editingDisabled"
                :model-value="item.v"
                :aria-label="fmtLabel(item.key)"
                @update:model-value="(val) => onParamChange(item.path, val)"
              />

              <!-- float / int 滑块 -->
              <div v-else-if="item.type === 'float' || item.type === 'int'" class="slider-row">
                <el-slider
                  :model-value="control(sec.name, item).value"
                  :min="control(sec.name, item).min"
                  :max="control(sec.name, item).max"
                  :step="control(sec.name, item).step"
                  :disabled="editingDisabled"
                  :aria-label="control(sec.name, item).label || fmtLabel(item.key)"
                  input-size="small"
                  size="small"
                  @change="(val) => onLengthOrNumberChange(sec.name, item, val)"
                />
                <CommittedNumber
                  :model-value="control(sec.name, item).value"
                  :min="control(sec.name, item).min"
                  :max="control(sec.name, item).max"
                  :step="control(sec.name, item).step"
                  :precision="control(sec.name, item).decimals"
                  :disabled="editingDisabled" :controls="false" size="small"
                  :aria-label="control(sec.name, item).label || fmtLabel(item.key)"
                  @change="(val) => onLengthOrNumberChange(sec.name, item, val)"
                />
              </div>

              <!-- string -->
              <el-input
                v-else
                :disabled="editingDisabled"
                :model-value="item.v"
                :aria-label="fmtLabel(item.key)"
                size="small"
                @update:model-value="(val) => onParamChange(item.path, val)"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div v-else class="loading-holder" v-loading="true" element-loading-text="加载参数…"></div>
</template>

<style scoped>
.param-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.actions {
  padding: 10px 12px 4px;
  display: flex;
  gap: 8px;
}
.panel-body {
  flex: 1;
  min-height: 0;
  display: flex;
}
.section-tabs {
  width: 100px;
  border-right: 1px solid #e4e7ed;
  padding: 8px 0;
  flex-shrink: 0;
}
.section-item {
  display: block;
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  font-family: inherit;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  color: #606266;
  border-left: 2px solid transparent;
}
.section-item:hover {
  background: #f5f7fa;
}
.section-item.active {
  color: var(--el-color-primary);
  font-weight: 600;
  border-left-color: var(--el-color-primary);
  background: #f5f7fa;
}
.groups-scroll {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 8px 12px;
}
.param-group {
  margin-bottom: 16px;
}
.group-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 10px;
  text-transform: capitalize;
}
.param-item {
  margin-bottom: 14px;
}
.param-label {
  font-size: 12px;
  color: #78716c;
  margin-bottom: 4px;
}
.param-source { font-size: 11px; color: #929a9f; margin-top: -2px; margin-bottom: 3px; }
.slider-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-right: 4px;
}
.slider-row .el-slider { flex: 1; min-width: 0; }
.slider-row .el-input-number { width: 82px; flex-shrink: 0; }
.loading-holder {
  height: 100%;
}
</style>
