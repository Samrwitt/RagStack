import { getDashboardData } from "../api";
import { AppShell, EvaluationPanel, Metrics } from "../components";

export default async function EvaluationPage() {
  const { health, sources, documents, jobs, error } = await getDashboardData();

  return (
    <AppShell
      active="/evaluation"
      title="Evaluation"
      subtitle={error ? `API unavailable: ${error}` : "Retrieval and grounding quality signals"}
    >
      <Metrics health={health} sources={sources} documents={documents} jobs={jobs} />
      <section className="grid">
        <EvaluationPanel health={health} sources={sources} documents={documents} wide />
      </section>
    </AppShell>
  );
}
