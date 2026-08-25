"use client";

import { Send } from "lucide-react";
import { FormEvent, useState } from "react";
import type { ChatMessage, ChatResponse } from "./api";

const publicApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ConversationItem =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; response: ChatResponse };

export function ChatClient() {
  const [question, setQuestion] = useState("");
  const [conversation, setConversation] = useState<ConversationItem[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuestion = question.trim();
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
          mode: "hybrid",
          top_k: 8,
          candidate_k: 50
        })
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Chat request failed with ${response.status}`);
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

  return (
    <div className="chatConsole">
      <div className="messages">
        {conversation.length === 0 ? (
          <p className="emptyState">Ask a question about your indexed documents.</p>
        ) : null}

        {conversation.map((item, index) => (
          <article className={`message ${item.role}`} key={`${item.role}-${index}`}>
            <span>{item.role === "user" ? "You" : "CorpusForge"}</span>
            <p>{item.content}</p>
            {item.role === "assistant" ? (
              <div className="answerMeta">
                <strong>{formatState(item.response.evidence_status)}</strong>
                <small>Query: {item.response.retrieval_query}</small>
                {item.response.citations.length > 0 ? (
                  <ol className="citations">
                    {item.response.citations.map((citation) => (
                      <li key={citation.chunk_id}>
                        {citation.title}
                        {citation.page ? `, page ${citation.page}` : ""}
                        {citation.section ? `, ${citation.section}` : ""}
                      </li>
                    ))}
                  </ol>
                ) : null}
              </div>
            ) : null}
          </article>
        ))}
      </div>

      {error ? <p className="chatError">{error}</p> : null}

      <form className="chatForm" onSubmit={handleSubmit}>
        <textarea
          aria-label="Ask a question"
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about policies, runbooks, docs, or synced sources..."
          rows={3}
          value={question}
        />
        <button disabled={isSending || question.trim().length === 0} type="submit">
          <Send size={18} />
          <span>{isSending ? "Sending" : "Ask"}</span>
        </button>
      </form>
    </div>
  );
}

function formatState(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
