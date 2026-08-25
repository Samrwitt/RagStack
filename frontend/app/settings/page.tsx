import { getDashboardData } from "../api";
import { AppShell, SecurityPanel, SettingsPanel } from "../components";

export default async function SettingsPage() {
  const { error } = await getDashboardData();

  return (
    <AppShell
      active="/settings"
      title="Settings"
      subtitle={error ? `API unavailable: ${error}` : "Runtime controls and guardrails"}
    >
      <section className="grid">
        <SettingsPanel wide />
        <SecurityPanel />
      </section>
    </AppShell>
  );
}
