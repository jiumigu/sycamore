import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as readerApi from '../api/readerApi'
import type { ReaderGroup, ReaderInteraction, ReaderMonthlySummary, ReaderYearlyStats } from '../types/readerTypes'

export const useReaderStore = defineStore('reader', () => {
  const groups = ref<ReaderGroup[]>([])
  const interactions = ref<ReaderInteraction[]>([])
  const resonancePoints = ref<ReaderInteraction[]>([])
  const monthlySummaries = ref<ReaderMonthlySummary[]>([])
  const yearlyStats = ref<ReaderYearlyStats | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const selectedGroupId = ref<number | null>(null)

  const formVisible = ref(false)
  const groupFormVisible = ref(false)

  function extractList<T>(data: unknown): T[] {
    if (data && typeof data === 'object' && 'results' in (data as Record<string, unknown>)) {
      return Array.isArray((data as Record<string, unknown>).results)
        ? ((data as Record<string, unknown>).results as T[]).filter(Boolean)
        : []
    }
    return Array.isArray(data) ? (data as T[]).filter(Boolean) : []
  }

  async function fetchGroups() {
    try {
      const res = await readerApi.getReaderGroups()
      groups.value = extractList<ReaderGroup>(res.data)
    } catch (e) {
      console.error('获取读者群体失败:', e)
      groups.value = []
    }
  }

  async function createGroup(data: Record<string, unknown>) {
    saving.value = true
    try {
      await readerApi.createReaderGroup(data)
      groupFormVisible.value = false
      await fetchGroups()
    } finally {
      saving.value = false
    }
  }

  async function deleteGroup(id: number) {
    try {
      await readerApi.deleteReaderGroup(id)
      if (selectedGroupId.value === id) selectedGroupId.value = null
      await fetchGroups()
      await fetchInteractions()
    } catch (e) {
      console.error('删除群体失败:', e)
    }
  }

  async function fetchInteractions(groupId?: number) {
    loading.value = true
    try {
      const res = await readerApi.getReaderInteractions(groupId)
      interactions.value = extractList<ReaderInteraction>(res.data)
    } finally {
      loading.value = false
    }
  }

  async function createInteraction(data: Record<string, unknown>) {
    saving.value = true
    try {
      await readerApi.createReaderInteraction(data)
      formVisible.value = false
      await Promise.all([
        fetchInteractions(selectedGroupId.value || undefined),
        fetchResonancePoints(selectedGroupId.value || undefined),
        fetchGroups(),
      ])
    } finally {
      saving.value = false
    }
  }

  async function deleteInteraction(id: number) {
    try {
      await readerApi.deleteReaderInteraction(id)
      await Promise.all([
        fetchInteractions(selectedGroupId.value || undefined),
        fetchResonancePoints(selectedGroupId.value || undefined),
        fetchGroups(),
      ])
    } catch (e) {
      console.error('删除互动失败:', e)
    }
  }

  async function fetchResonancePoints(groupId?: number) {
    try {
      const res = await readerApi.getResonancePoints(groupId)
      resonancePoints.value = extractList<ReaderInteraction>(res.data)
    } catch (e) {
      console.error('获取共振点失败:', e)
    }
  }

  async function fetchMonthlySummaries(params?: Record<string, unknown>) {
    try {
      const res = await readerApi.getMonthlySummaries(params)
      monthlySummaries.value = extractList<ReaderMonthlySummary>(res.data)
    } catch (e) {
      console.error('获取月末盘点失败:', e)
      monthlySummaries.value = []
    }
  }

  async function fetchYearlyStats(params?: Record<string, unknown>) {
    try {
      const res = await readerApi.getReaderYearlyStats(params)
      yearlyStats.value = res.data
    } catch (e) {
      console.error('获取年度统计失败:', e)
      yearlyStats.value = null
    }
  }

  async function createMonthlySummary(data: Record<string, unknown>) {
    saving.value = true
    try {
      await readerApi.createMonthlySummary(data)
      await fetchMonthlySummaries()
      await fetchYearlyStats()
    } finally {
      saving.value = false
    }
  }

  async function updateMonthlySummary(id: number, data: Record<string, unknown>) {
    saving.value = true
    try {
      await readerApi.updateMonthlySummary(id, data)
      await fetchMonthlySummaries()
      await fetchYearlyStats()
    } finally {
      saving.value = false
    }
  }

  async function deleteMonthlySummary(id: number) {
    try {
      await readerApi.deleteMonthlySummary(id)
      await fetchMonthlySummaries()
      await fetchYearlyStats()
    } catch (e) {
      console.error('删除盘点失败:', e)
    }
  }

  async function fetchAll() {
    await Promise.all([
      fetchGroups(),
      fetchInteractions(),
      fetchResonancePoints(),
      fetchMonthlySummaries(),
      fetchYearlyStats(),
    ])
  }

  return {
    groups, interactions, resonancePoints,
    monthlySummaries, yearlyStats,
    loading, saving, selectedGroupId,
    formVisible, groupFormVisible,
    fetchGroups, createGroup, deleteGroup,
    fetchInteractions, createInteraction, deleteInteraction,
    fetchResonancePoints, fetchAll,
    fetchMonthlySummaries, fetchYearlyStats,
    createMonthlySummary, updateMonthlySummary, deleteMonthlySummary,
  }
})
