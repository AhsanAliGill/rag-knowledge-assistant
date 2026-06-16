import { apiFetch } from "./client";

export interface EvalListItem {
  eval_id: string;
  doc_id: string;
  status: string;
  overall: number | null;
  qa_count: number;
  created_at: string;
}

export interface EvalScores {
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
  overall: number;
}

export interface EvalPassFail {
  faithfulness: string;
  answer_relevancy: string;
  context_precision: string;
  context_recall: string;
  overall: string;
}

export interface PerQuestion {
  question: string;
  expected_answer: string;
  generated_answer: string;
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
  source_found: boolean;
  source_section: string | null;
  latency_ms: number;
}

export interface EvalReport {
  eval_id: string;
  doc_id: string;
  status: string;
  qa_count: number;
  created_at: string;
  completed_at: string | null;
  scores: EvalScores | null;
  pass_fail: EvalPassFail | null;
  thresholds_used: EvalScores | null;
  per_question_results: PerQuestion[] | null;
  // status-only fields
  progress?: number;
  qa_total?: number;
  qa_done?: number;
}

export const listEvaluations = () =>
  apiFetch<{ evaluations: EvalListItem[]; total: number }>("/api/v1/rag/evaluations");

export const triggerEvaluation = (docId: string) =>
  apiFetch<{ eval_id: string; status: string; qa_count: number; message: string }>(
    "/api/v1/rag/evaluations",
    { method: "POST", body: JSON.stringify({ doc_id: docId }) }
  );

export const getEvaluation = (evalId: string) =>
  apiFetch<EvalReport>(`/api/v1/rag/evaluations/${evalId}`);
