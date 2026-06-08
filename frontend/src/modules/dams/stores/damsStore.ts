import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '../api/damsApi'
import type {
  AttentionMapData, DamsAccessLog, DamsFileResourceList,
} from '../types/damsTypes'

export const useDamsStore = defineStore('dams', () => {
  const files = ref<DamsFileResourceList[]>([])
  const totalCount = ref(0)
  const loading = ref(false)
  const attentionMap = ref<AttentionMapData | null>(null)
  const accessLogs = ref<DamsAccessLog[]>([])

  async function fetchFiles(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const res = await api.getFileList(params)
      if (res.data.results) {
        files.value = res.data.results
        totalCount.value = res.data.count
      } else if (Array.isArray(res.data)) {
        files.value = res.data
        totalCount.value = res.data.length
      }
      return res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchAttentionMap(params?: Record<string, unknown>) {
    const res = await api.getAttentionMap(params)
    attentionMap.value = res.data
    return res.data
  }

  async function fetchAccessLogs(params?: Record<string, unknown>) {
    const res = await api.getAccessLogList(params)
    if (res.data.results) {
      accessLogs.value = res.data.results
    } else if (Array.isArray(res.data)) {
      accessLogs.value = res.data
    }
    return res.data
  }

  async function createFile(data: Record<string, unknown>) {
    await api.createFile(data)
    await fetchFiles()
  }

  async function updateFile(id: number, data: Record<string, unknown>) {
    await api.updateFile(id, data)
    await fetchFiles()
  }

  async function deleteFile(id: number) {
    await api.deleteFile(id)
    await fetchFiles()
  }

  async function markOrganized(id: number) {
    await api.markFileOrganized(id)
    await fetchFiles()
  }

  return {
    files, totalCount, loading, attentionMap, accessLogs,
    fetchFiles, fetchAttentionMap, fetchAccessLogs,
    createFile, updateFile, deleteFile, markOrganized,
  }
})
