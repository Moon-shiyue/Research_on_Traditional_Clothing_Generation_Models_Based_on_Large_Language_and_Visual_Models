import test from 'node:test'
import assert from 'node:assert/strict'
import { pollTask } from '../src/api/taskPolling.js'

function harness(events, handlers = {}) {
  let elapsed = 0, reads = 0
  const results = [], errors = [], progress = []
  const options = {
    readTask: async () => {
      reads++
      const next = events.shift()
      if (next instanceof Error) throw next
      return next || { status: 'running', stage: 'pattern', progress: 75 }
    },
    now: () => elapsed,
    sleep: async ms => { elapsed += ms },
    timeoutMs: 6000,
    wrapError: error => ({ code: error.response?.status === 404 ? 'task_not_found' : 'network_error' }),
    handlers: { onResult: r => results.push(r), onError: e => errors.push(e), onProgress: p => progress.push(p), ...handlers },
  }
  return { options, results, errors, progress, get reads() { return reads } }
}

test('short outages recover and successful polls reset the consecutive failure count', async () => {
  const failed = () => new Error('temporary disconnect')
  const h = harness([failed(), failed(), {status:'running',progress:40}, failed(), failed(), {status:'done',result:{status:'generated'}}])
  h.options.timeoutMs = 20000
  await pollTask(h.options)
  assert.equal(h.reads,6)
  assert.deepEqual(h.results,[{status:'generated'}])
  assert.deepEqual(h.errors,[])
})

test('missing task after restart stops immediately instead of polling stale IDs', async () => {
  const missing = Object.assign(new Error('gone'),{response:{status:404}})
  const h = harness([missing])
  await pollTask(h.options)
  assert.equal(h.reads,1)
  assert.deepEqual(h.errors,[{code:'task_not_found'}])
})

test('server errors and persistent disconnects deliver one terminal error', async () => {
  const failed = harness([{status:'failed',error:{code:'generation_failed',message:'failed'}}])
  await pollTask(failed.options)
  assert.equal(failed.errors.length,1)
  const disconnected = harness(Array.from({length:4},()=>new Error('offline')))
  await pollTask(disconnected.options)
  assert.equal(disconnected.reads,4)
  assert.equal(disconnected.errors.length,1)
  assert.equal(disconnected.errors[0].code,'network_error')
})

test('UI callback exception cannot replay a completed result or issue another HTTP request', async () => {
  let applications = 0
  const h = harness([{status:'done',result:{status:'generated'}}],{
    onResult: () => { applications++; throw new Error('UI apply failed') },
  })
  await assert.rejects(pollTask(h.options),/UI apply failed/)
  assert.equal(h.reads,1)
  assert.equal(applications,1)
})

test('completed task without a valid result stops with a clear error', async () => {
  for (const result of [null, undefined, 'broken', []]) {
    const h = harness([{status:'done',result}])
    await pollTask(h.options)
    assert.equal(h.reads,1)
    assert.equal(h.errors[0].code,'invalid_task_result')
    assert.equal(h.results.length,0)
  }
})

test('long running tasks terminate at the time bound without fabricating success', async () => {
  const h = harness([])
  await pollTask(h.options)
  assert.equal(h.reads,4)
  assert.equal(h.errors[0].code,'task_timeout')
  assert.equal(h.results.length,0)
})
