"use client";

import { Check, Loader2, RefreshCw, Save, Settings as SettingsIcon } from "lucide-react";
import { useEffect, useState } from "react";
import type { SettingsConfig } from "../api";

const publicApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function SettingsClient() {
  const [config, setConfig] = useState<SettingsConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Editable fields
  const [rerankerEnabled, setRerankerEnabled] = useState(true);
  const [rerankerCandidateK, setRerankerCandidateK] = useState(50);
  const [contextTokenBudget, setContextTokenBudget] = useState(4000);
  const [minGroundingScore, setMinGroundingScore] = useState(0.1);

  async function fetchSettings() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${publicApiUrl}/api/v1/settings`);
      if (!response.ok) {
        throw new Error(`Failed to load settings (${response.status})`);
      }
      const data = (await response.json()) as SettingsConfig;
      setConfig(data);
      setRerankerEnabled(data.reranker_enabled);
      setRerankerCandidateK(data.reranker_candidate_k);
      setContextTokenBudget(data.context_token_budget);
      setMinGroundingScore(data.min_grounding_score);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error fetching settings");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchSettings();
  }, []);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSavedSuccess(false);

    try {
      const response = await fetch(`${publicApiUrl}/api/v1/settings`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          reranker_enabled: rerankerEnabled,
          reranker_candidate_k: rerankerCandidateK,
          context_token_budget: contextTokenBudget,
          min_grounding_score: minGroundingScore
        })
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Failed to save settings (${response.status})`);
      }

      const updated = (await response.json()) as SettingsConfig;
      setConfig(updated);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update settings");
    } finally {
      setSaving(false);
    }
  }

  if (loading && !config) {
    return (
      <div className="settingsConsole loading">
        <Loader2 size={24} className="animateSpin" />
        <span>Loading system configuration...</span>
      </div>
    );
  }

  return (
    <div className="settingsConsole">
      {error ? <div className="chatErrorBanner">{error}</div> : null}
      {savedSuccess ? (
        <div className="successBanner">
          <Check size={16} /> Runtime configuration updated successfully.
        </div>
      ) : null}

      <div className="settingsGroup">
        <h3>
          <SettingsIcon size={16} /> Retrieval & Reranking Settings
        </h3>

        <div className="settingItem">
          <label className="checkboxLabel">
            <input
              type="checkbox"
              checked={rerankerEnabled}
              onChange={(e) => setRerankerEnabled(e.target.checked)}
            />
            <strong>Enable Cross-Encoder Reranking</strong>
          </label>
          <p className="settingDesc">
            When enabled, top retrieval candidates from dense and sparse search are re-scored using cross-encoder.
          </p>
        </div>

        <div className="settingItem">
          <label htmlFor="candidateKInput">
            <strong>Reranker Candidate Pool Size (candidate_k)</strong>
          </label>
          <input
            id="candidateKInput"
            type="number"
            min={10}
            max={200}
            value={rerankerCandidateK}
            onChange={(e) => setRerankerCandidateK(Number(e.target.value))}
          />
          <p className="settingDesc">Number of candidates retrieved from vector & BM25 before applying reranker.</p>
        </div>

        <div className="settingItem">
          <label htmlFor="tokenBudgetInput">
            <strong>Context Token Budget (tokens)</strong>
          </label>
          <input
            id="tokenBudgetInput"
            type="number"
            min={500}
            max={32000}
            step={500}
            value={contextTokenBudget}
            onChange={(e) => setContextTokenBudget(Number(e.target.value))}
          />
          <p className="settingDesc">Maximum tokens allocated for context chunks in the LLM generation prompt.</p>
        </div>

        <div className="settingItem">
          <label htmlFor="groundingScoreInput">
            <strong>Minimum Grounding Cutoff Score</strong>
          </label>
          <input
            id="groundingScoreInput"
            type="number"
            min={0.0}
            max={1.0}
            step={0.05}
            value={minGroundingScore}
            onChange={(e) => setMinGroundingScore(Number(e.target.value))}
          />
          <p className="settingDesc">Queries with maximum hit score below this threshold will return INSUFFICIENT evidence status.</p>
        </div>

        <div className="providerInfoRow">
          <span>Active LLM Provider: <strong>{config?.llm_provider ?? "mock"}</strong></span>
          <span>Active Reranker Provider: <strong>{config?.reranker_provider ?? "flashrank"}</strong></span>
        </div>
      </div>

      <div className="settingsActions">
        <button type="button" className="secondaryButton" onClick={fetchSettings} disabled={saving}>
          <RefreshCw size={14} /> Reset
        </button>
        <button type="button" className="primaryButton" onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 size={14} className="animateSpin" /> : <Save size={14} />}
          <span>{saving ? "Saving..." : "Save Settings"}</span>
        </button>
      </div>
    </div>
  );
}
