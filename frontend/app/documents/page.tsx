import { getDashboardData } from "../api";
import { AppShell, DocumentsPanel, Metrics } from "../components";

export default async function DocumentsPage() {
  const { health, sources, documents, jobs, error } = await getDashboardData();

  return (
    <AppShell
      active="/documents"
      title="Documents"
      subtitle={error ? `API unavailable: ${error}` : "Indexed and processing documents"}
    >
      <Metrics health={health} sources={sources} documents={documents} jobs={jobs} />
      <section className="grid">
        <DocumentsPanel documents={documents} wide />
      </section>
    </AppShell>
  );
}
