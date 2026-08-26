"use client";

import { useState } from "react";
import { BookOpen, Github, RefreshCw, CheckCircle2, AlertCircle, Plus, Globe } from "lucide-react";
import type { Source } from "../api";

export function SourcesClient({ initialSources }: { initialSources: Source[] }) {
  const [sources, setSources] = useState<Source[]>(initialSources);
  const [activeTab, setActiveTab] = useState<"arxiv" | "github">("arxiv");

  // arXiv Form State
  const [arxivQuery, setArxivQuery] = useState("");
  const [arxivName, setArxivName] = useState("");

  // GitHub Form State
  const [githubRepo, setGithubRepo] = useState("");
  const [githubBranch, setGithubBranch] = useState("main");
  const [githubToken, setGithubToken] = useState("");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleImportArxiv = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!arxivQuery.trim()) return;

    setIsSubmitting(true);
    setStatusMessage(null);

    const apiBase = typeof window !== "undefined" ? "http://localhost:8000" : "";
    const sourceName = arxivName.trim() || `arXiv: ${arxivQuery.trim()}`;

    try {
      // 1. Create arXiv source connection
      const createRes = await fetch(`${apiBase}/api/v1/sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: sourceName,
          source_type: "arxiv",
          config: {
            paper_url: arxivQuery.trim(),
            arxiv_id: arxivQuery.trim(),
            search_query: arxivQuery.includes(" ") || arxivQuery.includes(":") ? arxivQuery.trim() : undefined,
          },
        }),
      });

      if (!createRes.ok) {
        const err = await createRes.json().catch(() => null);
        throw new Error(err?.detail || `Failed creating source (${createRes.status})`);
      }

      const newSource = await createRes.json();

      // 2. Trigger immediate sync
      const syncRes = await fetch(`${apiBase}/api/v1/sources/${newSource.id}/sync`, {
        method: "POST",
      });

      if (!syncRes.ok) {
        throw new Error("Created source but failed triggering initial paper sync");
      }

      setStatusMessage({
        type: "success",
        text: `Successfully connected "${sourceName}"! Paper download & indexing job enqueued.`,
      });

      setArxivQuery("");
      setArxivName("");
      refreshSources();
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed importing arXiv paper",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleImportGithub = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!githubRepo.trim()) return;

    setIsSubmitting(true);
    setStatusMessage(null);

    const apiBase = typeof window !== "undefined" ? "http://localhost:8000" : "";
    let repoPath = githubRepo.trim();
    if (repoPath.includes("github.com/")) {
      repoPath = repoPath.split("github.com/")[1].replace(/\.git$/, "");
    }
    const [owner, repo] = repoPath.split("/");

    if (!owner || !repo) {
      setStatusMessage({
        type: "error",
        text: "Please enter a valid GitHub repository in owner/repo format (e.g. huggingface/transformers)",
      });
      setIsSubmitting(false);
      return;
    }

    try {
      const createRes = await fetch(`${apiBase}/api/v1/sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: `GitHub: ${owner}/${repo}`,
          source_type: "github",
          config: {
            owner,
            repo,
            branch: githubBranch.trim() || "main",
            access_token: githubToken.trim() || undefined,
          },
        }),
      });

      if (!createRes.ok) {
        const err = await createRes.json().catch(() => null);
        throw new Error(err?.detail || `Failed creating GitHub source (${createRes.status})`);
      }

      const newSource = await createRes.json();

      // Trigger sync
      await fetch(`${apiBase}/api/v1/sources/${newSource.id}/sync`, { method: "POST" });

      setStatusMessage({
        type: "success",
        text: `Successfully connected GitHub repository "${owner}/${repo}"! Sync job enqueued.`,
      });

      setGithubRepo("");
      refreshSources();
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed connecting GitHub repository",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const syncSourceNow = async (sourceId: string) => {
    const apiBase = typeof window !== "undefined" ? "http://localhost:8000" : "";
    try {
      const res = await fetch(`${apiBase}/api/v1/sources/${sourceId}/sync`, { method: "POST" });
      if (res.ok) {
        setStatusMessage({ type: "success", text: "Sync job enqueued!" });
        refreshSources();
      }
    } catch {
      setStatusMessage({ type: "error", text: "Failed triggering sync" });
    }
  };

  const refreshSources = async () => {
    const apiBase = typeof window !== "undefined" ? "http://localhost:8000" : "";
    try {
      const res = await fetch(`${apiBase}/api/v1/sources`);
      if (res.ok) {
        const data = await res.json();
        setSources(data);
      }
    } catch {
      // Keep existing list
    }
  };

  return (
    <>
      {/* Importer Section */}
      <div className="panel" style={{ gridColumn: "span 3", minHeight: "auto", marginBottom: "14px" }}>
        <div className="panelTitle">
          <h2>Import Research Sources</h2>
          <div style={{ display: "flex", gap: "6px" }}>
            <button
              type="button"
              className={`tab ${activeTab === "arxiv" ? "active" : ""}`}
              onClick={() => setActiveTab("arxiv")}
            >
              <BookOpen size={14} style={{ display: "inline", marginRight: "4px" }} /> arXiv Papers
            </button>
            <button
              type="button"
              className={`tab ${activeTab === "github" ? "active" : ""}`}
              onClick={() => setActiveTab("github")}
            >
              <Github size={14} style={{ display: "inline", marginRight: "4px" }} /> GitHub Repos
            </button>
          </div>
        </div>

        {activeTab === "arxiv" ? (
          <form onSubmit={handleImportArxiv} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <p style={{ fontSize: "13px", color: "var(--muted)" }}>
              Crawl and index arXiv research papers by pasting an arXiv URL (e.g. <code>https://arxiv.org/abs/2301.07041</code>), arXiv ID (e.g. <code>2301.07041</code>), or search query.
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "10px" }}>
              <input
                type="text"
                placeholder="arXiv URL or ID (e.g. 2301.07041 or https://arxiv.org/abs/2301.07041)"
                value={arxivQuery}
                onChange={(e) => setArxivQuery(e.target.value)}
                style={{ padding: "10px", borderRadius: "6px", border: "1px solid var(--line)", font: "inherit" }}
                required
              />
              <input
                type="text"
                placeholder="Source Name (Optional)"
                value={arxivName}
                onChange={(e) => setArxivName(e.target.value)}
                style={{ padding: "10px", borderRadius: "6px", border: "1px solid var(--line)", font: "inherit" }}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button type="submit" className="primaryButton" disabled={isSubmitting || !arxivQuery.trim()}>
                {isSubmitting ? <RefreshCw size={16} className="animateSpin" /> : <Plus size={16} />}
                Import arXiv Paper
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleImportGithub} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <p style={{ fontSize: "13px", color: "var(--muted)" }}>
              Crawl open-source code and research documentation from GitHub repositories.
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: "10px" }}>
              <input
                type="text"
                placeholder="Repository (e.g. owner/repo or https://github.com/owner/repo)"
                value={githubRepo}
                onChange={(e) => setGithubRepo(e.target.value)}
                style={{ padding: "10px", borderRadius: "6px", border: "1px solid var(--line)", font: "inherit" }}
                required
              />
              <input
                type="text"
                placeholder="Branch (default: main)"
                value={githubBranch}
                onChange={(e) => setGithubBranch(e.target.value)}
                style={{ padding: "10px", borderRadius: "6px", border: "1px solid var(--line)", font: "inherit" }}
              />
              <input
                type="password"
                placeholder="Personal Access Token (Optional)"
                value={githubToken}
                onChange={(e) => setGithubToken(e.target.value)}
                style={{ padding: "10px", borderRadius: "6px", border: "1px solid var(--line)", font: "inherit" }}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button type="submit" className="primaryButton" disabled={isSubmitting || !githubRepo.trim()}>
                {isSubmitting ? <RefreshCw size={16} className="animateSpin" /> : <Plus size={16} />}
                Import GitHub Repository
              </button>
            </div>
          </form>
        )}

        {statusMessage && (
          <div
            className={statusMessage.type === "success" ? "successBanner" : "chatErrorBanner"}
            style={{ marginTop: "12px", display: "flex", alignItems: "center", gap: "8px" }}
          >
            {statusMessage.type === "success" ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <span>{statusMessage.text}</span>
          </div>
        )}
      </div>

      {/* Connected Sources List */}
      <div className="panel wide" style={{ gridColumn: "span 3" }}>
        <div className="panelTitle">
          <h2>Connected Sources ({sources.length})</h2>
          <button type="button" className="secondaryButton" onClick={refreshSources}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Source Name</th>
              <th>Type</th>
              <th>Status</th>
              <th>Documents</th>
              <th>Last Sync</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((source) => (
              <tr key={source.id}>
                <td style={{ fontWeight: 600 }}>{source.name}</td>
                <td>
                  {source.source_type === "arxiv" ? (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                      <BookOpen size={14} /> arXiv Paper
                    </span>
                  ) : source.source_type === "github" ? (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                      <Github size={14} /> GitHub Repo
                    </span>
                  ) : (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                      <Globe size={14} /> {source.source_type}
                    </span>
                  )}
                </td>
                <td className={source.status.toLowerCase()}>{source.status}</td>
                <td>{source.document_count.toLocaleString()} docs</td>
                <td>{source.last_sync_at ? new Date(source.last_sync_at).toLocaleString() : "Never"}</td>
                <td>
                  <button
                    type="button"
                    className="secondaryButton"
                    style={{ padding: "4px 8px", fontSize: "12px" }}
                    onClick={() => syncSourceNow(source.id)}
                  >
                    <RefreshCw size={12} /> Sync Now
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {sources.length === 0 && (
          <p className="emptyState">No connected sources yet. Use the importer above to add arXiv papers or GitHub repositories.</p>
        )}
      </div>
    </>
  );
}
