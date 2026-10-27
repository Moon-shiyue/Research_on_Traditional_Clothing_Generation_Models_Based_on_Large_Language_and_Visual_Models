import { paramLabel } from './labels.js'

const centimetres = new Set(['sleeve_cuff_width', 'sleeve_width', 'mamian_width', 'cuff_width',
  'root_width', 'bulge_width', 'collar_height', 'top_curve', 'collar_depth', 'overlap_amount',
  'border_width', 'front_depth', 'back_depth', 'front_width', 'neck_depth', 'placket_width',
  'elbow_width', 'tassel_length', 'hem_expand', 'neck_depth_front', 'collar_width', 'overlap','cuff_band_height','side_slit','strip_length','strip_width','panel_height','tie_length','tie_width','front_extension'])

// Native ratios remain in the wire schema; physical UI edits send unit=cm.
export function parameterControl(section, item, body) {
  const isLength = item.key === 'length' || item.key === 'sleeve_length' || item.key === 'petal_length'
  const legBased = item.key === 'length' && (['beizi', 'banbi', 'bijia', 'mamian-skirt', 'ruqun-skirt'].includes(section) || /-(robe|upper)$/.test(section))
  const reference = isLength ? Number(body?.[item.key === 'petal_length' ? 'shoulder_w' : legBased ? '_leg_length' : 'arm_length']) : 1
  const factor = Number.isFinite(reference) && reference > 0 ? reference : 1
  const physical = isLength && factor !== 1
  const inCm = physical || centimetres.has(item.key)
  const label = physical ? (item.key === 'petal_length' ? '云头大小基准（cm）' : item.key === 'sleeve_length' || section.endsWith('sleeve') ? '袖长（cm）'
    : ['mamian-skirt', 'ruqun-skirt'].includes(section) ? '裙长（cm）' : '衣长（cm）')
    : item.key === 'sleeve_width' && section === 'banbi' ? '袖口平铺半围（cm）'
    : item.key === 'sleeve_cuff_width' ? '袖口整围（cm）'
    : item.key === 'collar_width' ? (section.startsWith('stand-') ? '立领成品高（cm）' : '领襟成品宽（cm）')
    : inCm ? `${paramLabel(item.key)}（cm）`
    : ['cross_angle', 'collar_flare'].includes(item.key) ? `${paramLabel(item.key)}（°）` : null
  const decimals = item.type === 'int' ? 0 : (inCm ? 1 : 3)
  return {
    factor, label, decimals,
    value: Number((Number(item.v) * factor).toFixed(physical ? 1 : 8)),
    min: physical ? Math.ceil((item.range[0] * factor - 1e-8) * 10) / 10 : Number(item.range[0]),
    max: physical ? Math.floor((item.range[1] * factor + 1e-8) * 10) / 10 : Number(item.range[1]),
    step: item.type === 'int' ? 1 : physical ? .5 : inCm ? .1 : .025,
  }
}

export function wireValue(value, control) {
  return Number((Number(value) / control.factor).toFixed(8))
}
