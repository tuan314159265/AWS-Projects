import React, { useEffect, useState } from 'react';
import { Activity, Database, Server, Zap, Globe, Cloud, Cpu, ArrowRight, Search, Layers, FileText, Users, Bot, ExternalLink } from 'lucide-react';
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

  const services = data.services || {};
  const stats = data.stats || {};
  const steps = data.pipeline_steps || [];
  const components = data.components || [];

  return (
    <div className="p-8 bg-[#f8fafc] min-h-screen">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
          <Activity className="text-indigo-600" /> Architecture & Monitor
        </h1>
        <div className="flex gap-2">
          <span className="flex items-center gap-1 text-xs font-bold bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full">
            <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div> LIVE
          </span>
        </div>
      </div>

      {/* Service Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {Object.entries(services).map(([key, value]: any) => (
          <div key={key} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{key.replace(/_/g, ' ')}</p>
              <p className="text-sm font-bold text-slate-700 capitalize">{value}</p>
            </div>
            <div className={`p-2 rounded-lg ${value === 'connected' || value === 'active' ? 'bg-emerald-100' : 'bg-slate-100'}`}>
              {value === 'connected' || value === 'active' || value === 'running'
                ? <CheckCircle size={16} className="text-emerald-600" />
                : <AlertCircle size={16} className="text-amber-500" />}
            </div>
          </div>
        ))}
      </div>

      {/* Architecture Flow Diagram */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm mb-8 overflow-x-auto">
        <h3 className="font-bold text-slate-700 mb-6 flex items-center gap-2">
          <Server size={18} /> System Architecture
        </h3>

        <div className="min-w-[900px]">
          {/* INGESTION LANE */}
          <div className="mb-10">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-orange-500"></span> Data Ingestion Pipeline
            </div>
            <div className="flex items-center gap-0">
              <Node icon={<Globe size={20} />} label="News Sites" sub="Báo chí" color="orange" active />
              <ArrowRight size={20} className="text-slate-300 mx-2 shrink-0" />
              <Node icon={<Cpu size={20} />} label="Crawler" sub="Scrapy + Newspaper3k" color="indigo" active />
              <ArrowRight size={20} className="text-slate-300 mx-2 shrink-0" />
              <Node icon={<Layers size={20} />} label="SQS Queue" sub="newsrag-raw-news" color="amber" active />
              <ArrowRight size={20} className="text-slate-300 mx-2 shrink-0" />
              <Node icon={<Users size={20} />} label="Consumer" sub="Kafka → PostgreSQL" color="blue" active />
              <ArrowRight size={20} className="text-slate-300 mx-2 shrink-0" />
              <Node icon={<Database size={20} />} label="RDS Aurora" sub="PostgreSQL 15.4" color="emerald" active />
              <ArrowRight size={20} className="text-slate-300 mx-2 shrink-0" />
              <Node icon={<Bot size={20} />} label="ETL + Vectorize" sub="Bedrock Titan Embed → pgvector" color="violet" active />
              <ArrowRight size={20} className="text-slate-300 mx-2 shrink-0" />
              <Node icon={<Cloud size={20} />} label="pgvector" sub="PostgreSQL" color="cyan" active />
            </div>
          </div>

          {/* QUERY LANE */}
          <div className="mb-6">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-indigo-500"></span> Query Pipeline
            </div>
            <div className="flex items-center gap-0">
              <Node icon={<Globe size={20} />} label="Browser" sub="S3 + CloudFront" color="sky" active />
              <ArrowRight size={20} className="text-slate-300 mx-2 shrink-0" />
              <Node icon={<Server size={20} />} label="ALB" sub="newsrag-api-alb" color="slate" active />
              <ArrowRight size={20} className="text-slate-300 mx-2 shrink-0" />
              <Node icon={<Zap size={20} />} label="FastAPI" sub="ECS Fargate" color="indigo" active />
              <ArrowRight size={20} className="text-slate-300 mx-2 shrink-0" />
              <Node icon={<Search size={20} />} label="Retriever" sub="pgvector + Bedrock Rerank" color="violet" active />
              <ArrowRight size={20} className="text-slate-300 mx-2 shrink-0" />
              <Node icon={<FileText size={20} />} label="Generator" sub="Groq / Bedrock / NVIDIA" color="fuchsia" active />
              <ArrowRight size={20} className="text-slate-300 mx-2 shrink-0" />
              <Node icon={<Activity size={20} />} label="Response" sub="Streaming / JSON" color="emerald" active />
            </div>
          </div>
        </div>

        {/* AWS Services Legend */}
        <div className="mt-6 pt-4 border-t border-slate-100 flex flex-wrap gap-3">
          {[
            { label: 'ECS Fargate', desc: 'Pipeline runner + API' },
            { label: 'RDS Aurora', desc: 'Data Warehouse' },
            { label: 'SQS', desc: 'Message queue' },
            { label: 'ECR', desc: 'Docker registry' },
            { label: 'EventBridge', desc: 'Scheduler (3 tasks/day)' },
            { label: 'CloudWatch', desc: 'Monitoring & alerts' },
            { label: 'Bedrock', desc: 'LLM + Embedding' },
            { label: 'S3 + CloudFront', desc: 'Frontend hosting' },
          ].map((svc, i) => (
            <span key={i} className="text-[10px] text-slate-500 bg-slate-50 px-2 py-1 rounded-md border border-slate-200">
              <strong className="text-slate-700">{svc.label}</strong> — {svc.desc}
            </span>
          ))}
        </div>
      </div>

      {/* Pipeline Steps + Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Pipeline Steps */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm lg:col-span-2">
          <h3 className="font-bold text-slate-700 mb-4 flex items-center gap-2">
            <Layers size={16} /> ETL Pipeline Steps
          </h3>
          <div className="space-y-2">
            {steps.map((step: any) => (
              <div key={step.id} className="flex items-center gap-3 text-xs">
                <div className={`w-2 h-2 rounded-full ${step.type === 'db' ? 'bg-emerald-500' : step.type === 'transform' ? 'bg-indigo-500' : 'bg-amber-500'}`} />
                <span className="text-slate-600 w-16 uppercase tracking-wider font-bold">{step.type}</span>
                <span className="text-slate-800">{step.name}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Stats */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="font-bold text-slate-700 mb-4 flex items-center gap-2">
            <Database size={16} /> Current Stats
          </h3>
          <div className="space-y-4">
            {[
              { label: 'Articles', value: stats.total_processed ?? data?.stats?.total_articles ?? '-' },
              { label: 'Vectors', value: '-', note: '(check /monitor/metrics)' },
              { label: 'Last Run', value: stats.last_run ?? '-' },
            ].map((s) => (
              <div key={s.label} className="flex justify-between text-sm">
                <span className="text-slate-500">{s.label}</span>
                <span className="font-bold text-slate-800">{s.value}{s.note && <span className="text-[10px] text-slate-400 ml-1">{s.note}</span>}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* CloudWatch Link + Log Console */}
      <div className="bg-slate-900 rounded-xl p-4 font-mono text-xs text-emerald-400 shadow-2xl relative">
        <div className="flex items-center gap-2 mb-2 border-b border-slate-800 pb-2 text-slate-500 justify-between">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span className="ml-2">cloudwatch.log</span>
          </div>
          <div className="flex gap-2">
            <a href="https://ap-southeast-2.console.aws.amazon.com/cloudwatch/home?region=ap-southeast-2#dashboards/dashboard/NewsRAG-Monitor" target="_blank" rel="noreferrer"
              className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-sans font-bold uppercase tracking-wider text-[10px] bg-indigo-500/20 px-3 py-1 rounded-full border border-indigo-500/30 transition-all">
              <ExternalLink size={10} /> Dashboard
            </a>
            <a href="https://ap-southeast-2.console.aws.amazon.com/ecs/home?region=ap-southeast-2#/clusters/newsrag-cluster/services" target="_blank" rel="noreferrer"
              className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-sans font-bold uppercase tracking-wider text-[10px] bg-emerald-500/20 px-3 py-1 rounded-full border border-emerald-500/30 transition-all">
              <ExternalLink size={10} /> ECS
            </a>
          </div>
        </div>
        <div className="space-y-1 mt-3">
          <p className="text-slate-400"># Pipeline run @ {stats.last_run || 'N/A'}</p>
          {components.map((c: any) => (
            <p key={c.name}>
              [{stats.last_run || 'N/A'}] {c.status === 'active' ? 'INFO' : 'IDLE'}: {c.name} — {c.processed} items processed
            </p>
          ))}
          <p className="text-indigo-400">[OK] API server running on ECS Fargate (uvicorn :8000)</p>
          <p className="animate-pulse">_</p>
        </div>
      </div>
    </div>
  );
}

// --- Helper Components ---

function CheckCircle({ size, className }: { size: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className={className}>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

function AlertCircle({ size, className }: { size: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className={className}>
      <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

function Node({ icon, label, sub, color, active }: {
  icon: React.ReactNode; label: string; sub: string; color: string; active: boolean;
}) {
  const colorMap: Record<string, string> = {
    orange: 'bg-orange-100 text-orange-700 border-orange-200',
    indigo: 'bg-indigo-100 text-indigo-700 border-indigo-200',
    amber: 'bg-amber-100 text-amber-700 border-amber-200',
    blue: 'bg-blue-100 text-blue-700 border-blue-200',
    emerald: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    violet: 'bg-violet-100 text-violet-700 border-violet-200',
    cyan: 'bg-cyan-100 text-cyan-700 border-cyan-200',
    sky: 'bg-sky-100 text-sky-700 border-sky-200',
    slate: 'bg-slate-100 text-slate-700 border-slate-200',
    fuchsia: 'bg-fuchsia-100 text-fuchsia-700 border-fuchsia-200',
  };
  return (
    <div className={`flex flex-col items-center min-w-[90px] p-2 rounded-xl border ${active ? colorMap[color] || colorMap.indigo : 'bg-slate-50 text-slate-300 border-slate-100'} transition-all`}>
      <div className="mb-1">{icon}</div>
      <p className="font-bold text-[10px] leading-tight text-center">{label}</p>
      <p className="text-[8px] text-center opacity-70">{sub}</p>
    </div>
  );
}