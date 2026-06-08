import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as bookApi from '../api/bookApi'
import type { BookListParams, BookStats } from '../types/bookTypes'
import type { Book } from '../types/bookTypes'

export const useBookStore = defineStore('book', () => {
  const bookList = ref<Book[]>([])
  const stats = ref<BookStats | null>(null)
  const loading = ref(false)
  const submitting = ref(false)
  const totalCount = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(20)

  async function fetchBookList(params?: BookListParams) {
    loading.value = true
    try {
      const response = await bookApi.getBookList({
        page: currentPage.value,
        page_size: pageSize.value,
        ...params,
      })
      if (response.data.results) {
        bookList.value = response.data.results
        totalCount.value = response.data.count
      } else if (Array.isArray(response.data)) {
        bookList.value = response.data
        totalCount.value = response.data.length
      }
      return response.data
    } catch (error) {
      console.error('获取书籍列表失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  const currentBook = ref<Book | null>(null)

  async function fetchBookById(id: number) {
    loading.value = true
    try {
      const response = await bookApi.getBookDetail(id)
      currentBook.value = response.data
      return response.data
    } catch (error) {
      console.error('获取书籍详情失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const response = await bookApi.getBookStats()
      stats.value = response.data
      return response.data
    } catch (error) {
      console.error('获取统计失败:', error)
      throw error
    }
  }

  async function createNewBook(data: Record<string, unknown>) {
    submitting.value = true
    try {
      const response = await bookApi.createBook(data)
      return response.data
    } catch (error) {
      console.error('创建书籍失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  async function updateExistingBook(id: number, data: Record<string, unknown>) {
    submitting.value = true
    try {
      const response = await bookApi.updateBook(id, data)
      return response.data
    } catch (error) {
      console.error('更新书籍失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  async function deleteExistingBook(id: number) {
    try {
      await bookApi.deleteBook(id)
      return true
    } catch (error) {
      console.error('删除书籍失败:', error)
      throw error
    }
  }

  async function bulkDeleteBooks(bids: number[]) {
    try {
      const response = await bookApi.bulkDeleteBooks(bids)
      return response.data
    } catch (error) {
      console.error('批量删除失败:', error)
      throw error
    }
  }

  async function markAsCompleted(id: number) {
    try {
      const response = await bookApi.markAsCompleted(id)
      return response.data
    } catch (error) {
      console.error('标记完成失败:', error)
      throw error
    }
  }

  function resetState() {
    bookList.value = []
    stats.value = null
    loading.value = false
    submitting.value = false
    totalCount.value = 0
    currentPage.value = 1
    pageSize.value = 20
  }

  return {
    bookList, stats, loading, submitting, totalCount, currentPage, pageSize,
    currentBook,
    fetchBookList, fetchBookById, fetchStats, createNewBook, updateExistingBook,
    deleteExistingBook, bulkDeleteBooks, markAsCompleted,
    resetState,
  }
})
