/**
 * 展示媒体 —— **唯一实现**（作品库 works 与展厅 showroom 共用）。
 *
 * 🔴 `type` 由**后端上传接口按扩展名判定**下发，前端不写第二份判据；
 *    前端只存 `{type, url}`、只查表渲染。
 */
export interface MediaItem {
  type: 'image' | 'video'
  url: string
}
