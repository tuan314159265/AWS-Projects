export interface Source {
  id: number;
  name: string;
  url: string;
  description?: string;
  domain?: string;
}

export interface Article {
  id: number;
  title: string;
  url: string;
  source: string;
  published_date: string;
  author: string;
  snippet: string;
  content?: string;
}

export interface Stats {
  total_sources: number;
  total_articles: number;
  total_vectors: number;
  top_authors: { name: string; count: number; percent: number }[];
  source_distribution: { name: string; value: number; percent: number }[];
  trend_data: { date: string; count: number }[];
  latest_articles: { title: string; source: string; date: string }[];
}

export interface ModelInfo {
  name: string;
  model_id: string;
  provider: string;
}

export interface SearchHit {
  title: string;
  url: string;
  content: string;
  score: number;
}

export interface SearchResult {
  summary: string;
  results: SearchHit[];
  total: number;
  duration_ms: number;
}

export interface SearchResponse {
  raw_data: SearchResult;
  formatted_answer: string;
}

export interface RetrieveResult {
  title: string;
  url: string;
  score: number;
  content_snippet: string;
}

export interface ModelComparison {
  model: string;
  response: string;
}

export interface PipelineStatus {
  stage: string;
  progress: number;
  status: string;
}
