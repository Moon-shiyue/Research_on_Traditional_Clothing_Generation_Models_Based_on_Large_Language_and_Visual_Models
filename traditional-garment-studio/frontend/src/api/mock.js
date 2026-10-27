/**
 * Mock API 实现 —— 严格对齐 docs/api.md 契约（草案 v0.1）
 *
 * 模拟行为：
 * - POST /parse 的异步任务模式：阶段化进度推送（queued→parsing→projecting→pattern→rendering）
 * - WS 消息流：progress / message / result / error 四种 type
 * - 同一 Session 同时只允许一个任务（返回 task_conflict）
 * - PUT /design/params 同步返回新 SVG（快/慢参数不同延迟）
 * - 文本包含 "error" 时模拟 mmua_error 失败路径（联调错误处理用）
 */

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// 模块级任务状态（模拟后端 Session 单任务约束）
let runningTask = null

// ---------- mock 数据 ----------

const defaultDesignParams = () => ({
  body_id: 'mean_all',
  is_sectioned: true,
  params: {
    meta: {
      name: { v: 'test_tee', type: 'string', range: null },
      panel_class: { v: 'Tshirt', type: 'select', range: ['Tshirt', 'FittedShirt'] },
    },
    left: {
      collar: {
        collar_type: { v: 'Flat', type: 'select', range: ['Flat', 'Stand', 'Regular'] },
        collar_depth: { v: 0.14, type: 'float', range: [0.0, 0.5] },
        collar_angle: { v: 0.0, type: 'float', range: [0.0, 1.0] },
        collar_cut: { v: 0.0, type: 'float', range: [0.0, 1.0] },
      },
      sleeve: {
        sleeve_class: { v: 'Sleeve', type: 'select', range: ['Sleeve', 'SleeveCuff', 'PuffSleeve', 'no_sleeve'] },
        length: { v: 0.24, type: 'float', range: [0.0, 1.0] },
      },
      silhouette: {
        length: { v: 0.55, type: 'float', range: [0.35, 1.0] },
        width: { v: 0.23, type: 'float', range: [0.15, 0.45] },
        flare: { v: 0.15, type: 'float', range: [0.0, 0.6] },
      },
      neckline: {
        cutout: { v: 'No', type: 'select-null', range: ['No', 'V-cut', 'Square', 'Racer'] },
        depth: { v: 0.0, type: 'float', range: [0.0, 1.0] },
        width: { v: 0.0, type: 'float', range: [0.0, 1.0] },
      },
      finish: {
        finishing: { v: 'Clean', type: 'select', range: ['Raw', 'Clean', 'Famous'] },
        facings: { v: false, type: 'bool' },
        interlining: { v: true, type: 'bool' },
        binding: { v: false, type: 'bool' },
        topstitch: { v: true, type: 'bool' },
      },
    },
    other: {
      front_open: { v: 'No', type: 'select', range: ['No', 'Jacket', 'Zipper', 'Buttons'] },
      front_open_len: { v: 0.0, type: 'float', range: [0.0, 1.0] },
      front_open_style: {
        v: 'Overlapped',
        type: 'select',
        range: ['Overlapped', 'Overlapped-1', 'Overlapped-2', 'Single-1', 'Single-2'],
      },
    },
  },
})

const defaultBodyParams = () => ({
  body_id: 'mean_all',
  available_bodies: ['mean_all', 'nana'],
  params: {
    height: 171.99,
    chest_circ: 100.0,
    waist_circ: 88.0,
    hip_circ: 108.0,
    _bust_circ: 96.0, // 下划线前缀 = 派生只读参数
    _neck_circ: 40.0,
  },
})

let designState = defaultDesignParams()
let bodyState = defaultBodyParams()
let patternState = {
  svg_url: null,
  body_outline_url: '/mock/ggg_outline_mean_all.svg',
  panel_count: 0,
  stitch_count: 0,
  is_self_intersecting: false,
  updated_at: null,
}
let designList = []

// ---------- 工具 ----------

// mode: auto 的路由规则（与 gui/gui_pattern.py 行为一致）
function resolveMode({ text = '', image = null, mode = 'auto' }) {
  if (mode !== 'auto') return mode
  const t = text.trim()
  if (t.startsWith('modify:') || t.startsWith('m:')) return 'modify'
  if ((t.startsWith('stress:') || t.startsWith('s:')) && image) return 'stress'
  if (image && t) return 'picture_text'
  if (image) return 'picture'
  return 'text'
}

// 依据输入内容生成 mock 语义结果（简单启发式，够 demo 用）
function mockSemantics({ text = '', image, mode }) {
  const t = text
  const isMamian = t.includes('马面') || (image && mode.startsWith('picture'))
  const isSkirt = t.includes('裙')
  if (isMamian) {
    return {
      reply: '好的，已生成版型：明制交领长衫 + 马面裙（六褶顺裥），可直接在右侧查看裁片。',
      design_list: ['collar__jiaoling', 'sleeve__pipa', 'lower__mamianqun', 'pleats__6'],
      traditional: {
        dynasty: 'ming',
        upper: { type: 'changshan', collar: 'jiaoling', sleeve: 'pipa' },
        lower: { type: 'mamianqun', pleats: 6, pleat_style: 'shunzhe' },
        confidence: { upper: 0.9, lower: 0.85 },
      },
      rag_sources: [
        { title: '马面裙形制', snippet: '马面裙前后共四个裙门，两两重合，外侧裙门平整无褶，两侧打活褶，常见四到十对。', score: 0.717 },
        { title: '交领右衽', snippet: '交领指衣领左右交叉，右衽指衣襟向右掩，即左襟压右襟，是汉服最典型的领型。', score: 0.682 },
      ],
      svg: '/mock/pattern.svg',
      panels: 12,
      stitches: 24,
    }
  }
  if (isSkirt) {
    return {
      reply: '好的，已生成版型：圆领上衣 + 及膝圆裙，可在右侧查看裁片并调整参数。',
      design_list: ['collar__round', 'upper__tshirt', 'lower__skirt_circle'],
      traditional: null,
      svg: '/mock/pattern_alt.svg',
      panels: 6,
      stitches: 12,
    }
  }
  return {
    reply: '好的，已生成版型：宽松圆领 T 恤（短袖），可在右侧查看裁片并调整参数。',
    design_list: ['collar__flat', 'upper__tshirt', 'sleeve__short'],
    traditional: null,
    svg: '/mock/pattern.svg',
    panels: 8,
    stitches: 16,
  }
}

// 按路径数组取/设嵌套参数（path: ['left','sleeve','length']）
function getByPath(obj, path) {
  return path.reduce((o, k) => (o == null ? undefined : o[k]), obj)
}
function setByPath(obj, path, value) {
  const last = path[path.length - 1]
  const parent = path.slice(0, -1).reduce((o, k) => o[k], obj)
  parent[last] = value
}

// ---------- API 实现 ----------

export function createMockApi() {
  return {
    mode: 'mock',

    // POST /upload/image
    async uploadImage(file) {
      await delay(400)
      return { image_url: URL.createObjectURL(file) }
    },

    // POST /parse + WS /ws/{task_id}
    // handlers: { onProgress({stage,progress}), onMessage({role,content,image}), onResult(data), onError({code,message}) }
    async parse({ mode = 'auto', text = '', image = null }, handlers = {}) {
      if (runningTask) {
        throw Object.assign(new Error('已有任务运行中'), { code: 'task_conflict' })
      }
      const resolved = resolveMode({ text, image, mode })
      const taskId = 'task_' + Math.random().toString(36).slice(2, 9)
      runningTask = { taskId, stage: 'queued', progress: 0 }
      // 异步推进，不阻塞返回 taskId
      runTask({ taskId, mode: resolved, text, image, handlers })
      return { task_id: taskId, mode: resolved }
    },

    // GET /tasks/{task_id}（轮询降级；mock 下由前端事件流替代，这里给个查询能力）
    async getTask(taskId) {
      if (!runningTask || runningTask.taskId !== taskId) {
        return { task_id: taskId, status: 'done', stage: 'rendering', progress: 100, result: null }
      }
      return {
        task_id: taskId,
        status: 'running',
        stage: runningTask.stage,
        progress: runningTask.progress,
        result: null,
      }
    },

    // GET /design/params
    async getDesignParams() {
      await delay(200)
      return JSON.parse(JSON.stringify(designState))
    },

    // PUT /design/params
    async updateDesignParam(path, value) {
      // 模拟快/慢参数：flare/length/silhouette 组视为慢参数
      const slow = path.includes('silhouette') || path.includes('flare')
      await delay(slow ? 1500 : 300)
      setByPath(designState.params, path, { ...getByPath(designState.params, path), v: value })
      patternState.svg_url = patternState.svg_url // 不变
      patternState.updated_at = new Date().toISOString()
      return {
        svg_url: patternState.svg_url,
        svg_updated: true,
      }
    },

    // POST /design/random
    async randomDesign() {
      await delay(800)
      const walk = (node) => {
        for (const k of Object.keys(node)) {
          const p = node[k]
          if (p && typeof p === 'object' && 'v' in p) {
            if (p.type === 'float') p.v = +(p.range[0] + Math.random() * (p.range[1] - p.range[0])).toFixed(3)
            else if (p.type === 'bool') p.v = Math.random() > 0.5
          } else if (p && typeof p === 'object') {
            walk(p)
          }
        }
      }
      walk(designState.params)
      patternState.updated_at = new Date().toISOString()
      return JSON.parse(JSON.stringify(designState))
    },

    // POST /design/default
    async defaultDesign() {
      await delay(400)
      designState = defaultDesignParams()
      return JSON.parse(JSON.stringify(designState))
    },

    // GET /body/params
    async getBodyParams() {
      await delay(150)
      return JSON.parse(JSON.stringify(bodyState))
    },

    // PUT /body/params
    async updateBodyParam(path, value) {
      await delay(500)
      setByPath(bodyState.params, path, value)
      patternState.updated_at = new Date().toISOString()
      return { svg_url: patternState.svg_url, svg_updated: true }
    },

    // GET /pattern
    async getPattern() {
      await delay(100)
      return JSON.parse(JSON.stringify(patternState))
    },

    // GET /download —— mock：下载当前设计快照 JSON
    async download() {
      await delay(300)
      const snapshot = {
        time: new Date().toISOString(),
        design_list: designList,
        design_params: designState.params,
        body_params: bodyState.params,
      }
      const blob = new Blob([JSON.stringify(snapshot, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `Configured_design_${new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')}.json`
      a.click()
      URL.revokeObjectURL(url)
    },

    // GET /vocab（P2 占位，mock 提前实现：快捷标签）
    async getVocab() {
      await delay(100)
      return {
        dynasty: ['ming', 'song', 'tang'],
        quick_tags: ['明制', '马面裙', '交领', '立领', '琵琶袖', '褙子', '宋制', '齐胸襦裙'],
      }
    },
  }
}

// ---------- 任务推进（模拟 WS 消息流） ----------

async function runTask({ taskId, mode, text, image, handlers }) {
  const fail = !!text.includes('error')
  const emit = (fn, payload) => fn && fn(payload)

  try {
    // 阶段推进：queued → parsing → projecting → pattern → rendering
    const stages = [
      { stage: 'queued', progress: 5, delay: 300 },
      { stage: 'parsing', progress: 30, delay: 1600 },
      { stage: 'projecting', progress: 65, delay: 2000 },
      { stage: 'pattern', progress: 85, delay: 1000 },
      { stage: 'rendering', progress: 95, delay: 600 },
    ]

    for (const s of stages) {
      await delay(s.delay)
      if (fail && s.stage === 'parsing') break // 模拟云端解析失败
      runningTask = { taskId, ...s }
      emit(handlers.onProgress, { stage: s.stage, progress: s.progress })
      // parsing 阶段附带一条中间消息（模拟 MMUA 的过程性回复）
      if (s.stage === 'parsing') {
        emit(handlers.onMessage, {
          role: 'assistant',
          content: '正在解析设计意图，识别服装部件与形制特征…',
          image: null,
        })
      }
    }

    if (fail) {
      runningTask = null
      emit(handlers.onError, { code: 'mmua_error', message: '生成失败，请更换提示词或图片重试。' })
      return
    }

    const sem = mockSemantics({ text, image, mode })
    // 更新 mock 后端状态
    designList = sem.design_list
    patternState = {
      ...patternState,
      svg_url: sem.svg,
      panel_count: sem.panels,
      stitch_count: sem.stitches,
      is_self_intersecting: false,
      updated_at: new Date().toISOString(),
    }

    const result = {
      task_id: taskId,
      mode,
      reply: sem.reply,
      design_list: sem.design_list,
      traditional: sem.traditional,
      rag_sources: sem.rag_sources ?? null, // 语料命中时返回溯源，否则 null
      design_params: JSON.parse(JSON.stringify(designState.params)),
      pattern: JSON.parse(JSON.stringify(patternState)),
    }
    runningTask = null
    emit(handlers.onResult, result)
  } catch (e) {
    runningTask = null
    emit(handlers.onError, { code: 'pattern_error', message: String(e) })
  }
}
