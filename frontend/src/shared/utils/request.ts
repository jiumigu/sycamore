import axios from 'axios'
import type { AxiosInstance, AxiosResponse } from 'axios'

const request: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

request.interceptors.request.use(
  (config) => {
    // 默认 Content-Type: application/json 会让 axios 的默认 transformRequest
    // 对 FormData 做 JSON.stringify(formDataToJSON(data)) → 后端 request.FILES 为空
    // 移除 Content-Type，交由浏览器 XHR 自动生成 multipart/form-data; boundary=...
    if (config.data instanceof FormData) {
      config.headers.delete('Content-Type')
    }
    return config
  },
  (error) => Promise.reject(error),
)

request.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  },
)

export default request
