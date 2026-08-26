"use client";

import { Loader2, MessageSquare, RefreshCw, Send, Sparkles } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import type { ChatMessage, ChatResponse, DocumentItem } from "./api";

const publicApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ConversationItem =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; response: ChatResponse };

const SAMPLE_QUESTIONS = [
  "Summarize the core methodology and findings of the research paper.",
  "What are the main experimental results and metrics reported?",
  "How does this approach compare to prior baselines in the literature?"
];

function renderFormattedMarkdown(content: string) {
  if (!content) return null;

  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let currentList: React.ReactNode[] = [];

  const flushList = () => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} style={{ margin: "8px 0 12px 20px", paddingLeft: "12px" }}>
          {currentList}
        </ul>
      );
      currentList = [];
    }
  };

  const parseInline = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*|\$.*?\$)/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i} style={{ fontWeight: 600 }}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("$") && part.endsWith("$")) {
        const mathContent = part.startsWith("$$") && part.endsWith("$$") ? part.slice(2, -2) : part.slice(1, -1);
        return <code key={i} style={{ background: "rgba(255,255,255,0.08)", padding: "2px 6px", borderRadius: "4px", fontFamily: "monospace", fontSize: "13px" }}>{mathContent}</code>;
      }
      return part;
    });
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    if (trimmed === "---") {
      flushList();
      elements.push(<hr key={index} style={{ border: "none", borderTop: "1px solid rgba(255,255,255,0.12)", margin: "16px 0" }} />);
      return;
    }

    if (trimmed.startsWith("### ")) {
      flushList();
      elements.push(
        <h4 key={index} style={{ fontSize: "15px", fontWeight: 700, margin: "14px 0 6px 0" }}>
          {parseInline(trimmed.slice(4))}
        </h4>
      );
      return;
    }

    if (trimmed.startsWith("## ")) {
      flushList();
      elements.push(
        <h3 key={index} style={{ fontSize: "16px", fontWeight: 700, margin: "16px 0 6px 0" }}>
          {parseInline(trimmed.slice(3))}
        </h3>
      );
      return;
    }

    if (trimmed.startsWith("# ")) {
      flushList();
      elements.push(
        <h2 key={index} style={{ fontSize: "18px", fontWeight: 700, margin: "18px 0 8px 0" }}>
          {parseInline(trimmed.slice(2))}
        </h2>
      );
      return;
    }

    if (trimmed.startsWith("* ") || trimmed.startsWith("- ")) {
      currentList.push(
        <li key={`${index}-${currentList.length}`} style={{ marginBottom: "4px", lineHeight: "1.5" }}>
          {parseInline(trimmed.slice(2))}
        </li>
      );
      return;
    }

    flushList();

    if (trimmed === "") {
      elements.push(<div key={index} style={{ height: "6px" }} />);
    } else {
      elements.push(
        <p key={index} style={{ margin: "4px 0 8px 0", lineHeight: "1.6" }}>
          {parseInline(trimmed)}
        </p>
      );
    }
  });

  flushList();
  return <div>{elements}</div>;
}

export function ChatClient() {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"hybrid" | "dense" | "sparse">("hybrid");
  const [topK, setTopK] = useState(8);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [conversation, setConversation] = useState<ConversationItem[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchDocuments() {
      try {
        const res = await fetch(`${publicApiUrl}/api/v1/documents`);
        if (res.ok) {
          const data = (await res.json()) as DocumentItem[];
          setDocuments(data);
        }
      } catch {
        // Silently handle if documents fails to load
      }
    }
    fetchDocuments();
  }, []);

  async function handleSubmit(event?: FormEvent<HTMLFormElement>, customQuery?: string) {
    if (event) {
      event.preventDefault();
    }

    const targetQuery = customQuery ?? question;
    const trimmedQuestion = targetQuery.trim();
    if (!trimmedQuestion || isSending) {
      return;
    }

    const history: ChatMessage[] = conversation.map((item) => ({
      role: item.role,
      content: item.content
    }));

    setConversation((items) => [...items, { role: "user", content: trimmedQuestion }]);
    setQuestion("");
    setError(null);
    setIsSending(true);

    try {
      const response = await fetch(`${publicApiUrl}/api/v1/chat`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          question: trimmedQuestion,
          history,
          mode,
          top_k: topK,
          candidate_k: 50,
          document_ids: selectedDocId ? [selectedDocId] : []
        })
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Chat request failed with status ${response.status}`);
      }

      const answer = (await response.json()) as ChatResponse;
      setConversation((items) => [
        ...items,
        {
          role: "assistant",
          content: answer.answer,
          response: answer
        }
      ]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not send question");
    } finally {
      setIsSending(false);
    }
  }

  function handleClear() {
    setConversation([]);
    setError(null);
  }

  return (
    <div className="chatConsole">
      <div className="chatControls">
        <div className="controlGroup">
          <label htmlFor="modeSelect">Mode:</label>
          <select
            id="modeSelect"
            value={mode}
            onChange={(e) => setMode(e.target.value as "hybrid" | "dense" | "sparse")}
          >
            <option value="hybrid">Hybrid (Dense + Sparse)</option>
            <option value="dense">Dense Only (Vectors)</option>
            <option value="sparse">Sparse Only (BM25)</option>
          </select>

          <label htmlFor="topKSelect">Top K:</label>
          <select
            id="topKSelect"
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
          >
            <option value={4}>4 Chunks</option>
            <option value={8}>8 Chunks</option>
            <option value={12}>12 Chunks</option>
          </select>

          <label htmlFor="docSelect">Scope:</label>
          <select
            id="docSelect"
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
            style={{ maxWidth: "260px" }}
          >
            <option value="">Entire RAG (All Documents)</option>
            {documents.map((doc) => (
              <option key={doc.id} value={doc.id}>
                📄 {doc.title}
              </option>
            ))}
          </select>
        </div>

        {conversation.length > 0 ? (
          <button className="secondaryButton" type="button" onClick={handleClear}>
            <RefreshCw size={14} /> Clear Chat
          </button>
        ) : null}
      </div>

      <div className="messages">
        {conversation.length === 0 ? (
          <div className="chatEmptyState">
            <Sparkles size={32} className="emptyIcon" />
            <h3>Ask questions grounded in your document repository</h3>
            <p>Select a sample prompt below or type your query in the chat input.</p>
            <div className="samplePrompts">
              {SAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  className="samplePromptCard"
                  type="button"
                  onClick={() => handleSubmit(undefined, q)}
                >
                  <MessageSquare size={16} />
                  <span>{q}</span>
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {conversation.map((item, index) => (
          <article className={`message ${item.role}`} key={`${item.role}-${index}`}>
            <span style={{ fontWeight: 600, color: "var(--muted)", fontSize: "12px", display: "block", marginBottom: "4px" }}>
              {item.role === "user" ? "You" : "CorpusForge RAG"}
            </span>
            <div style={{ lineHeight: "1.6", margin: "4px 0 12px 0", fontSize: "14px" }}>
              {renderFormattedMarkdown(item.content)}
            </div>
            {item.role === "assistant" ? (
              <div className="answerMeta">
                <span className={`statusBadge ${item.response.evidence_status}`}>
                  {formatState(item.response.evidence_status)}
                </span>
                <small className="queryTrace">Expanded Query: {item.response.retrieval_query}</small>
                {item.response.citations && item.response.citations.length > 0 ? (
                  <div className="citationBox">
                    <strong>Sources & Citations ({item.response.citations.length}):</strong>
                    <ol className="citations">
                      {item.response.citations.map((citation) => (
                        <li key={citation.chunk_id}>
                          {citation.source_url ? (
                            <a href={citation.source_url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent)", textDecoration: "underline" }}>
                              {citation.title}
                            </a>
                          ) : (
                            <span>{citation.title}</span>
                          )}
                          {citation.page ? ` (page ${citation.page})` : ""}
                          {citation.section ? ` - ${citation.section}` : ""}
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : null}
              </div>
            ) : null}
          </article>
        ))}

        {isSending ? (
          <article className="message assistant loadingMessage">
            <span>CorpusForge RAG</span>
            <div className="loadingSpinnerRow">
              <Loader2 size={18} className="animateSpin" />
              <span>Retrieving relevant context and generating grounded response...</span>
            </div>
          </article>
        ) : null}
      </div>

      {error ? <div className="chatErrorBanner">{error}</div> : null}

      <form className="chatForm" onSubmit={handleSubmit}>
        <textarea
          aria-label="Ask a question"
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about policies, runbooks, docs, or synced sources..."
          rows={3}
          value={question}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
        <button disabled={isSending || question.trim().length === 0} type="submit">
          {isSending ? <Loader2 size={18} className="animateSpin" /> : <Send size={18} />}
          <span>{isSending ? "Processing" : "Ask"}</span>
        </button>
      </form>
    </div>
  );
}

function formatState(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
