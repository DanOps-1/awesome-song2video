import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

// 添加响应拦截器，提取后端错误信息
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // 提取后端返回的错误详情
    let message = '请求失败'
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') {
      message = detail
    } else if (Array.isArray(detail)) {
      // Pydantic 验证错误格式: [{loc: [...], msg: "...", type: "..."}]
      message = detail.map((d: any) => d.msg || d.message).join('; ')
    } else if (detail && typeof detail === 'object') {
      message = JSON.stringify(detail)
    } else if (error.message) {
      message = error.message
    }
    console.error('API Error:', error.response?.data || error)
    return Promise.reject(new Error(message))
  }
)

export default apiClient
