import request from '@/shared/utils/request'
import type { BookListParams, BookStats } from '../types/bookTypes'

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

export function getBookStats() {
  return request<BookStats>({
    url: '/books/stats/',
    method: 'get',
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
