import request from '@/shared/utils/request'
import type {
  LifeSample,
  LifeSampleForm,
  ObsidianConfig,
  ScanResult,
  Stats,
  SyncResult,
} from '../types'

/** 组装 open 端点路径：路径各段分别编码，保留 `/`（避免 %2F 被 Django 提前解码破坏匹配） */
function encodePath(path: string): string {
  return path
    .split('/')
    .map((seg) => encodeURIComponent(seg))
    .join('/')
}

export const sampleApi = {
  getList(params?: { search?: string; type?: string; status?: string; relevance?: string; tag?: string }) {
    return request.get<LifeSample[]>('/lifesample/samples/', { params })
  },

  getDetail(id: number) {
    return request.get<LifeSample>(`/lifesample/samples/${id}/`)
  },

  create(data: Partial<LifeSampleForm>) {
    return request.post<LifeSample>('/lifesample/samples/', data)
  },

  update(id: number, data: Partial<LifeSampleForm>) {
    return request.patch<LifeSample>(`/lifesample/samples/${id}/`, data)
  },

  delete(id: number) {
    return request.delete(`/lifesample/samples/${id}/`)
  },

  getTags() {
    return request.get<string[]>('/lifesample/samples/tags/')
  },

  getStats() {
    return request.get<Stats>('/lifesample/samples/stats/')
  },

  syncFromObsidian() {
    return request.post<SyncResult>('/lifesample/samples/sync-from-obsidian/')
  },

  getObsidianConfig() {
    return request.get<ObsidianConfig>('/lifesample/obsidian/config/')
  },

  updateObsidianConfig(data: Partial<ObsidianConfig>) {
    return request.post<ObsidianConfig>('/lifesample/obsidian/config/', data)
  },

  scanObsidian() {
    return request.get<ScanResult[]>('/lifesample/obsidian/scan/')
  },

  openObsidianFile(path: string) {
    return request.get<{ uri: string }>(`/lifesample/obsidian/open/${encodePath(path)}/`)
  },
}
