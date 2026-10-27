import test from 'node:test'
import assert from 'node:assert/strict'
import { createChatActions, createChatState } from '../src/stores/chatActions.js'

function harness({ resume = false } = {}) {
  const calls = []
  let handlers
  let nextError = null
  const design = { patternUpdating: false, results: [], applyParseResult(result) { this.results.push(result) } }
  const api = {
    async uploadImage(file) { calls.push({ upload: file }); return { image_id: 'img_uploaded' } },
    async parse(request, callbacks) {
      calls.push({ request }); handlers = callbacks
      if (nextError) { const error = nextError; nextError = null; throw error }
      return { task_id: 'task_' + calls.length }
    },
  }
  if (resume) api.resumeTask = async (taskId, callbacks) => {
    calls.push({ resume: taskId }); handlers = callbacks
    return { task_id: taskId }
  }
  const store = Object.assign(createChatState(), createChatActions({ api, getDesignStore: () => design }))
  return { store, calls, design, result(value) { handlers.onResult(value) }, error(value) { handlers.onError(value) }, failNext(value) { nextError = value } }
}

const imageFile = { name: 'test-reference.png' }
const original = { text: '身高170cm，裙长95cm', image: 'blob:test', imageFile, scope: 'outfit' }
const proposal = { status: 'needs_input', suggested_name: '半臂＋襦裙下裳', suggested_text: '半臂；襦裙，裙长95cm', image_proposal_id: 'proposal_1', reply: '请确认', pattern: { svg_url: '/previous.svg' } }

test('a lost parse acknowledgement retains the operation identifier while a new recognition gets a fresh one', async () => {
  const h=harness({resume:true})
  h.failNext({code:'network_error',message:'POST response lost'})
  await h.store.submit(original)
  const first=h.calls.filter(c=>c.request).at(-1).request.request_id
  assert.ok(first)
  assert.equal(h.store.resumeTaskId,null) // No task identifier was received.
  await h.store.retry()
  assert.equal(h.calls.filter(c=>c.request).at(-1).request.request_id,first)
  h.result({status:'needs_input',reply:'Recognition unavailable',image_retry_available:true})
  await h.store.retry()
  assert.notEqual(h.calls.filter(c=>c.request).at(-1).request.request_id,first)
})

test('expired choices restart the image with a fresh operation instead of replaying its old cached proposal', async () => {
  const h=harness();await h.store.submit(original)
  const initial=h.calls.at(-1).request.request_id
  h.result(proposal);h.failNext({code:'invalid_image_proposal',message:'Expired'})
  await h.store.confirmComponent();await h.store.retry()
  assert.notEqual(h.calls.at(-1).request.request_id,initial)
  assert.equal(h.calls.at(-1).request.image_proposal_id,null)
  assert.equal(h.calls.at(-1).request.image,'img_uploaded')
})

test('reading an accepted image task after an outage never resubmits the image or parse request', async () => {
  const h=harness({resume:true});await h.store.submit(original)
  const taskId=h.store.task.taskId
  h.error({code:'network_error',message:'Progress read disconnected'})
  assert.equal(h.store.resumeTaskId,taskId)
  assert.equal(h.store.messages.at(-1).retryLabel,'继续查看本次结果')
  await h.store.retry()
  assert.equal(h.calls.filter(c=>c.upload).length,1)
  assert.equal(h.calls.filter(c=>c.request).length,1)
  assert.deepEqual(h.calls.at(-1),{resume:taskId})
  h.result({...proposal})
  assert.equal(h.store.lastOutcome,'awaiting_confirmation')
  assert.equal(h.store.proposalInput.image,original.image)
  assert.equal(h.store.resumeTaskId,null)
})

test('a temporary server error while reading progress resumes the accepted task', async () => {
  const h=harness({resume:true});await h.store.submit(original)
  const taskId=h.store.task.taskId
  h.error({code:'server_error',message:'Temporary backend error'})
  await h.store.retry()
  assert.deepEqual(h.calls.at(-1),{resume:taskId})
  assert.equal(h.calls.filter(c=>c.request).length,1)
})

test('timed out confirmation resumes the same accepted task and preserves the next choice', async () => {
  const h=harness({resume:true});await h.store.submit(original)
  h.result({...proposal,innerwear_choices:[{id:'chest-wrap',label:'内搭'}]})
  await h.store.confirmComponent(null,null,'chest-wrap')
  const taskId=h.store.task.taskId
  h.error({code:'task_timeout',message:'Waiting exceeded'})
  await h.store.retry()
  assert.equal(h.calls.filter(c=>c.request).length,2)
  assert.deepEqual(h.calls.at(-1),{resume:taskId})
  h.result({...proposal,image_proposal_id:'next_token',skirt_choices:[{id:'ruqun-skirt',label:'下裙'}]})
  assert.equal(h.store.proposalInput.image,original.image)
  await h.store.confirmComponent(null,'ruqun-skirt')
  assert.equal(h.calls.at(-1).request.image_proposal_id,'next_token')
  assert.equal(h.calls.at(-1).request.skirt_choice,'ruqun-skirt')
})

test('a missing accepted task after restart returns to the original image without replaying stale choices', async () => {
  const h=harness({resume:true});await h.store.submit(original)
  h.result(proposal);await h.store.confirmComponent()
  h.error({code:'network_error',message:'Disconnected'})
  await h.store.retry()
  h.error({code:'task_not_found',message:'Backend restarted'})
  assert.equal(h.store.resumeTaskId,null)
  assert.equal(h.store.lastInput.image,original.image)
  assert.equal(h.store.lastInput.imageProposalId,null)
  assert.equal(h.store.messages.at(-1).retryLabel,'重新识别这张图片')
  h.store.onDesignRestored()
  const count=h.calls.length
  await h.store.retry()
  assert.equal(h.calls.length,count)
})

test('innerwear then skirt uses each new token, retains the original photo, and generates only after both choices', async () => {
  const h=harness();await h.store.submit(original)
  h.result({...proposal,innerwear_choices:[{id:'chest-wrap',label:'直幅系带内搭'}]})
  await h.store.confirmComponent(null,null,'chest-wrap')
  assert.equal(h.calls.at(-1).request.innerwear_choice,'chest-wrap')
  h.result({...proposal,image_proposal_id:'proposal_2',skirt_choices:[{id:'ruqun-skirt',label:'襦裙'}]})
  assert.equal(h.store.lastOutcome,'awaiting_confirmation')
  assert.equal(h.store.innerwearChoices.length,0)
  assert.equal(h.store.proposalInput.image,original.image)
  assert.equal(h.design.results.at(-1).pattern.svg_url,'/previous.svg')
  await h.store.confirmComponent(null,'ruqun-skirt')
  assert.equal(h.calls.at(-1).request.image_proposal_id,'proposal_2')
  assert.equal(h.calls.at(-1).request.skirt_choice,'ruqun-skirt')
  assert.equal(h.calls.at(-1).request.innerwear_choice,undefined)
  h.result({status:'generated',reply:'All garments generated',pattern:{svg_url:'/all-five.svg'}})
  assert.equal(h.store.lastOutcome,'generated')
  assert.equal(h.store.proposalInput,null)
  assert.equal(h.calls.filter(c=>c.upload).length,1)
})

test('opening choices name their garment and clear it after restoration', async () => {
  const h=harness();await h.store.submit(original)
  h.result({...proposal,opening_choices:[{id:'center',label:'对襟'}],opening_choice_name:'立领上衣'})
  assert.equal(h.store.openingChoiceName,'立领上衣')
  h.store.onDesignRestored()
  assert.equal(h.store.openingChoiceName,null)
})

test('unknown innerwear requires an explicit bound basic and retains it on retry', async () => {
  const h=harness(); await h.store.submit(original)
  h.result({...proposal,innerwear_choices:[{id:'chest-wrap',label:'直幅后背系带内搭'}]})
  const count=h.calls.length
  await h.store.confirmComponent()
  assert.equal(h.calls.length,count)
  await h.store.confirmComponent(null,null,'chest-wrap')
  assert.equal(h.calls.at(-1).request.innerwear_choice,'chest-wrap')
  assert.equal(h.calls.at(-1).request.image_proposal_id,'proposal_1')
  h.error({code:'network_error',message:'Temporary connection loss'})
  await h.store.retry()
  assert.equal(h.calls.at(-1).request.innerwear_choice,'chest-wrap')
  assert.equal(h.calls.filter(c=>c.upload).length,1)
  h.store.onDesignRestored();assert.deepEqual(h.store.innerwearChoices,[])
})

test('an occluded skirt requires a bound choice and retains it on a transport retry', async () => {
  const h=harness()
  await h.store.submit(original)
  h.result({...proposal,skirt_choices:[{id:'mamian-skirt',label:'马面裙'},{id:'ruqun-skirt',label:'襦裙下裳'}]})
  const count=h.calls.length
  await h.store.confirmComponent()
  await h.store.confirmComponent(null,'unknown')
  assert.equal(h.calls.length,count)
  await h.store.confirmComponent(null,'ruqun-skirt')
  assert.equal(h.calls.at(-1).request.skirt_choice,'ruqun-skirt')
  assert.equal(h.calls.at(-1).request.text,proposal.suggested_text)
  assert.equal(h.store.messages.at(-1).text,'选择：襦裙下裳')
  h.error({code:'network_error',message:'Test disconnect'})
  await h.store.retry()
  assert.equal(h.calls.at(-1).request.skirt_choice,'ruqun-skirt')
  assert.equal(h.calls.filter(c=>c.upload).length,1)
})

test('skirt then opening confirmation keeps the original image and uses the new token', async () => {
  const h=harness()
  await h.store.submit(original)
  h.result({...proposal,skirt_choices:[{id:'ruqun-skirt',label:'襦裙下裳'}]})
  await h.store.confirmComponent(null,'ruqun-skirt')
  h.result({...proposal,image_proposal_id:'proposal_2',opening_choices:[{id:'center',label:'对襟'}]})
  assert.equal(h.store.skirtChoices.length,0)
  assert.equal(h.store.proposalInput.image,original.image)
  await h.store.confirmComponent('center')
  assert.equal(h.calls.at(-1).request.image_proposal_id,'proposal_2')
  assert.equal(h.calls.at(-1).request.opening_choice,'center')
  assert.equal(h.calls.at(-1).request.skirt_choice,undefined)
  h.failNext({code:'invalid_image_proposal',message:'Test restart'})
  h.error({code:'invalid_image_proposal',message:'Test stale token'})
  // Retrying this failure must return to the original image, not guess either type.
  assert.equal(h.store.lastInput.image,original.image)
  h.store.onDesignRestored()
  assert.equal(h.store.skirtChoices.length,0)
})

test('an occluded opening requires an explicit choice and retains it on retry', async () => {
  const h = harness()
  await h.store.submit(original)
  h.result({...proposal, opening_choices:[{id:'center',label:'对襟闭合'},{id:'right',label:'右侧斜开襟'}]})
  const before=h.calls.length
  await h.store.confirmComponent()
  assert.equal(h.calls.length,before)
  await h.store.confirmComponent('center')
  assert.equal(h.calls.at(-1).request.opening_choice,'center')
  assert.equal(h.calls.at(-1).request.image_proposal_id,proposal.image_proposal_id)
  h.error({code:'network_error',message:'Test transient connection loss'})
  await h.store.retry()
  assert.equal(h.calls.at(-1).request.opening_choice,'center')
  assert.equal(h.calls.filter(c=>c.upload).length,1)
})

test('restoring a saved design clears stale confirmation and retry context', async () => {
  const h = harness()
  await h.store.submit(original)
  h.result(proposal)
  h.store.onDesignRestored()
  assert.equal(h.store.lastOutcome,'generated')
  for (const key of ['proposalInput','lastInput','imageProposalId','suggestedComponent','retryMessageId']) {
    assert.equal(h.store[key],null,key)
  }
  const requests = h.calls.length
  await h.store.confirmComponent()
  await h.store.retry()
  assert.equal(h.calls.length,requests)
})

test('expired image confirmation retries original image and scope, never its stale token', async () => {
  const h = harness()
  await h.store.submit(original)
  h.result(proposal)
  h.store.imageScope = 'component'
  h.failNext({ code: 'invalid_image_proposal', message: '图片建议已失效' })
  await h.store.confirmComponent()
  await h.store.retry()
  const request = h.calls.filter(c => c.request).at(-1).request
  assert.equal(request.image, 'img_uploaded')
  assert.equal(request.image_proposal_id, null)
  assert.equal(request.scope, 'outfit')
  assert.equal(request.text, original.text)
  assert.equal(h.calls.filter(c => c.upload).length, 1)
})

test('lost upload reference retains the File and reuploads on explicit retry', async () => {
  const h = harness()
  await h.store.submit(original)
  h.error({ code: 'image_not_found', message: '图片不存在' })
  await h.store.retry()
  assert.equal(h.calls.filter(c => c.upload).length, 2)
  assert.equal(h.calls.filter(c => c.request).at(-1).request.scope, 'outfit')
})

test('transient confirmation failure retries confirmation without a second vision request', async () => {
  const h = harness()
  await h.store.submit(original)
  h.result(proposal)
  h.failNext({ code: 'network_error', message: '连接中断' })
  await h.store.confirmComponent()
  await h.store.retry()
  const request = h.calls.filter(c => c.request).at(-1).request
  assert.equal(request.image, null)
  assert.equal(request.image_proposal_id, 'proposal_1')
  assert.equal(request.scope, 'outfit')
  assert.equal(h.calls.filter(c => c.upload).length, 1)
})

test('pending, rejected and completed requests expose distinct outcome states', async () => {
  const h = harness()
  await h.store.submit(original)
  h.result(proposal)
  assert.equal(h.store.lastOutcome, 'awaiting_confirmation')
  await h.store.confirmComponent()
  h.result({ status: 'generated', reply: '已生成', pattern: { svg_url: '/new.svg' } })
  assert.equal(h.store.lastOutcome, 'generated')
  assert.equal(h.store.proposalInput, null)
  assert.equal(h.store.lastInput, null)
  assert.equal(h.design.results.at(-1).pattern.svg_url, '/new.svg')
})
