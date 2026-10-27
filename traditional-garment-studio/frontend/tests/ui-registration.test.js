import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { createApp } from 'vue'
import { registerUI } from '../src/ui.js'

test('all Element Plus tags used by real templates resolve, including no-op child plugins', () => {
  const app = createApp({})
  registerUI(app)
  const folder = fileURLToPath(new URL('../src/components/', import.meta.url))
  const sources = [readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8'),
    ...readdirSync(folder).filter(n => n.endsWith('.vue')).map(n => readFileSync(folder + n, 'utf8'))]
  const tags = new Set(sources.flatMap(source => [...source.matchAll(/<(el-[a-z-]+)\b/g)].map(m => m[1])))
  for (const tag of tags) {
    const name = tag.split('-').map(s => s[0].toUpperCase() + s.slice(1)).join('')
    assert.ok(app.component(name), `${tag} must resolve to a registered Vue component`)
  }
  assert.ok(app.directive('loading'))
  assert.equal(app.component('ElRadioGroup').name, 'ElRadioGroup')
  assert.equal(app.component('ElRadioButton').name, 'ElRadioButton')
})
