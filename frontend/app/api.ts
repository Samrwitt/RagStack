const apiBaseUrl = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

type HealthCheck = {
  name: string;
  status: string;
};

export type HealthReport = {
  status: string;
  version: string;
  checks: HealthCheck[];
};

export type Source = {
  id: string;
  name: string;
  source_type: string;
  status: string;
  document_count: number;
  last_sync_at: string | null;
  last_error: string | null;
};

export type DocumentItem = {
  id: string;
  title: string;
  source_type: string;
  current_state: string;
  updated_at: string;
};

export type Job = {
  id: string;
  job_type: string;
  status: string;
  attempt: number;
  last_error: string | null;
  created_at: string;
};

export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

export type Citation = {
  index: number;
  document_id: string;
  version_id: string;
  chunk_id: string;
  title: string;
  source_type: string;
  source_url: string | null;
  page: number | null;
  section: string | null;
};

export type ChatResponse = {
  answer: string;
  evidence_status: string;
  citations: Citation[];
  retrieval_query: string;
  context: Record<string, unknown>[];
};

export type SearchHit = {
  chunk_id: string;
  document_id: string;
  version_id: string;
  score: number;
  rank: number;
  text: string;
  title: string;
  source_type: string;
  source_url: string | null;
  page: number | null;
  section: string | null;
  metadata: Record<string, unknown>;
  scores: Record<string, number>;
};

export type SearchDebugResponse = {
  query: string;
  mode: string;
  dense_hits: SearchHit[];
  sparse_hits: SearchHit[];
  rrf_hits: SearchHit[];
  reranked_hits: SearchHit[];
  final_context: SearchHit[];
  latency_ms: Record<string, number>;
};

export type EvalRecord = {
  question: string;
  expected_answer: string;
  relevant_document_ids: string[];
};

export type EvalRun = {
  id: string;
  name: string;
  status: string;
  config: Record<string, unknown>;
  metrics: Record<string, number>;
  results: Record<string, unknown>[];
};

export type SettingsConfig = {
  reranker_enabled: boolean;
  reranker_provider: string;
  llm_provider: string;
  reranker_candidate_k: number;
  context_token_budget: number;
  min_grounding_score: number;
};

export type DashboardData = {
  health: HealthReport | null;
  sources: Source[];
  documents: DocumentItem[];
  jobs: Job[];
  error: string | null;
};

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...options?.headers
    },
    ...options
  });

  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function getDashboardData(): Promise<DashboardData> {
  try {
    const [health, sources, documents, jobs] = await Promise.all([
      apiFetch<HealthReport>("/api/v1/health"),
      apiFetch<Source[]>("/api/v1/sources"),
      apiFetch<DocumentItem[]>("/api/v1/documents"),
      apiFetch<Job[]>("/api/v1/jobs")
    ]);

    return {
      health,
      sources,
      documents,
      jobs,
      error: null
    };
  } catch (error) {
    return {
      health: null,
      sources: [],
      documents: [],
      jobs: [],
      error: error instanceof Error ? error.message : "Could not reach the API"
    };
  }
}

export async function searchDebug(payload: {
  query: string;
  mode?: "hybrid" | "dense" | "sparse";
  top_k?: number;
  rerank?: boolean;
  use_hyde?: boolean;
  expand_query?: boolean;
}): Promise<SearchDebugResponse> {
  return apiFetch<SearchDebugResponse>("/api/v1/search/debug", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
