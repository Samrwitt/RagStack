import { getDashboardData } from "../api";
import { AppShell, ChatPanel, DocumentsPanel } from "../components";

export default async function ChatPage() {
  const { documents, error } = await getDashboardData();

  return (
    <AppShell
      active="/chat"
      title="Chat"
      subtitle={error ? `API unavailable: ${error}` : "Grounded answers with citations"}
    >
      <section className="grid">
        <ChatPanel wide />
        <DocumentsPanel documents={documents} />
      </section>
    </AppShell>
  );
}
