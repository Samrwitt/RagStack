"use client";

import { Layers, Loader2, Search, SlidersHorizontal, Sparkles } from "lucide-react";
import { FormEvent, useState } from "react";
import type { SearchDebugResponse, SearchHit } from "../api";

const publicApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function RetrievalDebuggerClient() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"hybrid" | "dense" | "sparse">("hybrid");
  const [topK, setTopK] = useState(8);
  const [candidateK, setCandidateK] = useState(50);
  const [rerank, setRerank] = useState(true);
  const [activeTab, setActiveTab] = useState<"reranked" | "dense" | "sparse" | "rrf" | "context">("reranked");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [debugData, setDebugData] = useState<SearchDebugResponse | null>(null);

  async function handleSearch(e?: FormEvent) {
    if (e) {
      e.preventDefault();
    }
    if (!query.trim() || loading) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${publicApiUrl}/api/v1/search/debug`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          query: query.trim(),
          mode,
          top_k: topK,
          candidate_k: candidateK,
          rerank
        })
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Search request failed (${response.status})`);
      }

      const data = (await response.json()) as SearchDebugResponse;
      setDebugData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to execute search");
    } finally {
      setLoading(false);
    }
  }

  function getActiveHits(): SearchHit[] {
    if (!debugData) return [];
    switch (activeTab) {
      case "dense":
        return debugData.dense_hits;
      case "sparse":
        return debugData.sparse_hits;
      case "rrf":
        return debugData.rrf_hits;
      case "reranked":
        return debugData.reranked_hits;
      case "context":
        return debugData.final_context;
      default:
        return debugData.reranked_hits;
    }
  }

  return (
    <div className="retrievalDebugger">
      <form className="debugForm" onSubmit={handleSearch}>
        <div className="searchBarRow">
          <input
            type="text"
            placeholder="Type query to test retrieval & reranking..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" disabled={loading || !query.trim()}>
            {loading ? <Loader2 size={18} className="animateSpin" /> : <Search size={18} />}
            <span>{loading ? "Searching..." : "Inspect"}</span>
          </button>
        </div>

        <div className="debugOptionsRow">
          <div className="optionItem">
            <SlidersHorizontal size={14} />
            <label htmlFor="debugMode">Mode:</label>
            <select
              id="debugMode"
              value={mode}
              onChange={(e) => setMode(e.target.value as "hybrid" | "dense" | "sparse")}
            >
              <option value="hybrid">Hybrid (RRF)</option>
              <option value="dense">Dense Vector</option>
              <option value="sparse">Sparse BM25</option>
            </select>
          </div>

          <div className="optionItem">
            <label htmlFor="debugTopK">Top K:</label>
            <input
              id="debugTopK"
              type="number"
              min={1}
              max={50}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            />
          </div>

          <div className="optionItem">
            <label htmlFor="debugCandidateK">Candidates:</label>
            <input
              id="debugCandidateK"
              type="number"
              min={1}
              max={200}
              value={candidateK}
              onChange={(e) => setCandidateK(Number(e.target.value))}
            />
          </div>

          <div className="optionItem checkboxOption">
            <label>
              <input
                type="checkbox"
                checked={rerank}
                onChange={(e) => setRerank(e.target.checked)}
              />
              Enable Reranker
            </label>
          </div>
        </div>
      </form>

      {error ? <div className="chatErrorBanner">{error}</div> : null}

      {debugData ? (
        <div className="debugResults">
          <div className="latencyMetricsRow">
            <span className="metricBadge">Dense: {debugData.latency_ms.dense} ms</span>
            <span className="metricBadge">Sparse: {debugData.latency_ms.sparse} ms</span>
            <span className="metricBadge">RRF: {debugData.latency_ms.rrf} ms</span>
            <span className="metricBadge">Reranker: {debugData.latency_ms.rerank} ms</span>
            <strong className="metricBadge total">Total: {debugData.latency_ms.total} ms</strong>
          </div>

          <div className="tabHeader">
            <button
              className={activeTab === "reranked" ? "tab active" : "tab"}
              type="button"
              onClick={() => setActiveTab("reranked")}
            >
              Reranked ({debugData.reranked_hits.length})
            </button>
            <button
              className={activeTab === "dense" ? "tab active" : "tab"}
              type="button"
              onClick={() => setActiveTab("dense")}
            >
              Dense Vectors ({debugData.dense_hits.length})
            </button>
            <button
              className={activeTab === "sparse" ? "tab active" : "tab"}
              type="button"
              onClick={() => setActiveTab("sparse")}
            >
              Sparse BM25 ({debugData.sparse_hits.length})
            </button>
            <button
              className={activeTab === "rrf" ? "tab active" : "tab"}
              type="button"
              onClick={() => setActiveTab("rrf")}
            >
              RRF Fusion ({debugData.rrf_hits.length})
            </button>
            <button
              className={activeTab === "context" ? "tab active" : "tab"}
              type="button"
              onClick={() => setActiveTab("context")}
            >
              Final Context ({debugData.final_context.length})
            </button>
          </div>

          <div className="hitCardsList">
            {getActiveHits().length === 0 ? (
              <p className="emptyState">No hits returned for this stage.</p>
            ) : (
              getActiveHits().map((hit, idx) => (
                <div key={`${hit.chunk_id}-${idx}`} className="hitCard">
                  <div className="hitCardHeader">
                    <span className="rankTag">Rank #{hit.rank}</span>
                    <strong className="hitTitle">{hit.title}</strong>
                    <span className="scoreTag">Score: {hit.score.toFixed(4)}</span>
                  </div>

                  <p className="hitSnippet">{hit.text}</p>

                  <div className="hitMetaRow">
                    {hit.source_type ? <span>Source: {hit.source_type}</span> : null}
                    {hit.page ? <span>Page: {hit.page}</span> : null}
                    {hit.section ? <span>Section: {hit.section}</span> : null}
                    {hit.scores && Object.keys(hit.scores).length > 0 ? (
                      <span className="scoresDetail">
                        Scores: {JSON.stringify(hit.scores)}
                      </span>
                    ) : null}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ) : !loading ? (
        <div className="debugEmptyState">
          <Layers size={32} />
          <p>Submit a query above to visualize Dense vs Sparse vs RRF vs Reranked candidates stage-by-stage.</p>
        </div>
      ) : null}
    </div>
  );
}
