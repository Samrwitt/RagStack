import { getDashboardData } from "./api";
import {
  AppShell,
  ChatPanel,
  DocumentsPanel,
  EvaluationPanel,
  JobsPanel,
  Metrics,
  RetrievalPanel,
  SecurityPanel,
  SettingsPanel,
  SourcesPanel
} from "./components";

export default async function Dashboard() {
  const { health, sources, documents, jobs, error } = await getDashboardData();

  return (
    <AppShell
      active="/"
      title="Overview"
      subtitle={error ? `API unavailable: ${error}` : "Acme Knowledge workspace"}
    >
      <Metrics health={health} sources={sources} documents={documents} jobs={jobs} />

      <section className="grid">
        <SourcesPanel sources={sources} wide />
        <ChatPanel />
        <RetrievalPanel />
        <EvaluationPanel health={health} sources={sources} documents={documents} />
        <JobsPanel jobs={jobs} />
        <SettingsPanel />
        <DocumentsPanel documents={documents} wide limit={6} />
        <SecurityPanel />
      </section>
    </AppShell>
  );
}
