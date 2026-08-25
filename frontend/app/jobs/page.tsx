import { getDashboardData } from "../api";
import { AppShell, JobsPanel, Metrics } from "../components";

export default async function JobsPage() {
  const { health, sources, documents, jobs, error } = await getDashboardData();

  return (
    <AppShell
      active="/jobs"
      title="Jobs"
      subtitle={
        error ? `API unavailable: ${error}` : "Ingestion, embedding, indexing, and failures"
      }
    >
      <Metrics health={health} sources={sources} documents={documents} jobs={jobs} />
      <section className="grid">
        <JobsPanel jobs={jobs} wide />
      </section>
    </AppShell>
  );
}
