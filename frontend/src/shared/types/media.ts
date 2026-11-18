/**
 * 展示媒体 —— **唯一实现**（作品库 works 与展厅 showroom 共用）。
 *
 * 🔴 `type` 由**后端上传接口按扩展名判定**下发，前端不写第二份判据；
 *    前端只存 `{type, url}`、只查表渲染。
 */
export interface MediaItem {
  type: 'image' | 'video'
  url: string
  /**
   * 列表缩略图（后端按 `{stem}_thumb.jpg` 派生，**没生成过是 `null`**）。
   *
   * 🔴 只给列表格子用，预览一律用 `url`：拿缩略图做预览等于把「看细节」
   *    悄悄降级成 200px，而且不报错。
   * ⚠️ 可选 —— 视频没有这个键（不是 `null`，是根本没有）。
   */
  thumb?: string | null
}
