/** Poll transport failures separately from UI callbacks; callbacks run at most once. */
export async function pollTask({ readTask, handlers = {}, wrapError, now = Date.now,
  sleep = ms => new Promise(resolve => setTimeout(resolve, ms)),
  timeoutMs = 10 * 60 * 1000, intervalMs = 1500, maxFailures = 4 }) {
  const started = now()
  let failures = 0
  while (now() - started < timeoutMs) {
    let task
    try {
      task = await readTask()
      failures = 0
    } catch (error) {
      failures += 1
      if (error.response?.status === 404 || failures >= maxFailures) {
        handlers.onError?.(wrapError(error))
        return
      }
      await sleep(intervalMs)
      continue
    }
    if (task.status === 'done') {
      if (!task.result || typeof task.result !== 'object' || Array.isArray(task.result)) {
        handlers.onError?.({ code: 'invalid_task_result', message: '任务未返回有效结果，请刷新纸样检查。' })
      } else {
        handlers.onResult?.(task.result)
      }
      return
    }
    if (task.status === 'failed') {
      handlers.onError?.(task.error || { message: '生成未完成，请调整输入重试。' })
      return
    }
    handlers.onProgress?.({ stage: task.stage, progress: task.progress })
    await sleep(intervalMs)
  }
  handlers.onError?.({ code: 'task_timeout', message: '等待时间过长，请稍后刷新纸样或检查后端。' })
}
