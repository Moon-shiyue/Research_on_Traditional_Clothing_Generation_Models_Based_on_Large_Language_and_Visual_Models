<script setup>
import { computed, ref, watch } from 'vue'
import { useDesignStore } from '../stores/design'
import { useChatStore } from '../stores/chat'
import { paramLabel, SECTION_LABELS } from '../utils/labels'
import { api } from '../api'

const design = useDesignStore()
const chat = useChatStore()
const showDimensions = ref(true)
const zoom = ref(1)
const fitWidth = ref(false)
const maxZoom = computed(() => fitWidth.value ? 6 : 3)
const printOpen = ref(false)
const printPlan = ref(null)
const printLoading = ref(false)
const printError = ref('')
const referenceOpen = ref(false)
const historyOpen = ref(false)
const historyItems = ref([])
const historyLoading = ref(false)
const historyError = ref('')
const emptyHint = computed(() => !design.loaded
  ? (design.loadError ? '连接制版服务后，可刷新状态读取纸样' : '正在读取制版状态…')
  : ({
  awaiting_confirmation: '识别完成，请在左侧确认制作纸样',
  needs_input: '本次尚未生成纸样，请补充说明或更换图片',
  error: '本次处理未完成，可在左侧重试',
}[chat.lastOutcome] || '输入描述或上传图片，开始生成纸样'))
const garmentLabel = computed(() => {
  const p = design.pattern
  if (p?.garments?.length) return p.garments.map(g => g.name).join('＋')
  return { 'ruqun-skirt':'襦裙下裳', 'cross-collar':'交领片', 'duijin-collar':'对襟领片',
    'round-collar':'圆领片', 'stand-collar':'立领片', 'wide-sleeve':'广袖片',
    'narrow-sleeve':'窄袖片', 'pipa-sleeve':'琵琶袖片' }[p?.component] || SECTION_LABELS[p?.component] || ''
})
const outcomeNotice = computed(() => {
  if (!design.pattern?.svg_url || chat.task.running || design.patternUpdating) return ''
  return {
    awaiting_confirmation: '图片建议待确认；右侧仍显示此前保留的纸样。',
    needs_input: '本次输入尚未生成新纸样；右侧保留已有结果。',
    error: '本次处理未确认成功；请核对右侧保留的纸样，或重试本次输入。',
  }[chat.lastOutcome] || design.pattern?.recovery_notice || ''
})
watch(() => design.pattern?.svg_url, () => {
  zoom.value = 1; printOpen.value = false; printPlan.value = null
  fitWidth.value = false
  referenceOpen.value = false; historyOpen.value = false
})
const patternUrl = computed(() => {
  const p = design.pattern
  if (!p) return null
  return showDimensions.value ? (p.body_layout_dimension_svg_url || p.preview_dimension_svg_url || p.dimension_svg_url || p.svg_url)
    : (p.body_layout_svg_url || p.preview_svg_url || p.svg_url)
})
const resources = computed(() => [
  ['详细制版图', design.pattern?.cutting_svg_url],
  ['款式示意', design.pattern?.style_svg_url],
  ['折褶说明', design.pattern?.pleat_detail_svg_url],
  ...(design.pattern?.garments || []).flatMap(g => [
    [g.name + '净样', g.dimension_svg_url], [g.name + '制版图', g.cutting_svg_url],
  ]),
].filter(item => item[1]))
function changeZoom(delta) { zoom.value = Math.min(maxZoom.value, Math.max(1, Math.round((zoom.value + delta) * 10) / 10)) }
function toggleWidth() { fitWidth.value = !fitWidth.value; zoom.value = 1 }
async function loadHistory() {
  historyLoading.value = true
  historyError.value = ''
  try { historyItems.value = (await api.getDesignHistory()).items || [] }
  catch (error) { historyError.value = error.message || '最近纸样暂时无法读取。' }
  finally { historyLoading.value = false }
}
watch(historyOpen, open => { if (open) loadHistory() })
async function restoreVersion(item) {
  if (item.current || chat.task.running || design.patternUpdating) return
  if (await design.restoreDesign(item.design_id)) {
    chat.onDesignRestored()
    historyOpen.value = false
  }
}
async function previewPrint() {
  printOpen.value = true
  printPlan.value = null
  printError.value = ''
  printLoading.value = true
  const url = design.pattern?.svg_url
  try {
    if (!api.getPrintPlan) throw new Error('A4打印需连接制版服务。')
    const plan = await api.getPrintPlan()
    if (url === design.pattern?.svg_url) printPlan.value = plan
  } catch (error) { printError.value = error.message || '打印预览未完成。' }
  finally { printLoading.value = false }
}
async function downloadPrint() {
  printError.value = ''
  printLoading.value = true
  try { await api.downloadPrint(printPlan.value.pattern_url) }
  catch (error) { printError.value = error.message || 'PDF下载未完成，请重试。' }
  finally { printLoading.value = false }
}
</script>

<template>
  <div class="pattern-view">
    <div v-if="outcomeNotice" class="outcome-notice" role="status">{{ outcomeNotice }}</div>
    <div class="toolbar">
      <el-switch v-model="showDimensions" :disabled="!patternUrl" active-text="尺寸（cm）" size="small" aria-label="显示裁片尺寸" />
      <span v-if="patternUrl" class="meta">{{ design.pattern.panel_count }} 裁片</span>
      <span v-if="garmentLabel" class="meta">{{ garmentLabel }}</span>
      <span v-if="design.pattern?.component === 'cloud-shoulder' && design.pattern?.assembly" class="meta">{{ design.pattern.assembly.layers }}层 · {{ design.pattern.assembly.petal_count }}云头</span>
      <el-tag v-if="design.pattern?.is_self_intersecting" type="danger" size="small">裁片自交</el-tag>
      <div v-if="patternUrl" class="zoom-tools">
        <el-button text size="small" :aria-label="fitWidth ? '查看整张纸样' : '按宽度查看纸样'" :aria-pressed="fitWidth" title="整套图过小时，按宽度显示并向下滚动查看全部裁片" @click="toggleWidth">{{ fitWidth ? '查看整图' : '适合宽度' }}</el-button>
        <el-button text size="small" aria-label="缩小纸样" :disabled="zoom <= 1" @click="changeZoom(-.3)">−</el-button>
        <el-button text size="small" title="适应画布" @click="zoom = 1">{{ Math.round(zoom * 100) }}%</el-button>
        <el-button text size="small" aria-label="放大纸样" :disabled="zoom >= maxZoom" @click="changeZoom(.3)">＋</el-button>
      </div>
    </div>
    <p v-if="fitWidth" class="scroll-hint">按相同比例显示，可向下及横向滚动查看全部裁片。</p>
    <div class="canvas-wrap">
      <div class="paper" :class="{ 'body-layout': design.pattern?.body_layout_svg_url, 'fit-width': fitWidth }" :style="{ width: `${zoom * 100}%`, height: fitWidth ? 'auto' : `${zoom * 100}%` }">
        <img v-if="patternUrl" :src="patternUrl" class="pattern-svg" :alt="design.pattern?.body_layout_svg_url ? '左侧人体定位，右侧无人体裁片平铺' : '裁片版型'" />
        <div v-if="design.patternUpdating || chat.task.running" class="updating-mask"><el-icon class="rotating" :size="24"><Loading /></el-icon><span>{{ chat.task.running ? chat.stageLabel + '…' : patternUrl ? '更新版型中…' : '保存人体尺寸…' }}</span></div>
        <div v-if="!patternUrl && !design.patternUpdating && !chat.task.running" class="empty-pattern">{{ emptyHint }}</div>
      </div>
    </div>
    <details v-if="design.pattern?.panel_measurements?.length" class="piece-measurements">
      <summary>裁片尺寸清单（cm）</summary>
      <p>净样平铺宽 × 高，不等于成衣围度；裁剪前按工艺另核缝份。</p>
      <table>
        <caption class="sr-only">当前裁片的净样外接尺寸，单位厘米</caption>
        <thead><tr><th scope="col">裁片</th><th scope="col">净宽</th><th scope="col">净高</th></tr></thead>
        <tbody><tr v-for="piece in design.pattern.panel_measurements" :key="piece.panel_id">
          <th scope="row">{{ piece.garment_name ? piece.garment_name + ' · ' : '' }}{{ piece.label }}</th>
          <td>{{ Number(piece.width_cm).toFixed(1) }}</td><td>{{ Number(piece.height_cm).toFixed(1) }}</td>
        </tr></tbody>
      </table>
    </details>
    <details v-if="patternUrl" class="pattern-notes">
      <summary>尺寸与说明</summary>
      <p v-if="design.bodyParams?.params">身高 {{ Number(design.bodyParams.params.height).toFixed(1) }} cm，腰围 {{ Number(design.bodyParams.params.waist).toFixed(1) }} cm；可在人体尺寸中调整。</p>
      <p v-if="design.pattern?.default_fields?.length">默认参数：{{ design.pattern.default_fields.map(key => paramLabel(key.split('.').pop())).join('、') }}。</p>
      <p v-if="design.pattern?.construction">裙长 {{ design.pattern.construction.skirt_length.toFixed(1) }} cm，每幅 {{ design.pattern.construction.pleat_count_each }} 个褶。当前仅生成裙装组件。</p>
      <p v-if="design.pattern?.assembly">{{ design.pattern.assembly.variant_label }}；轮廓与缝边配长已检查。</p>
      <p v-for="g in design.pattern?.garments || []" :key="g.id">{{ g.name }}：{{ g.panel_count }}片；与其它衣物分别缝制。</p>
      <p v-if="design.pattern?.body_layout">{{ design.pattern.body_layout.scope }}</p>
      <p>默认预览为净样，不含缝份。{{ (design.pattern?.warnings || []).join('；') }}</p>
    </details>
    <div class="bottombar">
      <el-popover v-if="api.getDesignHistory" v-model:visible="historyOpen" placement="top" :width="310" trigger="click">
        <p v-if="historyLoading" role="status">正在读取最近纸样…</p>
        <p v-else-if="historyError" role="alert">{{ historyError }}</p>
        <p v-else-if="!historyItems.length">还没有可恢复的完整纸样。</p>
        <div v-else class="history-list">
          <p>最近10份完整结果；恢复时一并还原款式和人体尺寸。</p>
          <el-button v-for="item in historyItems" :key="item.design_id" text class="history-item"
            :disabled="item.current || design.patternUpdating || chat.task.running" @click="restoreVersion(item)">
            <span>{{ item.name }} · {{ item.panel_count }}片{{ item.current ? '（当前）' : '' }}<small v-if="item.summary" class="history-summary">{{ item.summary }}</small><small>{{ String(item.updated_at).replace('T',' ') }}{{ item.has_reference_image ? ' · 有参考图' : '' }}</small></span>
          </el-button>
        </div>
        <template #reference><el-button text size="small" :disabled="design.patternUpdating || chat.task.running">最近纸样</el-button></template>
      </el-popover>
      <el-button v-if="design.pattern?.reference_image_url" text size="small" @click="referenceOpen = true">本次参考图</el-button>
      <el-popover v-if="resources.length" placement="top" :width="180" trigger="click">
        <div class="resource-links"><a v-for="[label, url] in resources" :key="url" :href="url" target="_blank" rel="noopener">{{ label }}</a></div>
        <template #reference><el-button text size="small">更多</el-button></template>
      </el-popover>
      <a v-if="patternUrl" :href="patternUrl" target="_blank" rel="noopener" class="open-pattern">打开原图</a>
      <el-button size="small" :disabled="!patternUrl || design.patternUpdating || chat.task.running || printLoading" @click="previewPrint">A4纸样</el-button>
      <el-button type="primary" size="small" :disabled="!patternUrl || design.patternUpdating || chat.task.running" @click="design.download()"><el-icon><Download /></el-icon>&nbsp;下载</el-button>
    </div>
    <el-dialog v-model="referenceOpen" title="当前纸样的参考图" width="min(620px, calc(100vw - 24px))" top="5vh" class="reference-dialog">
      <img v-if="referenceOpen && design.pattern?.reference_image_url" :src="design.pattern.reference_image_url" class="reference-image" alt="生成当前纸样时确认的参考服饰图片" />
      <p>此图用于样式参考。尺寸以当前人体与设计参数为准；后续编辑不会重新识图。</p>
    </el-dialog>
    <el-dialog v-model="printOpen" title="A4 分幅打印" width="min(580px, calc(100vw - 24px))" top="5vh" class="print-dialog" :close-on-click-modal="false" :close-on-press-escape="!printLoading" :show-close="!printLoading">
      <p v-if="printLoading" role="status">{{ printPlan ? '正在生成PDF，请稍候…' : '正在计算纸张数量…' }}</p>
      <p v-if="printError" role="alert" class="print-error">{{ printError }}</p>
      <template v-if="printPlan">
        <p><strong>共 {{ printPlan.page_count }} 张 A4</strong>（含1张校准页）；{{ printPlan.fabric_panel_count }}片裁布，{{ printPlan.paper_template_count }}套纸样。</p>
        <p v-for="note in printPlan.notes" :key="note">{{ note }}</p>
        <div class="print-pieces"><table>
          <thead><tr><th>裁片</th><th>裁布</th><th>行×列</th><th>PDF页码</th></tr></thead>
          <tbody><tr v-for="piece in printPlan.panels" :key="piece.panel_id"><td>{{ piece.label }}</td><td>{{ piece.cut_count }}片</td><td>{{ piece.rows }}×{{ piece.columns }}</td><td>{{ piece.first_page }}–{{ piece.last_page }}</td></tr></tbody>
        </table></div>
      </template>
      <template #footer><el-button :disabled="printLoading" @click="printOpen = false">关闭</el-button><el-button type="primary" :disabled="!printPlan || printLoading || design.patternUpdating || chat.task.running" :loading="printLoading && !!printPlan" @click="downloadPrint">下载PDF</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.pattern-view { height: 100%; display: flex; flex-direction: column; padding: 8px 12px 10px; }
.outcome-notice { color: #8a5a00; background: #fff7e6; border: 1px solid #f2ddb0; border-radius: 4px; padding: 7px 10px; margin-bottom: 6px; font-size: 12px; line-height: 1.5; }
.toolbar { display: flex; align-items: center; gap: 12px; min-height: 30px; padding-bottom: 6px; }
.meta { color: #909399; font-size: 12px; }
.zoom-tools { display: flex; align-items: center; margin-left: auto; }
.zoom-tools .el-button + .el-button { margin-left: 0; }
.canvas-wrap { flex: 1; min-height: 0; overflow: auto; border-radius: 3px; border: 1px solid #e4e7eb; }
.paper { position: relative; min-width: 100%; min-height: 100%; background-color: #fff; background-image: linear-gradient(#ebedf0 1px, transparent 1px), linear-gradient(90deg, #ebedf0 1px, transparent 1px); background-size: 16px 16px; overflow: hidden; }
.pattern-svg { position: absolute; inset: 20px; width: calc(100% - 40px); height: calc(100% - 40px); object-fit: contain; }
.paper.body-layout { min-width: 100%; }
.paper.fit-width .pattern-svg { position: relative; inset: auto; display: block; width: calc(100% - 40px); height: auto; margin: 20px; object-fit: initial; }
.scroll-hint { margin: 0 0 5px; color: #77818d; font-size: 12px; }
.pattern-notes { font-size: 12px; color: #77818d; line-height: 1.6; padding-top: 7px; max-height: 130px; overflow: auto; }
.pattern-notes summary { cursor: pointer; }
.pattern-notes p { margin: 5px 0; }
.piece-measurements { font-size: 12px; color: #536072; padding-top: 7px; max-height: 210px; overflow: auto; }
.piece-measurements summary { cursor: pointer; }
.piece-measurements p { margin: 6px 0; }
.piece-measurements table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
.piece-measurements th, .piece-measurements td { border-bottom: 1px solid #e5e8ed; padding: 4px 7px; text-align: right; }
.piece-measurements th:first-child { text-align: left; font-weight: 400; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
.bottombar { display: flex; align-items: center; justify-content: flex-end; gap: 12px; padding-top: 8px; }
.open-pattern, .resource-links a { font-size: 12px; color: var(--el-color-primary); }
.resource-links { display: flex; flex-direction: column; gap: 12px; padding: 6px; }
.updating-mask, .empty-pattern { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 8px; color: #909399; }
.updating-mask { background: rgba(255,255,255,.72); z-index: 2; }
.rotating { animation: rotate 1.2s linear infinite; }
.print-pieces { max-height: 260px; overflow: auto; }
.print-pieces table { width: 100%; border-collapse: collapse; font-size: 12px; }
.print-pieces th, .print-pieces td { padding: 7px; border-bottom: 1px solid #e5e8ed; text-align: left; }
.print-error { color: var(--el-color-danger); }
.reference-image { display: block; max-width: 100%; max-height: 65vh; margin: auto; object-fit: contain; }
.reference-dialog p { color: #77818d; font-size: 12px; line-height: 1.6; }
.history-list { max-height: 320px; overflow: auto; }
.history-list p { margin: 0 0 7px; font-size: 12px; color: #77818d; line-height: 1.5; }
.history-item { display: flex; width: 100%; height: auto; min-height: 42px; justify-content: flex-start; text-align: left; margin: 0 !important; }
.history-item small { display: block; margin-top: 4px; font-size: 11px; color: #929a9f; }
.history-item .history-summary { white-space: normal; line-height: 1.4; color: #65758a; }
.toolbar, .bottombar { flex-wrap: wrap; }
@keyframes rotate { to { transform: rotate(360deg); } }
@media (max-width: 800px) { .canvas-wrap { min-height: 320px; } .pattern-view { padding: 8px; } }
</style>
