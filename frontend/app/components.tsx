import {
  Activity,
  BarChart3,
  Briefcase,
  Database,
  FileText,
  MessageSquare,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck
} from "lucide-react";
import type { ReactNode } from "react";
import type { DocumentItem, HealthReport, Job, Source } from "./api";
import { ChatClient } from "./chat-client";
import { EvaluationClient } from "./evaluation/evaluation-client";
import { RetrievalDebuggerClient } from "./retrieval/retrieval-client";
import { SettingsClient } from "./settings/settings-client";

const nav = [
  { label: "Overview", href: "/", icon: Activity },
  { label: "Sources", href: "/sources", icon: Database },
  { label: "Documents", href: "/documents", icon: FileText },
  { label: "Chat", href: "/chat", icon: MessageSquare },
  { label: "Retrieval Debugger", href: "/retrieval", icon: Search },
  { label: "Evaluation", href: "/evaluation", icon: BarChart3 },
  { label: "Jobs", href: "/jobs", icon: RefreshCw },
  { label: "Settings", href: "/settings", icon: Settings }
] as const;

export function AppShell({
  active,
  title,
  subtitle,
  children
}: {
  active: string;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <main className="shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          <Briefcase size={22} />
          <strong>CorpusForge</strong>
        </a>
        <nav>
          {nav.map(({ label, href, icon: Icon }) => (
            <a className={active === href ? "active" : ""} href={href} key={href}>
              <Icon size={18} />
              <span>{label}</span>
            </a>
          ))}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          <a className="iconButton" aria-label="Refresh" href={active}>
            <RefreshCw size={18} />
          </a>
        </header>
        {children}
      </section>
    </main>
  );
}

export function Metrics({
  health,
  sources,
  documents,
  jobs
}: {
  health: HealthReport | null;
  sources: Source[];
  documents: DocumentItem[];
  jobs: Job[];
}) {
  const activeJobs = countActiveJobs(jobs);
  const indexedDocuments = countIndexedDocuments(documents);
  const connectedSources = countConnectedSources(sources);

  return (
    <section className="metrics">
      <Metric
        label="Indexed documents"
        value={indexedDocuments.toLocaleString()}
        delta={`${documents.length.toLocaleString()} total`}
      />
      <Metric
        label="Connected sources"
        value={connectedSources.toLocaleString()}
        delta={`${sources.length.toLocaleString()} configured`}
      />
      <Metric
        label="Active jobs"
        value={activeJobs.toLocaleString()}
        delta={`${jobs.length.toLocaleString()} total`}
      />
      <Metric
        label="API health"
        value={health?.status ?? "offline"}
        delta={health?.version ? `v${health.version}` : "waiting for backend"}
      />
    </section>
  );
}

export function SourcesPanel({ sources, wide = false }: { sources: Source[]; wide?: boolean }) {
  return (
    <div className={wide ? "panel wide" : "panel"}>
      <PanelTitle title="Sources" />
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Status</th>
            <th>Volume</th>
            <th>Last sync</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => (
            <tr key={source.id}>
              <td>{source.name}</td>
              <td>{formatSourceType(source.source_type)}</td>
              <td className={source.status}>{formatState(source.status)}</td>
              <td>{source.document_count.toLocaleString()} docs</td>
              <td>{formatDate(source.last_sync_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {sources.length === 0 ? <EmptyState text="No sources returned by the API yet." /> : null}
    </div>
  );
}

export function DocumentsPanel({
  documents,
  wide = false,
  limit
}: {
  documents: DocumentItem[];
  wide?: boolean;
  limit?: number;
}) {
  const visibleDocuments = typeof limit === "number" ? documents.slice(0, limit) : documents;

  return (
    <div className={wide ? "panel wide" : "panel"}>
      <PanelTitle title="Documents" />
      <div className="documents">
        {visibleDocuments.map((document) => (
          <DocumentRow
            key={document.id}
            title={document.title}
            state={formatState(document.current_state)}
            source={formatSourceType(document.source_type)}
          />
        ))}
        {documents.length === 0 ? <EmptyState text="Upload or sync documents to populate this list." /> : null}
      </div>
    </div>
  );
}

export function ChatPanel({ wide = false }: { wide?: boolean }) {
  return (
    <div className={wide ? "panel wide" : "panel"}>
      <PanelTitle title="Chat" />
      <ChatClient />
    </div>
  );
}

export function RetrievalPanel({ wide = false }: { wide?: boolean }) {
  return (
    <div className={wide ? "panel wide" : "panel"}>
      <PanelTitle title="Retrieval Debugger" />
      <RetrievalDebuggerClient />
    </div>
  );
}

export function EvaluationPanel({
  health,
  sources,
  documents,
  wide = false
}: {
  health: HealthReport | null;
  sources: Source[];
  documents: DocumentItem[];
  wide?: boolean;
}) {
  return (
    <div className={wide ? "panel wide" : "panel"}>
      <PanelTitle title="Evaluation" />
      <EvaluationClient />
    </div>
  );
}

export function JobsPanel({ jobs, wide = false }: { jobs: Job[]; wide?: boolean }) {
  const failedJobs = jobs.filter((job) => job.status === "failed").length;

  return (
    <div className={wide ? "panel wide" : "panel"}>
      <PanelTitle title="Jobs" />
      <div className="jobs">
        <span>Queued or running</span>
        <strong>{countActiveJobs(jobs)}</strong>
        <span>Failed</span>
        <strong>{failedJobs}</strong>
        <span>Latest</span>
        <strong>{formatJobStatus(jobs[0])}</strong>
      </div>
      {wide && jobs.length > 0 ? (
        <table className="stackedTable">
          <thead>
            <tr>
              <th>Type</th>
              <th>Status</th>
              <th>Attempt</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{formatState(job.job_type)}</td>
                <td className={job.status}>{formatState(job.status)}</td>
                <td>{job.attempt}</td>
                <td>{formatDate(job.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {jobs.length === 0 ? <EmptyState text="No jobs returned by the API yet." /> : null}
    </div>
  );
}

export function SettingsPanel({ wide = false }: { wide?: boolean }) {
  return (
    <div className={wide ? "panel wide" : "panel"}>
      <PanelTitle title="Settings" />
      <SettingsClient />
    </div>
  );
}

export function SecurityPanel() {
  return (
    <div className="panel security">
      <ShieldCheck size={20} />
      <span>RBAC, ACL filters, rate limits, SSRF checks, and DLQ replay are enabled.</span>
    </div>
  );
}

function Metric({ label, value, delta }: { label: string; value: string; delta: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{delta}</small>
    </div>
  );
}

function PanelTitle({ title }: { title: string }) {
  return (
    <div className="panelTitle">
      <h2>{title}</h2>
    </div>
  );
}

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span>{label}</span>
      <div className="bar">
        <i style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function DocumentRow({ title, state, source }: { title: string; state: string; source: string }) {
  return (
    <div className="documentRow">
      <FileText size={17} />
      <strong>{title}</strong>
      <span>{source}</span>
      <em>{state}</em>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="emptyState">{text}</p>;
}

function formatState(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatSourceType(value: string) {
  return formatState(value);
}

function formatDate(value: string | null) {
  if (!value) {
    return "Never";
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

function percentage(value: number, total: number) {
  if (total === 0) {
    return 0;
  }

  return Math.round((value / total) * 100);
}

function healthPercentage(health: HealthReport | null) {
  if (!health || health.checks.length === 0) {
    return 0;
  }

  return percentage(
    health.checks.filter((check) => check.status === "ok").length,
    health.checks.length
  );
}

function formatJobStatus(job: Job | undefined) {
  if (!job) {
    return "None";
  }

  return formatState(job.status);
}

function countActiveJobs(jobs: Job[]) {
  return jobs.filter((job) => ["queued", "running", "retrying"].includes(job.status)).length;
}

function countIndexedDocuments(documents: DocumentItem[]) {
  return documents.filter((document) => document.current_state === "indexed").length;
}

function countConnectedSources(sources: Source[]) {
  return sources.filter((source) => source.status === "connected").length;
}
