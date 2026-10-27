/**
 * 中英文映射字典 —— 仅 UI 显示层翻译
 * 原则：发送给后端的参数名/枚举值保持原文，只在展示时转中文
 * 未收录的键回退为原文（真实后端上线后未知参数仍可读）
 */

// 分区名 → 中文
export const SECTION_LABELS = {
  'cross-robe':'交领长袍', 'cross-upper':'交领上衣', 'round-robe':'圆领长袍',
  'round-upper':'圆领上衣', 'stand-robe':'立领长衫', 'stand-upper':'立领上衣',
  bijia:'圆领对襟比甲',
  'duijin-upper':'直领对襟上衣',
  pibo:'直幅披帛',
  'chest-wrap':'直幅系带抹胸',
  'mamian-skirt': '马面裙', 'ruqun-skirt': '襦裙', beizi: '褙子', banbi: '半臂',
  'cloud-shoulder': '云肩', 'pipa-sleeve': '琵琶袖', 'wide-sleeve': '广袖', 'narrow-sleeve': '窄袖',
  'cross-collar': '交领', 'round-collar': '圆领', 'duijin-collar': '对襟', 'stand-collar': '立领',
  traditional: '朝代与场合',
  meta: '基本信息',
  left: '衣身',
  other: '其他',
}

// 参数组名 → 中文
export const GROUP_LABELS = {
  collar: '领子',
  sleeve: '袖子',
  silhouette: '廓形',
  neckline: '领口',
  finish: '缝制工艺',
}

// 参数键名 → 中文
export const PARAM_LABELS = {
  petal_length:'云头大小基准', front_extension:'云肩前摆加长',
  panel_height:'抹胸围前净高',front_coverage:'围前覆盖比（布幅÷胸围）',tie_length:'系带净长',tie_width:'系带展开宽',
  strip_length:'披帛净长',strip_width:'披帛净幅宽',
  hem_expand:'下摆单侧放量', chest_ease:'胸围松量比', neck_depth_front:'前领深',
  collar_width:'领宽/立领高', overlap:'搭襟宽',
  sleeve_type:'袖型', belt:'腰带',
  opening_type:'开襟位置',
  cuff_band_height:'袖口条成品宽',
  side_slit:'侧衩垂直高度',
  dynasty: '朝代', occasion: '场合', mamian_width: '马面宽度', pleat_ruffle: '褶量比', rise: '腰位比例',
  sleeve_length: '袖长比例', sleeve_width: '袖口宽度', cuff_width: '袖口宽度', root_width: '袖根宽度',
  bulge_width: '袖身膨起宽度', collar_height: '领高', collar_flare: '领口外倾角', top_curve: '领顶弧起量',
  cross_angle: '交叉角', overlap_amount: '左右襟重叠量', border_width: '领缘宽度', front_depth: '前领深',
  back_depth: '后领深', front_width: '前襟宽', neck_depth: '领深', placket_width: '门襟宽', elbow_width: '肘部宽',
  hem_ratio: '裙摆展宽比', waist_position: '腰位比例', layers: '层数', petal_count: '云头数量',
  tassel_length: '垂须长度', slit_height: '开衩高度比例',
  sleeve_cuff_width: '袖口整围（cm）',
  // meta 段
  name: '名称',
  panel_class: '服装类别',
  // collar 组
  collar_type: '领型',
  collar_depth: '领深',
  collar_angle: '领角',
  collar_cut: '领口剪裁',
  // sleeve 组
  sleeve_class: '袖型',
  length: '长度',
  width: '宽度',
  flare: '喇叭度',
  // silhouette 组
  // neckline 组
  cutout: '领口开衩',
  depth: '深度',
  // finish 组
  finishing: '缝边工艺',
  facings: '贴边',
  interlining: '衬布',
  binding: '滚边',
  topstitch: '明线',
  // other 段
  front_open: '前片开襟',
  front_open_len: '开襟长度',
  front_open_style: '开襟样式',
  // 人体尺寸
  height: '身高',
  waist: '腰围', hips: '臀围', bust: '胸围', underbust: '下胸围',
  arm_length: '臂长', wrist: '腕围', shoulder_w: '肩宽', neck_w: '颈宽',
  hips_line: '腰臀垂直距离', waist_line: '腰线距离', head_l: '头长',
  back_width: '背宽', leg_circ: '腿围', armscye_depth: '袖窿深',
  arm_pose_angle: '手臂姿态角', bum_points: '臀峰间距', bust_line: '胸线距离',
  bust_points: '胸点间距', crotch_hip_diff: '裆臀高度差', hip_back_width: '后臀宽',
  hip_inclination: '臀部倾角', shoulder_incl: '肩斜角', vert_bust_line: '胸线垂距',
  waist_back_width: '后腰宽', waist_over_bust_line: '经胸腰线距离',
  _leg_length: '腿长', _waist_level: '腰线高度', _hip_level: '臀线高度',
  _base_sleeve_balance: '袖根平衡量',
  _bust_line: '综合胸线距离', _hip_inclination: '臀部制版倾角',
  _shoulder_incl: '肩部制版倾角', _armscye_depth: '制版袖窿深',
  chest_circ: '胸围',
  waist_circ: '腰围',
  hip_circ: '臀围',
  _bust_circ: '净胸围',
  _neck_circ: '颈围',
}

// 枚举值 → 中文（仅显示，提交值不变）
export const VALUE_LABELS = {
  Han: '汉代', Tang: '唐代', Song: '宋代', Ming: '明代', Qing: '清代',
  Changfu: '常服', Lifu: '礼服', Bianfu: '便服', mean_female: '标准女性尺寸',
  // panel_class
  Tshirt: 'T恤（宽松）',
  FittedShirt: '合身衬衫',
  // collar_type
  Flat: '平领',
  Stand: '立领',
  Regular: '常规领',
  // sleeve_class
  Sleeve: '基础袖',
  SleeveCuff: '收口袖',
  PuffSleeve: '泡泡袖',
  no_sleeve: '无袖',
  // cutout
  No: '无',
  'V-cut': 'V 领',
  Square: '方领',
  Racer: '背心式',
  // finishing
  Raw: '毛边',
  Clean: '包边',
  Famous: '装饰滚边',
  // front_open
  Jacket: '对襟',
  Zipper: '拉链',
  Buttons: '纽扣',
  // front_open_style
  Overlapped: '重叠式',
  'Overlapped-1': '重叠式 1',
  'Overlapped-2': '重叠式 2',
  'Single-1': '单襟 1',
  'Single-2': '单襟 2',
  // 体型
  mean_all: '标准均码',
  nana: 'nana 体型',
}

export function sectionLabel(name) {
  return SECTION_LABELS[name] || name
}

export function groupLabel(name) {
  return GROUP_LABELS[name] || name.replace(/_/g, ' ')
}

export function paramLabel(key) {
  return PARAM_LABELS[key] || key.replace(/_/g, ' ')
}

export function valueLabel(v) {
  if (v === null || v === undefined || v === '') return '无'
  return VALUE_LABELS[v] || String(v)
}
