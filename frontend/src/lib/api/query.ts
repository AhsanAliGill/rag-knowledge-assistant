import { apiFetch } from "./client";

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export interface SourceChunk {
  chunk_id: string;
  doc_id: string | null;
  corpus_name: string | null;
  section_path: string | null;
  page_num: number | null;
  relevance_score: number;
  text_excerpt: string;
}

export interface QueryMeta {
  query_id: string;
  corpus_searched: string;
  chunks_retrieved: number;
  chunks_after_rerank: number;
  latency_ms: number;
}

export interface QueryResponse {
  answer: string;
  sources: SourceChunk[];
  metadata: QueryMeta;
  conversation_id: string;
}

export const sendQuery = (question: string, conversationId?: string) =>
  apiFetch<QueryResponse>("/api/v1/rag/query", {
    method: "POST",
    body: JSON.stringify({
      question,
      ...(conversationId ? { conversation_id: conversationId } : {}),
    }),
  });

export type StreamEvent =
  | { type: "start"; conversation_id: string }
  | { type: "meta"; sources: SourceChunk[]; query_id: string; chunks_retrieved: number }
  | { type: "token"; content: string }
  | { type: "done"; latency_ms: number }
  | { type: "error"; message: string };

export async function* streamQuery(
  question: string,
  conversationId?: string,
): AsyncGenerator<StreamEvent> {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/v1/rag/query/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      question,
      conversation_id: conversationId ?? null,
    }),
  });

  if (!res.ok || !res.body) {
    if (res.status === 401) {
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    const err = await res.json().catch(() => ({ detail: "Stream failed" }));
    throw new Error((err as { detail?: string }).detail ?? "Stream failed");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        yield JSON.parse(trimmed) as StreamEvent;
      } catch {
        // skip malformed line
      }
    }
  }

  if (buffer.trim()) {
    try {
      yield JSON.parse(buffer.trim()) as StreamEvent;
    } catch {
      // ignore
    }
  }
}
