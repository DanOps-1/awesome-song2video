import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { mixService } from '../services/api';

export default function Home() {
  const [title, setTitle] = useState('');
  const [lyrics, setLyrics] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !lyrics.trim()) return;

    setLoading(true);
    try {
      const mix = await mixService.createMix(title, lyrics);
      await mixService.generateTimeline(mix.id);
      navigate(`/editor/${mix.id}`);
    } catch (error) {
      console.error('Failed to create mix:', error);
      alert('创建失败，请确保后端服务已启动。');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-white flex items-center justify-center p-6">
      <div className="max-w-xl w-full bg-slate-800 p-10 rounded-3xl shadow-2xl border border-slate-700">
        <div className="text-center mb-10">
          <h1 className="text-5xl font-bold text-blue-500 mb-3">Song2Video</h1>
          <p className="text-lg text-slate-400 font-light">AI 驱动的歌词视频生成器</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8">
          <div className="space-y-2">
            <label className="block text-sm font-semibold text-slate-300">歌曲名称</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="输入歌曲名..."
              className="w-full bg-slate-900 border border-slate-600 rounded-xl px-5 py-4 text-lg focus:ring-2 focus:ring-blue-500 outline-none text-white"
              required
            />
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-semibold text-slate-300">歌词内容</label>
            <textarea
              value={lyrics}
              onChange={(e) => setLyrics(e.target.value)}
              placeholder="粘贴歌词..."
              rows={6}
              className="w-full bg-slate-900 border border-slate-600 rounded-xl px-5 py-4 text-base focus:ring-2 focus:ring-blue-500 outline-none text-white"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-4 px-6 rounded-xl transition-colors disabled:opacity-50"
          >
            {loading ? '处理中...' : '开始创作'}
          </button>
        </form>
      </div>
    </div>
  );
}
