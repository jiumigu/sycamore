import request from '@/shared/utils/request'
import type {
  Book, BookListParams, BookStats, ReadingFocus, ReadingFocusCloseMode, ReadingFocusSwitchResult,
} from '../types/bookTypes'

export function getBookList(params?: BookListParams) {
  return request({
    url: '/books/',
    method: 'get',
    params,
  })
}

export function getBookDetail(id: number) {
  return request({
    url: `/books/${id}/`,
    method: 'get',
  })
}

export function createBook(data: Record<string, unknown>) {
  return request({
    url: '/books/',
    method: 'post',
    data,
  })
}

export function updateBook(id: number, data: Record<string, unknown>) {
  return request({
    url: `/books/${id}/`,
    method: 'put',
    data,
  })
}

export function deleteBook(id: number) {
  return request({
    url: `/books/${id}/`,
    method: 'delete',
  })
}

export function bulkDeleteBooks(bids: number[]) {
  return request({
    url: '/books/bulk_delete/',
    method: 'delete',
    data: { bids },
  })
}

/** 批量改「阅读状态」/「阅读深度」。
 *
 *  `payload` 两个字段至少给一个；`status` 不接受「弃读」（后端 400）。
 *  返回里的 `requested` 是**传进去的编号个数**、`updated` 是**实际改动的行数** ——
 *  选中的书可能已被别处删掉，两个数要分开看，别把命中数当请求数。 */
export function bulkUpdateBooks(
  bids: number[],
  payload: { status?: string; reading_depth?: number },
) {
  return request<{ updated: number; requested: number }>({
    url: '/books/bulk_update/',
    method: 'post',
    data: { bids, ...payload },
  })
}

export function getBookStats(params?: { year?: string }) {
  return request<BookStats>({
    url: '/books/stats/',
    method: 'get',
    params,
  })
}

export function getBooksByYear(year: string, params?: BookListParams) {
  return request({
    url: '/books/by_year/',
    method: 'get',
    params: { year, ...params },
  })
}

export function getBooksByType(btype: string, params?: BookListParams) {
  return request({
    url: '/books/by_type/',
    method: 'get',
    params: { btype, ...params },
  })
}

export function searchBooksByTag(tag: string, params?: BookListParams) {
  return request({
    url: '/books/search_by_tag/',
    method: 'get',
    params: { tag, ...params },
  })
}

export function markAsCompleted(id: number) {
  return request({
    url: `/books/${id}/mark_completed/`,
    method: 'post',
  })
}

/** 当前在读的那一本（全库唯一）。只读接口，看一眼不会建行。 */
export function getReadingFocus() {
  return request<ReadingFocus>({
    url: '/books/reading-focus/',
    method: 'get',
  })
}

/** 换书弹窗的候选（v3.64.81）。**口径在后端**：只含还能读的书（待读 / 在读 /
 *  二刷 / 搁置），且已排除当前这本 —— 前端不许再筛一遍，那是第二份口径。 */
export function getFocusCandidates(search = '') {
  return request<{ results: Book[]; count: number }>({
    url: '/books/reading-focus/candidates/',
    method: 'get',
    params: search ? { search } : {},
  })
}

/** 换书。`closeMode` 是**给旧书的结论**：没有旧书时不要传（传了后端 400）。 */
export function switchReadingFocus(
  bookId: number,
  closeMode?: ReadingFocusCloseMode,
  reason?: string,
) {
  return request<ReadingFocusSwitchResult>({
    url: '/books/reading-focus/switch/',
    method: 'post',
    data: { book_id: bookId, close_mode: closeMode, reason: reason || '' },
  })
}

