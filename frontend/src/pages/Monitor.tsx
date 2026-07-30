import React, { useEffect, useState } from 'react';
import { Activity, Database, Server, Zap, CheckCircle2, AlertCircle, Clock } from 'lucide-react';
import { api } from '../lib/api';

export default function PipelineMonitor() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      try { setData(await api.pipelineStatus()); }
      catch { /* ignore polling errors */ }
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!data) return <div className="p-8">Đang tải dữ liệu giám sát...</div>;

  return (
    <div className="p-8 bg-[#f8fafc] min-h-screen">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
          <Activity className="text-indigo-600" /> Pipeline Monitor
        </h1>
        <div className="flex gap-2">
          <span className="flex items-center gap-1 text-xs font-bold bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full">
            <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div> SYSTEM LIVE
          </span>
        </div>
      </div>

      {/* Dãy Card trạng thái dịch vụ */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        {Object.entries(data.services).map(([key, value]: any) => (
          <div key={key} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{key}</p>
              <p className="text-sm font-bold text-slate-700 capitalize">{value}</p>
            </div>
            <CheckCircle2 size={20} className="text-emerald-500" />
          </div>
        ))}
      </div>

      {/* Sơ đồ Pipeline Flow */}
      <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-sm mb-8">
        <h3 className="font-bold text-slate-700 mb-8 flex items-center gap-2">
          <Server size={18} /> Data Ingestion Flow
        </h3>
        
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 relative">
          {data.components.map((comp: any, idx: number) => (
            <React.Fragment key={idx}>
              <div className="flex flex-col items-center z-10">
                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center shadow-lg transition-all ${
                  comp.status === 'active' ? 'bg-indigo-600 text-white scale-110' : 'bg-slate-100 text-slate-400'
                }`}>
                  {idx === 0 && <Zap size={24} />}
                  {idx === 1 && <Clock size={24} />}
                  {idx === 2 && <Database size={24} />}
                  {idx === 3 && <Activity size={24} />}
                </div>
                <p className="mt-3 font-bold text-slate-700 text-sm">{comp.name}</p>
                <p className="text-[10px] text-slate-400 font-medium uppercase">{comp.status}</p>
                <p className="text-xs font-bold text-indigo-600 mt-1">{comp.processed} items</p>
              </div>
              
              {idx < data.components.length - 1 && (
                <div className="hidden md:block flex-1 h-[2px] bg-slate-100 relative overflow-hidden min-w-[50px]">
                  {comp.status === 'active' && (
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-indigo-400 to-transparent animate-shimmer" 
                         style={{ backgroundSize: '200% 100%' }}></div>
                  )}
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Log Console giả lập */}
      <div className="bg-slate-900 rounded-xl p-4 font-mono text-xs text-emerald-400 shadow-2xl relative">
        <div className="flex items-center gap-2 mb-2 border-b border-slate-800 pb-2 text-slate-500 justify-between">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span className="ml-2">system_logs.sh</span>
          </div>
          <a href="https://ap-southeast-2.console.aws.amazon.com/cloudwatch/home?region=ap-southeast-2#dashboards/dashboard/NewsRAG-Monitor" target="_blank" rel="noreferrer" className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-sans font-bold uppercase tracking-wider text-[10px] bg-indigo-500/20 px-3 py-1 rounded-full border border-indigo-500/30 transition-all">
            Xem trên CloudWatch
          </a>
        </div>
        <div className="space-y-1 mt-3">
          <p>[{data.stats.last_run}] INFO: SQS consumer received {data.stats.total_processed || 12} messages from SQS queue</p>
          <p>[{data.stats.last_run}] INFO: ETL job completed. {data.stats.total_processed || 10} articles written to fact_articles.</p>
          <p className="text-indigo-400">[{data.stats.last_run}] SUCCESS: Vectorized chunks to pgvector database</p>
          <p className="animate-pulse">_</p>
        </div>
      </div>
    </div>
  );
}