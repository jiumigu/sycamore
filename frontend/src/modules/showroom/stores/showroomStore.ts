import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as showroomApi from '../api/showroomApi'
import type {
  ShowroomCase, ShowroomMeta, ShowroomPreview, ShowroomProfile,
  ShowroomSkill, ShowroomWork,
} from '../types/showroomTypes'

export const useShowroomStore = defineStore('showroom', () => {
  const profile = ref<ShowroomProfile | null>(null)
  const cases = ref<ShowroomCase[]>([])
  const skills = ref<ShowroomSkill[]>([])
  const works = ref<ShowroomWork[]>([])
  const meta = ref<ShowroomMeta | null>(null)
  const preview = ref<ShowroomPreview | null>(null)

  const loading = ref(false)
  /**
   * 预览**取数失败**（区别于「还没有内容」）。
   * 🔴 裸 `catch { preview = null }` 会把「接口挂了」画成「展厅还是空的」。
   */
  const loadError = ref(false)

  async function fetchProfile() {
    const res = await showroomApi.getProfile()
    profile.value = res.data
    return res.data
  }

  async function saveProfile(data: Partial<ShowroomProfile>) {
    const res = await showroomApi.updateProfile(data)
    profile.value = res.data
    return res.data
  }

  async function fetchMeta() {
    const res = await showroomApi.getMeta()
    meta.value = res.data
    return res.data
  }

  async function fetchCases() {
    const res = await showroomApi.getCases()
    cases.value = Array.isArray(res.data) ? res.data : []
  }

  async function createCase(data: Record<string, unknown>) {
    const res = await showroomApi.createCase(data)
    return res.data
  }

  async function updateCase(id: number, data: Record<string, unknown>) {
    const res = await showroomApi.updateCase(id, data)
    return res.data
  }

  async function deleteCase(id: number) {
    await showroomApi.deleteCase(id)
  }

  async function fetchSkills() {
    const res = await showroomApi.getSkills()
    skills.value = Array.isArray(res.data) ? res.data : []
  }

  async function createSkill(data: Record<string, unknown>) {
    const res = await showroomApi.createSkill(data)
    return res.data
  }

  async function updateSkill(id: number, data: Record<string, unknown>) {
    const res = await showroomApi.updateSkill(id, data)
    return res.data
  }

  async function deleteSkill(id: number) {
    await showroomApi.deleteSkill(id)
  }

  async function fetchWorks() {
    const res = await showroomApi.getWorks()
    works.value = Array.isArray(res.data) ? res.data : []
  }

  async function createWork(data: Record<string, unknown>) {
    const res = await showroomApi.createWork(data)
    return res.data
  }

  async function updateWork(id: number, data: Record<string, unknown>) {
    const res = await showroomApi.updateWork(id, data)
    return res.data
  }

  async function deleteWork(id: number) {
    await showroomApi.deleteWork(id)
  }

  async function fetchPreview() {
    loading.value = true
    loadError.value = false
    try {
      const res = await showroomApi.getPreview()
      preview.value = res.data
    } catch {
      preview.value = null
      loadError.value = true
    } finally {
      loading.value = false
    }
    return preview.value
  }

  return {
    profile, cases, skills, works, meta, preview, loading, loadError,
    fetchProfile, saveProfile, fetchMeta,
    fetchCases, createCase, updateCase, deleteCase,
    fetchSkills, createSkill, updateSkill, deleteSkill,
    fetchWorks, createWork, updateWork, deleteWork,
    fetchPreview,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，Pinia store 实例不会重建 —— 改本文件后
// 页面跑的还是旧定义（模板新、数据逻辑旧）。生产构建里整段被 tree-shake。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useShowroomStore, import.meta.hot))
}
