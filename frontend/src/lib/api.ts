import { Stats, Article, Source, ModelInfo, SearchResponse, SearchHit } from './types';

const BASE_URL = import.meta.env.VITE_API_URL || '';

class ApiError extends Error {
  code: number;
  constructor(msg: string, code: number) {
    super(msg);
    this.code = code;
  }
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(text || `HTTP ${res.status}`, res.status);
  }
  return res.json();
}

// ---- Hooks ----

import { useState, useEffect } from 'react';

export function useApi<T>(path: string, opts?: RequestInit) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = () => {
    setLoading(true);
    setError(null);
    request<T>(path, opts)
      .then(setData)
      .catch((e) => setError(e.message || 'Lỗi kết nối'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [path]);

  return { data, loading, error, refetch: fetchData };
}

// ---- API methods ----

export const api = {
  stats: ()        => request<Stats>('/stats'),
  sources: ()      => request<Source[]>('/sources'),
  models: ()       => request<{ models: ModelInfo[] }>('/models'),
  articles: (q?: string, limit = 50, offset = 0) =>
    request<Article[]>(`/articles?limit=${limit}&offset=${offset}${q ? `&q=${encodeURIComponent(q)}` : ''}`),
  search: (query: string, model = 'default') =>
    request<SearchResponse>('/search', {
      method: 'POST',
      body: JSON.stringify({ query, model }),
    }),
  retrieve: (query: string) =>
    request<{ results: SearchHit[]; total_found: number }>('/search/retrieve', {
      method: 'POST',
      body: JSON.stringify({ query }),
    }),
  compare: (query: string, model = 'default') =>
    request<{ model_responses: { model: string; response: string }[]; context_documents: number }>('/search/compare', {
      method: 'POST',
      body: JSON.stringify({ query, model }),
    }),
  pipelineStatus: () => request('/pipeline/status'),
  monitorMetrics: () => request('/monitor/metrics'),
};

export { request, ApiError };
