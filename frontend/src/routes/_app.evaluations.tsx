import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Play, Eye, ChevronDown, ChevronUp, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { StatusBadge } from "@/components/StatusBadge";
import { cn } from "@/lib/utils";
import {
  listEvaluations, triggerEvaluation, getEvaluation,
  type EvalListItem, type EvalReport, type PerQuestion,
} from "@/lib/api/evaluations";
import { listDocuments, type DocRead } from "@/lib/api/documents";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";

export const Route = createFileRoute("/_app/evaluations")({
  head: () => ({ meta: [{ title: "Evaluations — Knowledge Assistant" }] }),
  component: EvaluationsPage,
});

function scoreColor(score: number) {
  if (score >= 0.8) return "text-emerald-600";
  if (score >= 0.6) return "text-amber-600";
  return "text-red-500";
}

function EvaluationsPage() {
  const [evals, setEvals] = useState<EvalListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [runOpen, setRunOpen] = useState(false);
  const [readyDocs, setReadyDocs] = useState<DocRead[]>([]);
  const [selectedDocId, setSelectedDocId] = useState("");
  const [triggering, setTriggering] = useState(false);
  const [view, setView] = useState<EvalReport | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const pollTimers: Record<string, ReturnType<typeof setInterval>> = {};

  const fetchEvals = () =>
    listEvaluations()
      .then((r) => setEvals(r.evaluations))
      .catch(() => toast.error("Failed to load evaluations"))
      .finally(() => setLoading(false));

  useEffect(() => {
    fetchEvals();
    listDocuments()
      .then((r) => {
        const ready = r.documents.filter((d) => d.status === "ready");
        setReadyDocs(ready);
        if (ready.length > 0) setSelectedDocId(ready[0].doc_id);
      })
      .catch(() => {});
    return () => { Object.values(pollTimers).forEach(clearInterval); };
  }, []);

  const startPolling = (evalId: string) => {
    if (pollTimers[evalId]) return;
    pollTimers[evalId] = setInterval(async () => {
      try {
        const report = await getEvaluation(evalId);
        if (report.status === "completed" || report.status === "failed") {
          clearInterval(pollTimers[evalId]);
          delete pollTimers[evalId];
          await fetchEvals();
          if (report.status === "completed") toast.success("Evaluation complete!");
          else toast.error("Evaluation failed");
        }
      } catch { /* ignore */ }
    }, 3000);
  };

  const handleTrigger = async () => {
    if (!selectedDocId) return;
    setTriggering(true);
    try {
      const res = await triggerEvaluation(selectedDocId);
      toast.success(`Evaluation started — ${res.qa_count} Q&A pairs`);
      setRunOpen(false);
      await fetchEvals();
      startPolling(res.eval_id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start evaluation");
    } finally {
      setTriggering(false);
    }
  };

  const openReport = async (evalId: string) => {
    setLoadingReport(true);
    setView(null);
    try {
      const report = await getEvaluation(evalId);
      setView(report);
    } catch {
      toast.error("Failed to load evaluation report");
    } finally {
      setLoadingReport(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1A1B41]">Evaluations</h1>
          <p className="text-sm text-[#5B5C8A] mt-1">RAGAS faithfulness, relevancy, precision, and recall scoring.</p>
        </div>
        <button
          onClick={() => setRunOpen(true)}
          className="text-white px-4 py-2 rounded-xl text-sm font-semibold active:scale-95 transition-all flex items-center gap-2 neon-gradient" style={{ background: "linear-gradient(135deg, #00F2FE, #F62681)" }}
        >
          <Play className="h-4 w-4" />
          Run Evaluation
        </button>
      </header>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-[#9BA3C2]" />
        </div>
      ) : evals.length === 0 ? (
        <div className="glass rounded-xl p-12 flex flex-col items-center text-center">
          <p className="text-sm text-[#9BA3C2]">No evaluations yet. Run one to measure your RAG quality.</p>
        </div>
      ) : (
        <div className="glass rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-[#5B5C8A] border-b border-purple-100" style={{ background: "rgba(255,255,255,0.55)" }}>
                <tr>
                  <th className="text-left font-semibold px-6 py-3">Document ID</th>
                  <th className="text-left font-semibold px-3 py-3">Status</th>
                  <th className="text-left font-semibold px-3 py-3">Q&amp;A</th>
                  <th className="text-left font-semibold px-3 py-3">Faithfulness</th>
                  <th className="text-left font-semibold px-3 py-3">Relevancy</th>
                  <th className="text-left font-semibold px-3 py-3">Precision</th>
                  <th className="text-left font-semibold px-3 py-3">Recall</th>
                  <th className="text-left font-semibold px-3 py-3">Overall</th>
                  <th className="text-right font-semibold px-6 py-3">Details</th>
                </tr>
              </thead>
              <tbody>
                {evals.map((e) => (
                  <tr key={e.eval_id} className="border-t border-purple-100 hover:transition-colors">
                    <td className="px-6 py-3.5 text-[#5B5C8A] font-mono text-xs truncate max-w-[200px]">
                      {e.doc_id.slice(0, 8)}…
                    </td>
                    <td className="px-3 py-3.5"><StatusBadge status={e.status as "pending" | "processing" | "ready" | "failed" | "completed" | "queued"} /></td>
                    <td className="px-3 py-3.5 text-[#5B5C8A]">{e.qa_count}</td>
                    <td className="px-3 py-3.5 text-[#9BA3C2]">—</td>
                    <td className="px-3 py-3.5 text-[#9BA3C2]">—</td>
                    <td className="px-3 py-3.5 text-[#9BA3C2]">—</td>
                    <td className="px-3 py-3.5 text-[#9BA3C2]">—</td>
                    <td className={cn("px-3 py-3.5 font-bold", e.overall != null ? scoreColor(e.overall) : "text-[#9BA3C2]")}>
                      {e.overall != null ? e.overall.toFixed(2) : "—"}
                    </td>
                    <td className="px-6 py-3.5 text-right">
                      <button
                        onClick={() => openReport(e.eval_id)}
                        disabled={e.status !== "completed"}
                        className="p-1.5 rounded-lg text-[#9BA3C2] hover:text-[#00F2FE] hover:bg-purple-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Run Evaluation dialog */}
      <Dialog open={runOpen} onOpenChange={(o) => !o && setRunOpen(false)}>
        <DialogContent className="glass-opaque text-[#1A1B41] border-0">
          <DialogHeader>
            <DialogTitle className="text-[#1A1B41]">Run RAGAS Evaluation</DialogTitle>
            <DialogDescription className="text-[#5B5C8A]">
              Generate Q&amp;A pairs and score retrieval + generation quality.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <label className="text-xs font-semibold text-[#5B5C8A] uppercase tracking-wide">Document</label>
            {readyDocs.length === 0 ? (
              <p className="text-sm text-[#9BA3C2]">No ready documents found. Upload and process a PDF first.</p>
            ) : (
              <select
                value={selectedDocId}
                onChange={(e) => setSelectedDocId(e.target.value)}
                className="w-full glass rounded-xl px-3 py-2.5 text-sm text-[#1A1B41] focus:outline-none transition-all"
              >
                {readyDocs.map((d) => (
                  <option key={d.doc_id} value={d.doc_id}>{d.filename}</option>
                ))}
              </select>
            )}
          </div>
          <DialogFooter>
            <button
              onClick={() => setRunOpen(false)}
              className="glass text-[#1A1B41] px-4 py-2 rounded-xl text-sm font-medium transition-colors hover:opacity-80"
            >
              Cancel
            </button>
            <button
              onClick={handleTrigger}
              disabled={!selectedDocId || triggering}
              className="flex items-center gap-2 disabled:opacity-50 text-white px-4 py-2 rounded-xl text-sm font-semibold transition-all neon-gradient" style={{ background: "linear-gradient(135deg, #00F2FE, #F62681)" }}
            >
              {triggering && <Loader2 className="h-3 w-3 animate-spin" />}
              Start Evaluation
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Report detail sheet */}
      <Sheet open={!!view || loadingReport} onOpenChange={(o) => !o && setView(null)}>
        <SheetContent className="glass-opaque text-[#1A1B41] w-full sm:max-w-2xl overflow-y-auto border-0">
          {loadingReport ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-[#9BA3C2]" />
            </div>
          ) : view && (
            <>
              <SheetHeader>
                <SheetTitle className="text-slate-800 font-mono text-sm">{view.eval_id}</SheetTitle>
                <SheetDescription className="text-[#9BA3C2]">
                  {new Date(view.created_at).toLocaleString()}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-6 space-y-6 px-4 pb-8">
                <StatusBadge status={view.status as "pending" | "processing" | "ready" | "failed" | "completed" | "queued"} />

                {view.scores && view.pass_fail && view.thresholds_used && (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <MetricCard label="Faithfulness" score={view.scores.faithfulness} threshold={view.thresholds_used.faithfulness} verdict={view.pass_fail.faithfulness} />
                      <MetricCard label="Answer Relevancy" score={view.scores.answer_relevancy} threshold={view.thresholds_used.answer_relevancy} verdict={view.pass_fail.answer_relevancy} />
                      <MetricCard label="Context Precision" score={view.scores.context_precision} threshold={view.thresholds_used.context_precision} verdict={view.pass_fail.context_precision} />
                      <MetricCard label="Context Recall" score={view.scores.context_recall} threshold={view.thresholds_used.context_recall} verdict={view.pass_fail.context_recall} />
                    </div>
                    <div className="glass-strong rounded-xl p-6 text-center" style={{ background: "linear-gradient(135deg, rgba(0,242,254,0.08), rgba(246,38,129,0.08))" }}>
                      <div className="text-xs text-[#9BA3C2] mb-2 font-medium uppercase tracking-wide">Overall Score</div>
                      <div className={cn("text-5xl font-bold", scoreColor(view.scores.overall))}>
                        {view.scores.overall.toFixed(2)}
                      </div>
                    </div>
                  </>
                )}

                {view.per_question_results && view.per_question_results.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-[#1A1B41] mb-3">Per-question breakdown</h3>
                    <div className="glass-strong rounded-xl overflow-hidden">
                      <table className="w-full text-xs">
                        <thead className="text-[#5B5C8A] border-b border-purple-100" style={{ background: "rgba(255,255,255,0.60)" }}>
                          <tr>
                            <th className="text-left font-semibold px-3 py-2">#</th>
                            <th className="text-left font-semibold px-3 py-2">Question</th>
                            <th className="text-center font-semibold px-2 py-2">Src</th>
                            <th className="text-right font-semibold px-2 py-2">ms</th>
                            <th className="text-center font-semibold px-2 py-2">F</th>
                            <th className="text-center font-semibold px-2 py-2">AR</th>
                            <th className="text-center font-semibold px-2 py-2">CP</th>
                            <th className="text-center font-semibold px-2 py-2">CR</th>
                          </tr>
                        </thead>
                        <tbody>
                          {view.per_question_results.map((q, i) => (
                            <PerQuestionRow key={i} index={i + 1} q={q} />
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function MetricCard({ label, score, threshold, verdict }: {
  label: string; score: number; threshold: number; verdict: string;
}) {
  return (
    <div className="glass-strong rounded-xl p-4">
      <div className="text-xs text-[#9BA3C2] font-medium">{label}</div>
      <div className="flex items-end justify-between mt-1">
        <div className={cn("text-2xl font-bold", scoreColor(score))}>{score.toFixed(2)}</div>
        <span className={cn(
          "text-[10px] font-semibold px-2 py-0.5 rounded-full border",
          verdict === "pass"
            ? "bg-emerald-50 text-emerald-600 border-emerald-200"
            : "bg-red-50 text-red-500 border-red-200",
        )}>
          {verdict}
        </span>
      </div>
      <div className="mt-2 h-1.5 bg-purple-100 rounded-full overflow-hidden relative">
        <div className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-500 rounded-full" style={{ width: `${score * 100}%` }} />
        <div className="absolute top-0 w-0.5 h-full bg-purple-400" style={{ left: `${threshold * 100}%` }} />
      </div>
      <div className="text-[10px] text-[#9BA3C2] mt-1.5">Threshold: {threshold.toFixed(2)}</div>
    </div>
  );
}

function ScoreDot({ score }: { score: number }) {
  const color = score >= 0.8 ? "bg-emerald-400" : score >= 0.6 ? "bg-amber-400" : "bg-red-400";
  return (
    <td className="px-2 py-2 text-center">
      <span className={cn("inline-block h-2 w-2 rounded-full", color)} title={score.toFixed(2)} />
    </td>
  );
}

function PerQuestionRow({ index, q }: { index: number; q: PerQuestion }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr onClick={() => setOpen((v) => !v)} className="border-t border-purple-100 cursor-pointer hover:bg-purple-50/60 transition-colors">
        <td className="px-3 py-2 text-[#9BA3C2]">{index}</td>
        <td className="px-3 py-2 text-[#1A1B41] max-w-[200px]">
          <div className="flex items-center gap-1 truncate">
            {open ? <ChevronUp className="h-3 w-3 text-[#9BA3C2] shrink-0" /> : <ChevronDown className="h-3 w-3 text-[#9BA3C2] shrink-0" />}
            <span className="truncate">{q.question}</span>
          </div>
        </td>
        <td className="px-2 py-2 text-center">
          {q.source_found
            ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 inline" />
            : <XCircle className="h-3.5 w-3.5 text-red-400 inline" />}
        </td>
        <td className="px-2 py-2 text-right text-[#5B5C8A]">{q.latency_ms}</td>
        <ScoreDot score={q.faithfulness} />
        <ScoreDot score={q.answer_relevancy} />
        <ScoreDot score={q.context_precision} />
        <ScoreDot score={q.context_recall} />
      </tr>
      {open && (
        <tr className="border-t border-purple-100 bg-purple-50/50">
          <td colSpan={8} className="px-4 py-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-[10px] text-[#9BA3C2] uppercase font-semibold mb-1">Expected</div>
                <div className="text-slate-600 text-xs">{q.expected_answer}</div>
              </div>
              <div>
                <div className="text-[10px] text-[#9BA3C2] uppercase font-semibold mb-1">Generated</div>
                <div className="text-slate-600 text-xs">{q.generated_answer}</div>
              </div>
            </div>
            {q.source_section && (
              <div className="text-[10px] text-[#9BA3C2] mt-2">Source: {q.source_section}</div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
