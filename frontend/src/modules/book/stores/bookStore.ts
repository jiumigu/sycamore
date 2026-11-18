import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as bookApi from '../api/bookApi'
import type { BookListParams, BookStats, ReadingFocus, ReadingFocusCloseMode } from '../types/bookTypes'
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

  async function fetchStats(params?: { year?: string }) {
    try {
      const response = await bookApi.getBookStats(params)
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

  /** 批量改「阅读状态」/「阅读深度」。口径（能改哪些状态）在后端，这里只搬运。 */
  async function bulkUpdateBooks(
    bids: number[],
    payload: { status?: string; reading_depth?: number },
  ) {
    try {
      const response = await bookApi.bulkUpdateBooks(bids, payload)
      return response.data
    } catch (error) {
      console.error('批量修改失败:', error)
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

  /** 当前在读的那一本。`null` = 还没指定，**不是**加载失败。 */
  const focus = ref<ReadingFocus | null>(null)

  async function fetchReadingFocus() {
    try {
      const response = await bookApi.getReadingFocus()
      focus.value = response.data
      return response.data
    } catch (error) {
      console.error('获取当前在读失败:', error)
      throw error
    }
  }

  /** 换书 —— 必须带旧书结论（`closeMode`），否则后端 400。 */
  async function switchFocus(
    bookId: number,
    closeMode?: ReadingFocusCloseMode,
    reason?: string,
  ) {
    submitting.value = true
    try {
      const response = await bookApi.switchReadingFocus(bookId, closeMode, reason)
      focus.value = response.data
      return response.data
    } catch (error) {
      console.error('换书失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  /** 换书弹窗里的候选书（本地一份，**不写 `bookList`**）。
   *
   *  🔴 不能借用 `fetchBookList`：它会顺手改写 `bookList` / `totalCount`，
   *     于是弹窗里搜一次，背后的表格就被换掉了 —— 关掉弹窗看到的是搜索结果，
   *     而筛选条还写着原来的条件。 */
  const focusCandidates = ref<Book[]>([])

  async function searchFocusCandidates(keyword = '') {
    // 口径（哪些书能当候选、当前这本排不排）**全在后端**（v3.64.81）。
    // 🔴 这里不要再 filter：原来那句 `b.bid !== focus.value?.book?.bid` 是
    //    仅剩的本地口径，后端已经在 `candidate_queryset` 里排除过一遍；
    //    两边各写一份，将来放宽规则时必有一边漏掉 —— 而且漏了不报错，
    //    只是弹窗里多出几本不该出现的书（用户报的就是这个）。
    const response = await bookApi.getFocusCandidates(keyword)
    focusCandidates.value = response.data?.results ?? []
    return focusCandidates.value
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
    currentBook, focus, focusCandidates,
    fetchBookList, fetchBookById, fetchStats, createNewBook, updateExistingBook,
    deleteExistingBook, bulkDeleteBooks, bulkUpdateBooks, markAsCompleted,
    fetchReadingFocus, switchFocus, searchFocusCandidates,
    resetState,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useBookStore, import.meta.hot))
}
