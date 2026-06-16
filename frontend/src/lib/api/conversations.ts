import { apiFetch } from "./client";

export interface ConvSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ConvHistory extends ConvSummary {
  messages: MessageItem[];
}

export const listConversations = () =>
  apiFetch<ConvSummary[]>("/api/v1/rag/conversations");

export const getConversation = (id: string) =>
  apiFetch<ConvHistory>(`/api/v1/rag/conversations/${id}`);

export const deleteConversation = (id: string) =>
  apiFetch<void>(`/api/v1/rag/conversations/${id}`, { method: "DELETE" });
