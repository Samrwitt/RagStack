"use client";

import { useState, useRef } from "react";
import { FileText, Upload, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import type { DocumentItem } from "../api";

export function DocumentsClient({ initialDocuments }: { initialDocuments: DocumentItem[] }) {
  const [documents, setDocuments] = useState<DocumentItem[]>(initialDocuments);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setStatusMessage(null);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    setStatusMessage(null);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const apiBase = typeof window !== "undefined" ? "http://localhost:8000" : "";
      const res = await fetch(`${apiBase}/api/v1/documents/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => null);
        throw new Error(errorData?.detail || `Upload failed with status ${res.status}`);
      }

      const result = await res.json();
      setStatusMessage({
        type: "success",
        text: `Uploaded "${selectedFile.name}" successfully! Processing job enqueued.`,
      });
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      // Fetch refreshed document list
      refreshDocuments();
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to upload document",
      });
    } finally {
      setIsUploading(false);
    }
  };

  const refreshDocuments = async () => {
    try {
      const apiBase = typeof window !== "undefined" ? "http://localhost:8000" : "";
      const res = await fetch(`${apiBase}/api/v1/documents`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch {
      // Keep existing list on error
    }
  };

  return (
    <>
      {/* Upload Box */}
      <div className="panel" style={{ gridColumn: "span 3", minHeight: "auto", marginBottom: "14px" }}>
        <div className="panelTitle">
          <h2>Upload Document</h2>
        </div>
        <form onSubmit={handleUpload} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div
            style={{
              border: "2px dashed var(--line)",
              borderRadius: "8px",
              padding: "20px",
              textAlign: "center",
              background: "#f8fafc",
              cursor: "pointer",
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload size={28} style={{ color: "var(--accent)", marginBottom: "8px" }} />
            <p style={{ fontWeight: 600, fontSize: "14px", marginBottom: "4px" }}>
              {selectedFile ? selectedFile.name : "Click or drag a file to upload"}
            </p>
            <span style={{ fontSize: "12px", color: "var(--muted)" }}>
              Supports PDF, DOCX, Markdown (.md), and TXT files (up to 50MB)
            </span>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.md,.txt,.html"
              onChange={handleFileChange}
              style={{ display: "none" }}
            />
          </div>

          {statusMessage && (
            <div
              className={statusMessage.type === "success" ? "successBanner" : "chatErrorBanner"}
              style={{ display: "flex", alignItems: "center", gap: "8px" }}
            >
              {statusMessage.type === "success" ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
              <span>{statusMessage.text}</span>
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
            {selectedFile && (
              <button
                type="button"
                className="secondaryButton"
                onClick={() => {
                  setSelectedFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
              >
                Clear
              </button>
            )}
            <button type="submit" className="primaryButton" disabled={!selectedFile || isUploading}>
              {isUploading ? (
                <>
                  <RefreshCw size={16} className="animateSpin" /> Uploading & Ingesting...
                </>
              ) : (
                <>
                  <Upload size={16} /> Upload & Process
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Documents List Panel */}
      <div className="panel wide" style={{ gridColumn: "span 3" }}>
        <div className="panelTitle">
          <h2>Indexed Documents ({documents.length})</h2>
          <button type="button" className="secondaryButton" onClick={refreshDocuments}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
        <div className="documents">
          {documents.map((doc) => (
            <div key={doc.id} className="documentRow">
              <FileText size={17} />
              <strong>{doc.title}</strong>
              <span>{doc.source_type}</span>
              <em style={{ textTransform: "capitalize" }}>{doc.current_state.replace("_", " ")}</em>
            </div>
          ))}
          {documents.length === 0 && (
            <p className="emptyState">No documents uploaded or indexed yet. Use the uploader above to add one.</p>
          )}
        </div>
      </div>
    </>
  );
}
