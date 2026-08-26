import { getDashboardData } from "../api";
import { AppShell, Metrics } from "../components";
import { SourcesClient } from "./sources-client";

export default async function SourcesPage() {
  const { health, sources, documents, jobs, error } = await getDashboardData();

  return (
    <AppShell
      active="/sources"
      title="Sources"
      subtitle={error ? `API unavailable: ${error}` : "Import and manage research papers & code repositories"}
    >
      <Metrics health={health} sources={sources} documents={documents} jobs={jobs} />
      <section className="grid">
        <SourcesClient initialSources={sources} />
      </section>
    </AppShell>
  );
}
