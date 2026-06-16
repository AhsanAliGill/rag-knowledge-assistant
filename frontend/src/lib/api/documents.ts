import { apiFetch } from "./client";

export interface DocRead {
  doc_id: string;
  filename: string;
  status: "pending" | "processing" | "ready" | "failed";
  page_count: number | null;
  chunk_count: number | null;
  size_bytes: number;
  created_at: string;
  ready_at: string | null;
}

export interface DocDetailRead extends DocRead {
  parent_chunks: number | null;
  child_chunks: number | null;
  sha256: string;
}

export interface JobStatus {
  job_id: string;
  doc_id: string;
  status: string;
  progress: number;
  message: string | null;
  error_message: string | null;
}

export interface UploadResponse {
  doc_id: string;
  job_id: string;
  status: string;
  message: string;
}

export const listDocuments = () =>
  apiFetch<{ documents: DocRead[]; total: number }>("/api/v1/rag/documents");

export const uploadDocument = (file: File, description?: string) => {
  const fd = new FormData();
  fd.append("file", file);
  if (description) fd.append("description", description);
  return apiFetch<UploadResponse>("/api/v1/rag/documents", { method: "POST", body: fd });
};

export const deleteDocument = (docId: string) =>
  apiFetch<void>(`/api/v1/rag/documents/${docId}`, { method: "DELETE" });

export const getDocument = (docId: string) =>
  apiFetch<DocDetailRead>(`/api/v1/rag/documents/${docId}`);

export const getJobStatus = (jobId: string) =>
  apiFetch<JobStatus>(`/api/v1/rag/documents/jobs/${jobId}`);
