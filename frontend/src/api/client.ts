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
    const message = error.response?.data?.detail || error.message || '请求失败'
    const enhancedError = new Error(message)
    return Promise.reject(enhancedError)
  }
)

export default apiClient
