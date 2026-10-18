/// <reference types="vite/client" />

/**
 * 构建 ID —— 由 `vite.config.ts` 的 `define` 在**编译期**替换成字符串字面量。
 *
 * 语义：这是「这个页面加载时服务端手上的那份代码」的编号。
 * 远端 `/build_id.json` 给的是**服务端当前**的编号，两者不等
 * ⇒ 这个标签页在跑旧代码（见 `shared/utils/buildVersion.ts`）。
 */
declare const __BUILD_ID__: string
