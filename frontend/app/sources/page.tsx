import { getDashboardData } from "../api";
import { AppShell, Metrics, SourcesPanel } from "../components";

export default async function SourcesPage() {
  const { health, sources, documents, jobs, error } = await getDashboardData();

  return (
    <AppShell
      active="/sources"
      title="Sources"
      subtitle={error ? `API unavailable: ${error}` : "Source connections and sync status"}
    >
      <Metrics health={health} sources={sources} documents={documents} jobs={jobs} />
      <section className="grid">
        <SourcesPanel sources={sources} wide />
      </section>
    </AppShell>
  );
}
