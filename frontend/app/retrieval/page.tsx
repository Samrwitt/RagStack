import { getDashboardData } from "../api";
import { AppShell, DocumentsPanel, RetrievalPanel } from "../components";

export default async function RetrievalPage() {
  const { documents, error } = await getDashboardData();

  return (
    <AppShell
      active="/retrieval"
      title="Retrieval Debugger"
      subtitle={
        error ? `API unavailable: ${error}` : "Hybrid search, filters, reranking, and context"
      }
    >
      <section className="grid">
        <RetrievalPanel wide />
        <DocumentsPanel documents={documents} />
      </section>
    </AppShell>
  );
}
