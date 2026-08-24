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

const nav = [
  ["Overview", Activity],
  ["Sources", Database],
  ["Documents", FileText],
  ["Chat", MessageSquare],
  ["Retrieval Debugger", Search],
  ["Evaluation", BarChart3],
  ["Jobs", RefreshCw],
  ["Settings", Settings]
] as const;

const sources = [
  ["Website", "Connected", "184 docs", "3 min ago"],
  ["GitHub", "Syncing", "612 docs", "running"],
  ["PostgreSQL", "Connected", "48 rows", "21 min ago"],
  ["REST API", "Warning", "93 records", "retry queued"],
  ["Google Drive", "Connected", "1,204 files", "8 min ago"]
];

export default function Dashboard() {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Briefcase size={22} />
          <strong>CorpusForge</strong>
        </div>
        <nav>
          {nav.map(([label, Icon]) => (
            <a className={label === "Overview" ? "active" : ""} href={`#${label}`} key={label}>
              <Icon size={18} />
              <span>{label}</span>
            </a>
          ))}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>Overview</h1>
            <p>Acme Knowledge workspace</p>
          </div>
          <button className="iconButton" aria-label="Refresh">
            <RefreshCw size={18} />
          </button>
        </header>

        <section className="metrics">
          <Metric label="Indexed documents" value="2,141" delta="+86 today" />
          <Metric label="Retrieval p95" value="682 ms" delta="-44 ms" />
          <Metric label="Groundedness" value="91.8%" delta="+2.1%" />
          <Metric label="Failed jobs" value="7" delta="3 replayable" />
        </section>

        <section className="grid">
          <div className="panel wide" id="Sources">
            <PanelTitle title="Sources" />
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Volume</th>
                  <th>Last sync</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((row) => (
                  <tr key={row[0]}>
                    {row.map((cell, index) => (
                      <td key={cell} className={index === 1 ? cell.toLowerCase() : ""}>
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="panel" id="Chat">
            <PanelTitle title="Chat" />
            <div className="chat">
              <p className="question">How many annual leave days do employees receive?</p>
              <p className="answer">Employees receive 22 annual leave days. [1]</p>
              <span className="citation">[1] Handbook, Leave, page 3</span>
            </div>
          </div>

          <div className="panel" id="Retrieval Debugger">
            <PanelTitle title="Retrieval Debugger" />
            <ol className="trace">
              <li>Query rewrite: annual leave entitlement</li>
              <li>Filters: org, workspace, current version, ACL</li>
              <li>Hybrid: dense 50 + BM25 50</li>
              <li>Rerank: 50 to 8</li>
            </ol>
          </div>

          <div className="panel" id="Evaluation">
            <PanelTitle title="Evaluation" />
            <div className="bars">
              <Bar label="Recall@10" value={91} />
              <Bar label="MRR" value={80} />
              <Bar label="Citations" value={88} />
            </div>
          </div>

          <div className="panel" id="Jobs">
            <PanelTitle title="Jobs" />
            <div className="jobs">
              <span>Embedding queue</span>
              <strong>12</strong>
              <span>DLQ</span>
              <strong>7</strong>
              <span>Workers</span>
              <strong>4 online</strong>
            </div>
          </div>

          <div className="panel" id="Settings">
            <PanelTitle title="Settings" />
            <div className="settings">
              <label>
                <input type="checkbox" defaultChecked />
                Reranking
              </label>
              <label>
                <input type="checkbox" defaultChecked />
                ACL enforcement
              </label>
              <label>
                <input type="checkbox" defaultChecked />
                Rate limiting
              </label>
            </div>
          </div>

          <div className="panel wide" id="Documents">
            <PanelTitle title="Documents" />
            <div className="documents">
              <DocumentRow title="Employee Handbook" state="Indexed" source="Google Drive" />
              <DocumentRow title="On-call Runbook" state="Indexed" source="GitHub" />
              <DocumentRow title="Benefits API" state="Chunked" source="REST API" />
            </div>
          </div>

          <div className="panel security">
            <ShieldCheck size={20} />
            <span>RBAC, ACL filters, rate limits, SSRF checks, and DLQ replay are enabled.</span>
          </div>
        </section>
      </section>
    </main>
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
