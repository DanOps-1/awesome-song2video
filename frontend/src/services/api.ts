import axios from 'axios';

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// 类型定义
export interface Mix {
  id: string;
  song_title: string;
  status: string;
  created_at: string;
}

export interface MixLine {
  id: string;
  text: string;
  start_time: number;
  end_time: number;
  clip_id?: string | null;
  clip_url?: string | null;
  clip_source?: string | null;
}

interface MixLineResponse {
  id: string;
  line_no: number;
  original_text: string;
  start_time_ms: number;
  end_time_ms: number;
  auto_confidence: number;
  selected_segment_id: string | null;
  status: string;
  annotations: any;
  candidates: Array<{
    id: string;
    source_video_id: string;
    start_time_ms: number;
    end_time_ms: number;
    score: number;
  }>;
  audit_log: any[];
}

export interface RenderStatus {
  job_id: string;
  status: string;
  output_url?: string | null;
}

// API 方法对象
export const mixService = {
  createMix: async (songTitle: string, lyrics: string) => {
    const response = await api.post<Mix>('/mixes', {
      song_title: songTitle,
      lyrics_text: lyrics,
      source_type: 'upload',
    });
    return response.data;
  },

  generateTimeline: async (mixId: string) => {
    await api.post(`/mixes/${mixId}/generate-timeline`);
  },

  getLines: async (mixId: string) => {
    const response = await api.get<{ lines: MixLineResponse[] }>(`/mixes/${mixId}/lines`);
    // 转换后端数据格式到前端格式
    return response.data.lines.map(line => ({
      id: line.id,
      text: line.original_text,
      start_time: line.start_time_ms / 1000, // 毫秒转秒
      end_time: line.end_time_ms / 1000, // 毫秒转秒
      clip_id: line.selected_segment_id,
      clip_url: null, // 暂时为空
      clip_source: line.candidates[0]?.source_video_id || null, // 使用第一个候选的视频ID
    }));
  },

  updateLineClip: async (mixId: string, lineId: string, clipId: string) => {
    await api.patch(`/mixes/${mixId}/lines/${lineId}`, {
      clip_id: clipId,
    });
  },

  searchClip: async (mixId: string, lineId: string, query: string) => {
    const response = await api.post(`/mixes/${mixId}/lines/${lineId}/search`, {
      query: query,
    });
    return response.data;
  },

  getPreview: async (mixId: string) => {
    const response = await api.get(`/mixes/${mixId}/preview`);
    return response.data;
  },

  startRender: async (mixId: string) => {
    const response = await api.post<{ job_id: string }>(`/mixes/${mixId}/render`);
    return response.data;
  },

  getRenderStatus: async (mixId: string, jobId: string) => {
    const response = await api.get<RenderStatus>(`/mixes/${mixId}/render`, {
      params: { job_id: jobId },
    });
    return response.data;
  },
};