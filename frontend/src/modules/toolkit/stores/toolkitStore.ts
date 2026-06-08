import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '../api/toolkitApi'
import type { ToolDefinition, CategoryInfo, ExecutionRecord, ToolResult } from '../types/toolkitTypes'

export const useToolkitStore = defineStore('toolkit', () => {
  const tools = ref<ToolDefinition[]>([])
  const categories = ref<CategoryInfo[]>([])
  const currentTool = ref<ToolDefinition | null>(null)
  const loading = ref(false)
  const executing = ref(false)
  const executionResult = ref<ToolResult | null>(null)
  const currentExecutionId = ref<number | null>(null)
  const executionStatus = ref<string>('')
  const progress = ref(0)
  const history = ref<ExecutionRecord[]>([])
  const historyTotal = ref(0)

  async function fetchTools(category?: string) {
    loading.value = true
    try {
      const res = await api.getToolList(category)
      tools.value = res.data.tools || []
      categories.value = res.data.categories || []
      return res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchToolDetail(toolKey: string) {
    const res = await api.getToolDetail(toolKey)
    currentTool.value = res.data
    return res.data
  }

  async function runTool(toolKey: string, params: Record<string, unknown>) {
    executing.value = true
    executionResult.value = null
    currentExecutionId.value = null
    executionStatus.value = 'running'
    progress.value = 0
    try {
      const res = await api.executeTool(toolKey, params)
      currentExecutionId.value = res.data.execution_id
      executionStatus.value = res.data.status
      if (res.data.result) {
        executionResult.value = res.data.result
        progress.value = 100
      }
      return res.data
    } catch (e: any) {
      executionStatus.value = 'failed'
      throw e
    } finally {
      executing.value = false
    }
  }

  async function pollStatus(executionId: number) {
    const res = await api.getTaskStatus(executionId)
    const data = res.data
    executionStatus.value = data.status
    progress.value = data.progress || 0
    if (data.result) {
      executionResult.value = data.result
    }
    return data
  }

  async function runFileTool(toolKey: string, file: File, mode: string) {
    executing.value = true
    executionResult.value = null
    executionStatus.value = 'running'
    progress.value = 0
    try {
      const formData = new FormData()
      formData.append('tool_key', toolKey)
      formData.append('file', file)
      formData.append('mode', mode)
      const res = await api.convertFile(formData)
      executionStatus.value = res.data.status
      if (res.data.result) {
        executionResult.value = res.data.result
        progress.value = 100
      }
      return res.data
    } catch (e: any) {
      executionStatus.value = 'failed'
      throw e
    } finally {
      executing.value = false
    }
  }

  async function fetchHistory(params?: Record<string, unknown>) {
    const res = await api.getHistory(params)
    history.value = res.data.results || []
    historyTotal.value = res.data.total || 0
    return res.data
  }

  function resetExecution() {
    executionResult.value = null
    currentExecutionId.value = null
    executionStatus.value = ''
    progress.value = 0
  }

  return {
    tools, categories, currentTool, loading, executing,
    executionResult, currentExecutionId, executionStatus, progress,
    history, historyTotal,
    fetchTools, fetchToolDetail, runTool, runFileTool, pollStatus, fetchHistory, resetExecution,
  }
})
