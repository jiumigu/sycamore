/** Core — API 层 */

import request from '@/shared/utils/request'

export function backupDatabase() {
  return request({ url: '/core/backup/database/', method: 'post' })
}

export function quickRecord(data: { module: string; content: string }) {
  return request({ url: '/core/quick-record/', method: 'post', data })
}
