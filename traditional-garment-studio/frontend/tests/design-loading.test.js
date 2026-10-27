import test from 'node:test'
import assert from 'node:assert/strict'
import { loadDesignState, applyDesignResult } from '../src/stores/designLoading.js'

const snapshot = id => ({
  design: { params: { name: id } }, body: { params: { waist: id } }, pattern: { svg_url: id },
})
const state = () => ({ designParams: null, bodyParams: null, pattern: null, loaded: false, loadError: '', loadRevision: 0 })
function pending() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function delayedApi() {
  const next = pending()
  return { next, api: {
    getDesignParams: () => next.promise.then(r => r.design),
    getBodyParams: () => next.promise.then(r => r.body),
    getPattern: () => next.promise.then(r => r.pattern),
  } }
}
function generated(store, id) {
  const row = snapshot(id)
  applyDesignResult(store, { status: 'generated', design_params: row.design.params,
    body_params: row.body, pattern: row.pattern, design_list: [id] })
}

test('an older page load cannot replace a newer generated paper or restored body', async () => {
  const store = state(), h = delayedApi()
  const loading = loadDesignState(store, h.api)
  generated(store, 'new')
  h.next.resolve(snapshot('old'))
  await loading
  assert.equal(store.pattern.svg_url, 'new')
  assert.equal(store.bodyParams.params.waist, 'new')
  assert.equal(store.designParams.params.name, 'new')
  assert.equal(store.loaded, true)
})

test('a late old load failure does not show a connection warning after a successful generation', async () => {
  const store = state(), h = delayedApi()
  const loading = loadDesignState(store, h.api)
  generated(store, 'new')
  h.next.reject(new Error('old connection failed'))
  await loading
  assert.equal(store.loadError, '')
  assert.equal(store.pattern.svg_url, 'new')
})

test('two refreshes keep the newer completed snapshot even if the older request arrives last', async () => {
  const store = state(), a = delayedApi(), b = delayedApi()
  const old = loadDesignState(store, a.api)
  const fresh = loadDesignState(store, b.api)
  b.next.resolve(snapshot('new')); await fresh
  a.next.resolve(snapshot('old')); await old
  assert.equal(store.pattern.svg_url, 'new')
  assert.equal(store.bodyParams.params.waist, 'new')
})

test('a clarification without a new complete design does not discard initial parameter loading', async () => {
  const store = state(), h = delayedApi()
  const loading = loadDesignState(store, h.api)
  applyDesignResult(store, { status: 'needs_input', pattern: null })
  h.next.resolve(snapshot('saved')); await loading
  assert.equal(store.pattern.svg_url, 'saved')
  assert.equal(store.loaded, true)
})

test('a current refresh error keeps the visible paper and exposes its actual warning', async () => {
  const store = state(), h = delayedApi()
  generated(store, 'saved')
  const loading = loadDesignState(store, h.api)
  h.next.reject(new Error('current connection failed')); await loading
  assert.equal(store.pattern.svg_url, 'saved')
  assert.equal(store.loadError, 'current connection failed')
})
