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

export type Document = {
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

export type DashboardData = {
  health: HealthReport | null;
  sources: Source[];
  documents: Document[];
  jobs: Job[];
  error: string | null;
};

async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    cache: "no-store",
    headers: {
      Accept: "application/json"
    }
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
      apiFetch<Document[]>("/api/v1/documents"),
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
