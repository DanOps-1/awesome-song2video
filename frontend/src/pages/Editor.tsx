import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { mixService, type MixLine } from '../services/api'; // 加了 type
import clsx from 'clsx';

export default function Editor() {
  const { id } = useParams<{ id: string }>();
  const [lines, setLines] = useState<MixLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);
  const [renderJobId, setRenderJobId] = useState<string | null>(null);
  const [renderStatus, setRenderStatus] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'preview' | 'search'>('preview');

  useEffect(() => {
    if (id) {
      loadTimeline();
    }
  }, [id]);

  useEffect(() => {
    let interval: any;
    if (loading && id) {
      interval = setInterval(loadTimeline, 3000);
    }
    return () => clearInterval(interval);
  }, [loading, id]);

  useEffect(() => {
    let interval: any;
    if (renderJobId && id && renderStatus !== 'completed' && renderStatus !== 'failed') {
      interval = setInterval(async () => {
        try {
          const status = await mixService.getRenderStatus(id, renderJobId);
          setRenderStatus(status.status);
        } catch (e) {
          console.error(e);
        }
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [renderJobId, renderStatus, id]);

  const loadTimeline = async () => {
    if (!id) return;
    try {
      const data = await mixService.getLines(id);
      if (data && data.length > 0) {
        setLines(data);
        setLoading(false);
      }
    } catch (error) {
      console.error('Loading timeline failed:', error);
    }
  };

  const handleRender = async () => {
    if (!id) return;
    try {
      const res = await mixService.startRender(id);
      setRenderJobId(res.job_id);
      setRenderStatus('queued');
    } catch (e) {
      console.error(e);
      alert('提交渲染失败');
    }
  };

  const selectedLine = lines.find(l => l.id === selectedLineId);

  return (
    <div className="h-screen bg-black text-slate-200 flex flex-col overflow-hidden font-sans">
      {/* Header */}
      <header className="h-16 border-b border-slate-800 bg-slate-900 flex items-center justify-between px-6">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-white">
            Song2Video <span className="font-light text-slate-500">| 工作台</span>
          </h1>
        </div>
        
        <div className="flex items-center gap-6">
           {renderStatus && (
              <div className="flex items-center gap-3 bg-slate-800 px-4 py-1.5 rounded-full">
                <span className="text-xs text-slate-400 uppercase font-bold">状态: {renderStatus}</span>
              </div>
           )}
           
           <button 
             onClick={handleRender}
             disabled={!!renderJobId && renderStatus !== 'completed' && renderStatus !== 'failed'}
             className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-lg text-sm font-bold"
           >
             {renderStatus === 'completed' ? '重新渲染' : '导出视频'}
           </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex overflow-hidden relative">
        
        {/* Left Sidebar: Timeline */}
        <div className="w-80 border-r border-slate-800 flex flex-col bg-slate-900">
          <div className="p-4 border-b border-slate-800">
            <h2 className="text-xs font-bold text-slate-500 uppercase">时间轴序列</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {loading ? (
              <div className="flex flex-col items-center justify-center h-64 gap-4 text-slate-500">
                <span className="text-sm">生成中...</span>
              </div>
            ) : (
              lines.map((line) => (
                <div
                  key={line.id}
                  onClick={() => setSelectedLineId(line.id)}
                  className={clsx(
                    "group p-3 rounded-xl border transition-all cursor-pointer relative",
                    selectedLineId === line.id
                      ? "bg-blue-900/20 border-blue-500"
                      : "bg-slate-800 border-transparent hover:bg-slate-700"
                  )}
                >
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-[10px] font-mono text-slate-500 bg-black/30 px-1.5 py-0.5 rounded">
                      {(line.start_time).toFixed(1)}s - {(line.end_time).toFixed(1)}s
                    </span>
                    <span className={clsx("text-xs", line.clip_id ? "text-green-500" : "text-yellow-500")}>
                       {line.clip_id ? "●" : "○"}
                    </span>
                  </div>
                  <p className={clsx("text-sm font-medium leading-relaxed", 
                    selectedLineId === line.id ? "text-white" : "text-slate-400"
                  )}>{line.text}</p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Center: Preview & Edit */}
        <div className="flex-1 bg-black flex flex-col items-center justify-center p-8 relative">
          {selectedLine ? (
            <div className="w-full max-w-4xl space-y-8">
              
              <div className="aspect-video bg-slate-900 rounded-2xl overflow-hidden border border-slate-800 relative group flex items-center justify-center">
                 <p className="text-slate-500">PREVIEW: {selectedLine.clip_source || "等待匹配..."}</p>
              </div>

              <div className="bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden">
                <div className="flex border-b border-slate-800">
                   <button 
                     onClick={() => setActiveTab('preview')}
                     className={clsx("flex-1 py-3 text-sm font-medium transition-colors", activeTab === 'preview' ? "bg-slate-800 text-white" : "text-slate-500 hover:text-slate-300")}
                   >
                     当前素材
                   </button>
                   <button 
                     onClick={() => setActiveTab('search')}
                     className={clsx("flex-1 py-3 text-sm font-medium transition-colors", activeTab === 'search' ? "bg-slate-800 text-white" : "text-slate-500 hover:text-slate-300")}
                   >
                     搜索替换
                   </button>
                </div>
                
                <div className="p-6">
                   {activeTab === 'search' ? (
                     <div className="flex gap-3">
                       <input 
                           type="text" 
                           placeholder="搜索视频..." 
                           className="w-full bg-black border border-slate-700 rounded-xl pl-4 pr-4 py-3 text-sm focus:border-blue-500 outline-none text-white"
                         />
                       <button className="bg-blue-600 hover:bg-blue-500 text-white px-6 rounded-xl text-sm font-medium">
                         搜索
                       </button>
                     </div>
                   ) : (
                     <div className="flex items-center justify-between">
                       <div className="text-sm text-slate-400">
                         当前匹配来源: <span className="text-blue-400 font-mono ml-2">{selectedLine.clip_source || "自动匹配中..."}</span>
                       </div>
                       <button className="text-xs text-slate-400 hover:text-white transition-colors bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700">
                         重新匹配
                       </button>
                     </div>
                   )}
                </div>
              </div>

            </div>
          ) : (
            <div className="text-slate-700 text-center">
              <p className="text-lg font-light">请选择左侧歌词行</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
