"use client";

import { BarChart3, FlaskConical, Loader2, Play, Plus, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import type { EvalRecord, EvalRun } from "../api";

const publicApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEFAULT_DATASET: EvalRecord[] = [
  {
    question: "What is the annual leave policy for full-time employees?",
    expected_answer: "Full-time employees receive 22 days of annual leave.",
    relevant_document_ids: []
  },
  {
    question: "How are security vulnerabilities handled?",
    expected_answer: "Vulnerabilities must be reported to security@corpusforge.local within 24 hours.",
    relevant_document_ids: []
  }
];

export function EvaluationClient() {
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [runningEval, setRunningEval] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [testQuestion, setTestQuestion] = useState("");
  const [testExpected, setTestExpected] = useState("");
  const [customDataset, setCustomDataset] = useState<EvalRecord[]>(DEFAULT_DATASET);

  async function fetchRuns() {
    setLoadingRuns(true);
    setError(null);
    try {
      const response = await fetch(`${publicApiUrl}/api/v1/evaluation/runs`);
      if (response.ok) {
        const data = (await response.json()) as EvalRun[];
        setRuns(data);
      } else {
        throw new Error(`Failed to load runs (${response.status})`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error fetching evaluation runs");
    } finally {
      setLoadingRuns(false);
    }
  }

  useEffect(() => {
    fetchRuns();
  }, []);

  function handleAddQuestion() {
    if (!testQuestion.trim()) return;
    setCustomDataset((prev) => [
      ...prev,
      {
        question: testQuestion.trim(),
        expected_answer: testExpected.trim(),
        relevant_document_ids: []
      }
    ]);
    setTestQuestion("");
    setTestExpected("");
  }

  async function handleRunEvaluation(isExperiment: boolean) {
    if (customDataset.length === 0 || runningEval) return;
    setRunningEval(true);
    setError(null);

    const endpoint = isExperiment
      ? `${publicApiUrl}/api/v1/evaluation/experiment`
      : `${publicApiUrl}/api/v1/evaluation/run`;

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          name: isExperiment ? "Standard Retrieval Benchmark" : "Ad hoc Evaluation",
          dataset: customDataset,
          config: {
            mode: "hybrid",
            top_k: 10,
            candidate_k: 50,
            rerank: true,
            generate: true
          }
        })
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Evaluation failed (${response.status})`);
      }

      await fetchRuns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run evaluation");
    } finally {
      setRunningEval(false);
    }
  }

  return (
    <div className="evaluationConsole">
      <div className="evalSection">
        <div className="sectionHeader">
          <div className="sectionTitleRow">
            <FlaskConical size={18} />
            <h3>Evaluation Dataset Benchmark ({customDataset.length} items)</h3>
          </div>
          <div className="actionButtons">
            <button
              type="button"
              className="primaryButton"
              disabled={runningEval || customDataset.length === 0}
              onClick={() => handleRunEvaluation(false)}
            >
              {runningEval ? <Loader2 size={14} className="animateSpin" /> : <Play size={14} />}
              <span>Run Single Eval</span>
            </button>

            <button
              type="button"
              className="experimentButton"
              disabled={runningEval || customDataset.length === 0}
              onClick={() => handleRunEvaluation(true)}
            >
              {runningEval ? <Loader2 size={14} className="animateSpin" /> : <BarChart3 size={14} />}
              <span>Run Experiment (Dense vs Hybrid vs Reranker)</span>
            </button>
          </div>
        </div>

        <div className="addQuestionRow">
          <input
            type="text"
            placeholder="Test Question..."
            value={testQuestion}
            onChange={(e) => setTestQuestion(e.target.value)}
          />
          <input
            type="text"
            placeholder="Expected Answer (Ground Truth)..."
            value={testExpected}
            onChange={(e) => setTestExpected(e.target.value)}
          />
          <button type="button" onClick={handleAddQuestion} disabled={!testQuestion.trim()}>
            <Plus size={16} /> Add
          </button>
        </div>

        <ul className="datasetList">
          {customDataset.map((item, idx) => (
            <li key={idx} className="datasetItem">
              <strong>Q: {item.question}</strong>
              {item.expected_answer ? <p>Expected: {item.expected_answer}</p> : null}
            </li>
          ))}
        </ul>
      </div>

      {error ? <div className="chatErrorBanner">{error}</div> : null}

      <div className="evalSection">
        <div className="sectionHeader">
          <div className="sectionTitleRow">
            <BarChart3 size={18} />
            <h3>Evaluation Runs & Experiment Results</h3>
          </div>
          <button type="button" className="secondaryButton" onClick={fetchRuns} disabled={loadingRuns}>
            <RefreshCw size={14} className={loadingRuns ? "animateSpin" : ""} /> Refresh
          </button>
        </div>

        {runs.length === 0 ? (
          <p className="emptyState">No evaluation runs recorded yet. Click &quot;Run Experiment&quot; above.</p>
        ) : (
          <div className="runsTableContainer">
            <table className="evalTable">
              <thead>
                <tr>
                  <th>Run Name</th>
                  <th>Status</th>
                  <th>Recall@K</th>
                  <th>MRR</th>
                  <th>NDCG@K</th>
                  <th>Groundedness</th>
                  <th>Faithfulness</th>
                  <th>Relevance</th>
                  <th>Citation Precision</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>
                      <strong>{run.name}</strong>
                      <div className="runConfigTag">
                        {String(run.config?.mode ?? "hybrid")} {run.config?.rerank ? "+ Reranker" : ""}
                      </div>
                    </td>
                    <td><span className="statusBadge succeeded">{run.status}</span></td>
                    <td>{formatMetric(run.metrics?.recall_at_k)}</td>
                    <td>{formatMetric(run.metrics?.mrr)}</td>
                    <td>{formatMetric(run.metrics?.ndcg_at_k)}</td>
                    <td>{formatMetric(run.metrics?.groundedness)}</td>
                    <td>{formatMetric(run.metrics?.faithfulness)}</td>
                    <td>{formatMetric(run.metrics?.answer_relevance)}</td>
                    <td>{formatMetric(run.metrics?.citation_correctness)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function formatMetric(val: number | undefined) {
  if (typeof val !== "number") return "-";
  return (val * 100).toFixed(1) + "%";
}
