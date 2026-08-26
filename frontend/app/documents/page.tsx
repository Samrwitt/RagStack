import { getDashboardData } from "../api";
import { AppShell, Metrics } from "../components";
import { DocumentsClient } from "./documents-client";

export default async function DocumentsPage() {
  const { health, sources, documents, jobs, error } = await getDashboardData();

  return (
    <AppShell
      active="/documents"
      title="Documents"
      subtitle={error ? `API unavailable: ${error}` : "Upload and inspect ingested documents"}
    >
      <Metrics health={health} sources={sources} documents={documents} jobs={jobs} />
      <section className="grid">
        <DocumentsClient initialDocuments={documents} />
      </section>
    </AppShell>
  );
}
