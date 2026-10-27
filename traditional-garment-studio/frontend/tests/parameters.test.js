import test from 'node:test'
import assert from 'node:assert/strict'
import { parameterControl, wireValue } from '../src/utils/parameters.js'

test('cloud lobe cm uses shoulder width while its front extension stays native cm', () => {
  for (const shoulder of [28,40,42]) {
    const lobe=parameterControl('cloud-shoulder',{key:'petal_length',v:.5,type:'float',range:[.15,.9]},{shoulder_w:shoulder,arm_length:60})
    assert.equal(lobe.factor,shoulder)
    assert.equal(lobe.value,shoulder*.5)
    assert.equal(lobe.label,'云头大小基准（cm）')
    assert.ok(Math.abs(wireValue(14,lobe)*shoulder-14)<1e-6)
    const front=parameterControl('cloud-shoulder',{key:'front_extension',v:10,type:'float',range:[0,20]},{shoulder_w:shoulder})
    assert.equal(front.factor,1);assert.equal(front.value,10)
    assert.equal(front.label,'云肩前摆加长（cm）')
  }
})

test('pibo strip length and width stay native centimetres after body changes', () => {
  for (const body of [{_leg_length:82,arm_length:50},{_leg_length:110,arm_length:65},{}]) {
    for (const [key,value,range] of [['strip_length',300,[150,500]],['strip_width',30,[10,70]]]) {
      const control=parameterControl('pibo',{key,v:value,type:'float',range},body)
      assert.equal(control.factor,1)
      assert.equal(control.value,value)
      assert.equal(wireValue(value,control),value)
      assert.match(control.label,/cm/)
      assert.equal(control.min,range[0]);assert.equal(control.max,range[1])
    }
  }
})

test('skirt and upper-body lengths present cm and send original ratios', () => {
  const item = { key: 'length', v: .95, type: 'float', range: [.2, 1.5] }
  for (const component of ['mamian-skirt', 'ruqun-skirt', 'beizi', 'banbi', 'bijia', 'cross-robe', 'round-robe','stand-robe','cross-upper','round-upper','stand-upper','duijin-upper']) {
    const control = parameterControl(component, item, { _leg_length: 100, arm_length: 60 })
    assert.equal(control.value, 95)
    assert.equal(control.min, 20)
    assert.equal(control.max, 150)
    assert.equal(wireValue(95, control), .95)
    assert.match(control.label, /cm/)
  }
})

test('sleeve length uses arm length, while physical cuff width never scales', () => {
  const body = { _leg_length: 100, arm_length: 60 }
  const cuff = parameterControl('beizi', { key: 'sleeve_cuff_width', v: 60, type: 'float', range: [16, 80] }, body)
  assert.equal(cuff.value, 60)
  assert.equal(wireValue(40, cuff), 40)
  for (const [component, key] of [['beizi', 'sleeve_length'], ['banbi', 'sleeve_length'], ['wide-sleeve', 'length']]) {
    const control = parameterControl(component, { key, v: .9, type: 'float', range: [.7, 1.2] }, body)
    assert.equal(control.value, 54)
    assert.equal(wireValue(48, control), .8)
  }
})

test('changing body dimensions recomputes display without rewriting style', () => {
  const item = { key: 'length', v: .9, type: 'float', range: [.2, 1.5] }
  assert.equal(parameterControl('mamian-skirt', item, { _leg_length: 100 }).value, 90)
  assert.equal(parameterControl('mamian-skirt', item, { _leg_length: 110 }).value, 99)
  assert.equal(item.v, .9)
})

test('integer layer count and unknown body information remain safe wire values', () => {
  const layer = parameterControl('cloud-shoulder', { key: 'layers', v: 3, type: 'int', range: [1, 3] }, {})
  assert.equal(layer.value, 3)
  assert.equal(layer.step, 1)
  assert.equal(wireValue(2, layer), 2)
  const length = parameterControl('beizi', { key: 'length', v: 1, type: 'float', range: [.75, 1.25] }, null)
  assert.equal(length.factor, 1)
  assert.equal(length.value, 1)
  assert.equal(length.label, null)
})

test('rounded cm control endpoints remain within supported native bounds', () => {
  for (const reference of [82.2754, 90.1424, 105.9671]) {
    const item = { key: 'length', v: .95, type: 'float', range: [.2, 1.5] }
    const control = parameterControl('mamian-skirt', item, { _leg_length: reference })
    assert.ok(control.min / reference >= item.range[0])
    assert.ok(control.max / reference <= item.range[1])
    assert.ok(control.max - control.min > 1)
  }
})
