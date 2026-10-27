/** Shared state loading and generated-result application, without Pinia/DOM. */
export async function loadDesignState(store, api) {
  const revision = ++store.loadRevision
  store.loadError = ''
  try {
    const [design, body, pattern] = await Promise.all([
      api.getDesignParams(), api.getBodyParams(), api.getPattern(),
    ])
    if (revision !== store.loadRevision) return false
    store.designParams = design
    store.bodyParams = body
    store.pattern = pattern
    store.loaded = true
    return true
  } catch (error) {
    if (revision !== store.loadRevision) return false
    store.loadError = error.message || '后端未连接，请启动制版服务后重试。'
    return false
  }
}

export function applyDesignResult(store, result) {
  // A parse/restore response is newer than any initial GET still in flight.
  // Clarifications with no new state must still allow initial body loading.
  if (result.status === 'generated' || result.design_params || result.body_params) store.loadRevision++
  store.loadError = ''
  if (result.design_params) {
    store.designParams = { ...store.designParams, params: result.design_params, is_sectioned: true }
  }
  if ('pattern' in result) store.pattern = result.pattern
  if (result.body_params) store.bodyParams = result.body_params
  if (result.design_params && result.body_params) store.loaded = true
  store.designList = result.design_list || []
}
