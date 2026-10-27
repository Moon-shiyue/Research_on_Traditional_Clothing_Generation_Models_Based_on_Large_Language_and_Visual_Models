/**
 * API 入口 —— mock / real 一键切换
 * .env: VITE_API_MODE=mock | real
 * 页面代码只 import { api }，不感知后端是否存在
 */
import { createMockApi } from './mock'
import { createRealApi } from './real'

const mode = import.meta.env.VITE_API_MODE || 'real'
export const api = mode === 'real' ? createRealApi() : createMockApi()
export const apiMode = mode
