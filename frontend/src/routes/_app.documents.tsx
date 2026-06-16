import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Upload, Eye, Trash2, FileText, FileX, Copy, Info, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { StatusBadge } from "@/components/StatusBadge";
import {
  listDocuments, uploadDocument, deleteDocument, getDocument, getJobStatus,
  type DocRead, type DocDetailRead,
} from "@/lib/api/documents";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from "@/components/ui/tooltip";

export const Route = createFileRoute("/_app/documents")({
  head: () => ({ meta: [{ title: "Documents — Knowledge Assistant" }] }),
  beforeLoad: () => {
    const raw = localStorage.getItem("user");
    const user = raw ? (JSON.parse(raw) as { role?: string }) : null;
    if (user?.role !== "admin") throw redirect({ to: "/dashboard" });
  },
  component: DocumentsPage,
});

/* ── Neon orbital loader ── */
function NeonLoader() {
  const ring = (inset: number, color: string, glowColor: string, dir: string, dur: string): React.CSSProperties => ({
    position: "absolute",
    inset,
    borderRadius: "50%",
    border: "2.5px solid transparent",
    borderTopColor: color,
    borderRightColor: dir === "cw" ? `${glowColor}55` : "transparent",
    borderLeftColor: dir === "ccw" ? `${glowColor}55` : "transparent",
    boxShadow: `0 0 10px ${glowColor}66`,
    animation: `orbit-${dir} ${dur} linear infinite`,
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "80px 0", gap: 22 }}>
      <div style={{ position: "relative", width: 76, height: 76 }}>
        <div style={ring(0,  "#00F2FE", "#00F2FE", "cw",  "1.4s")} />
        <div style={ring(10, "#F62681", "#F62681", "ccw", "0.95s")} />
        <div style={ring(20, "#A78BFA", "#A78BFA", "cw",  "0.62s")} />
        <div style={{
          position: "absolute", inset: 30, borderRadius: "50%",
          background: "linear-gradient(135deg, #00F2FE, #F62681)",
          boxShadow: "0 0 14px rgba(0,242,254,0.70), 0 0 28px rgba(246,38,129,0.50)",
          animation: "loader-pulse 1.1s ease-in-out infinite",
        }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 9 }}>
        <p style={{
          color: "#5B5C8A", fontSize: 11, fontWeight: 700,
          letterSpacing: "0.12em", textTransform: "uppercase",
          animation: "loader-text-fade 1.8s ease-in-out infinite",
        }}>
          Loading Documents
        </p>
        <div style={{ display: "flex", gap: 6 }}>
          {(["#00F2FE", "#A78BFA", "#F62681"] as const).map((col, i) => (
            <div key={col} style={{
              width: 5, height: 5, borderRadius: "50%", background: col,
              boxShadow: `0 0 7px ${col}cc`,
              animation: `loader-pulse 0.9s ease-in-out ${i * 0.22}s infinite`,
            }} />
          ))}
        </div>
      </div>
    </div>
  );
}

function fmtBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1048576).toFixed(1)} MB`;
}

interface ProgressEntry { jobId: string; progress: number; message: string }

function DocumentsPage() {
  const navigate = useNavigate();
  const [docs, setDocs] = useState<DocRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewDocId, setViewDocId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DocDetailRead | null>(null);
  const [deleteDoc, setDeleteDoc] = useState<DocRead | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [pickedFiles, setPickedFiles] = useState<File[]>([]);
  const [description, setDescription] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<Record<string, ProgressEntry>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollTimers = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const fetchDocs = () =>
    listDocuments()
      .then((r) => setDocs(r.documents))
      .catch(() => toast.error("Failed to load documents"))
      .finally(() => setLoading(false));

  useEffect(() => {
    fetchDocs();
    return () => { Object.values(pollTimers.current).forEach(clearInterval); };
  }, []);

  const startPolling = (docId: string, jobId: string) => {
    if (pollTimers.current[docId]) return;
    pollTimers.current[docId] = setInterval(async () => {
      try {
        const job = await getJobStatus(jobId);
        setProgress((p) => ({
          ...p,
          [docId]: { jobId, progress: job.progress, message: job.message ?? "" },
        }));
        if (job.status === "completed" || job.status === "failed") {
          clearInterval(pollTimers.current[docId]);
          delete pollTimers.current[docId];
          setProgress((p) => { const n = { ...p }; delete n[docId]; return n; });
          await fetchDocs();
          if (job.status === "completed") toast.success("Document is ready to query!");
          else toast.error(`Processing failed: ${job.error_message ?? "unknown error"}`);
        }
      } catch { /* ignore */ }
    }, 2000);
  };

  const handleUpload = async () => {
    if (pickedFiles.length === 0) { toast.error("Please select at least one PDF file"); return; }
    setUploading(true);
    let successCount = 0;
    for (const file of pickedFiles) {
      try {
        const res = await uploadDocument(file, description || undefined);
        setProgress((p) => ({
          ...p,
          [res.doc_id]: { jobId: res.job_id, progress: 0, message: "Queued..." },
        }));
        startPolling(res.doc_id, res.job_id);
        successCount++;
      } catch (err) {
        toast.error(`${file.name}: ${err instanceof Error ? err.message : "Upload failed"}`);
      }
    }
    if (successCount > 0) {
      toast.success(`${successCount} document${successCount > 1 ? "s" : ""} queued for processing`);
      setUploadOpen(false);
      setPickedFiles([]);
      setDescription("");
      await fetchDocs();
    }
    setUploading(false);
  };

  const handleDelete = async () => {
    if (!deleteDoc) return;
    setDeleting(true);
    try {
      await deleteDocument(deleteDoc.doc_id);
      setDocs((prev) => prev.filter((d) => d.doc_id !== deleteDoc.doc_id));
      toast.success(`Deleted ${deleteDoc.filename}`);
      setDeleteDoc(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  };

  const openDetail = async (docId: string) => {
    setViewDocId(docId);
    setDetail(null);
    try {
      const d = await getDocument(docId);
      setDetail(d);
    } catch {
      toast.error("Failed to load document details");
    }
  };

  const processingEntries = Object.entries(progress);

  return (
    <TooltipProvider>
      <div className="space-y-6 max-w-7xl">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-[#1A1B41]">Documents</h1>
            <p className="text-sm text-[#5B5C8A] mt-1">Upload PDFs to build your knowledge base.</p>
          </div>
          <button
            onClick={() => setUploadOpen(true)}
            className="text-white px-4 py-2 rounded-xl text-sm font-semibold active:scale-95 transition-all flex items-center gap-2 neon-gradient" style={{ background: "linear-gradient(135deg, #00F2FE, #F62681)" }}
          >
            <Upload className="h-4 w-4" />
            Upload PDF
          </button>
        </header>

        {processingEntries.map(([docId, entry]) => (
          <div key={docId} className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-indigo-500" />
                <div className="text-sm font-medium text-slate-800">
                  {docs.find((d) => d.doc_id === docId)?.filename ?? "Processing..."}
                </div>
              </div>
              <StatusBadge status="processing" />
            </div>
            <div className="h-2 bg-purple-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-500 ease-out rounded-full"
                style={{ width: `${entry.progress}%` }}
              />
            </div>
            <div className="flex items-center justify-between mt-2">
              <div className="text-xs text-[#9BA3C2]">{entry.message}</div>
              <div className="text-xs text-slate-600 font-semibold">{entry.progress}%</div>
            </div>
          </div>
        ))}

        {loading ? (
          <NeonLoader />
        ) : docs.length === 0 ? (
          <div className="glass rounded-xl p-12 flex flex-col items-center text-center">
            <div className="h-16 w-16 rounded-2xl flex items-center justify-center mb-4" style={{ background: "rgba(255,255,255,0.50)" }}>
              <FileX className="h-8 w-8 text-slate-300" />
            </div>
            <h3 className="text-base font-semibold text-[#1A1B41]">No documents yet</h3>
            <p className="text-sm text-[#9BA3C2] mt-1 mb-5">Upload your first PDF to get started</p>
            <button
              onClick={() => setUploadOpen(true)}
              className="text-white px-4 py-2 rounded-xl text-sm font-semibold active:scale-95 transition-all flex items-center gap-2 neon-gradient" style={{ background: "linear-gradient(135deg, #00F2FE, #F62681)" }}
            >
              <Upload className="h-4 w-4" />
              Upload PDF
            </button>
          </div>
        ) : (
          <div className="glass rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-[#5B5C8A] border-b border-purple-100" style={{ background: "rgba(255,255,255,0.55)" }}>
                  <tr>
                    <th className="text-left font-semibold px-6 py-3">Filename</th>
                    <th className="text-left font-semibold px-3 py-3">Status</th>
                    <th className="text-left font-semibold px-3 py-3">Pages</th>
                    <th className="text-left font-semibold px-3 py-3">Chunks</th>
                    <th className="text-left font-semibold px-3 py-3">Size</th>
                    <th className="text-left font-semibold px-3 py-3">Uploaded</th>
                    <th className="text-right font-semibold px-6 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((d) => (
                    <tr key={d.doc_id} className="border-t border-purple-100 hover:bg-purple-50/40 transition-colors">
                      <td className="px-6 py-3.5">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-indigo-400 shrink-0" />
                          <span className="text-[#1A1B41] truncate max-w-[280px]">{d.filename}</span>
                        </div>
                      </td>
                      <td className="px-3 py-3.5"><StatusBadge status={d.status} /></td>
                      <td className="px-3 py-3.5 text-[#5B5C8A]">{d.page_count ?? "—"}</td>
                      <td className="px-3 py-3.5 text-[#5B5C8A]">{d.chunk_count ?? "—"}</td>
                      <td className="px-3 py-3.5 text-[#5B5C8A]">{fmtBytes(d.size_bytes)}</td>
                      <td className="px-3 py-3.5 text-[#9BA3C2]">
                        {new Date(d.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-3.5">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => openDetail(d.doc_id)}
                            className="p-1.5 rounded-lg text-[#9BA3C2] hover:text-[#00F2FE] hover:bg-purple-50 transition-colors"
                          >
                            <Eye className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => setDeleteDoc(d)}
                            className="p-1.5 rounded-lg text-[#9BA3C2] hover:text-red-500 hover:bg-red-50 transition-colors"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Detail sheet */}
        <Sheet open={!!viewDocId} onOpenChange={(o) => !o && setViewDocId(null)}>
          <SheetContent className="glass-opaque text-[#1A1B41] w-full sm:max-w-md overflow-y-auto border-0">
            <SheetHeader>
              <SheetTitle className="text-[#1A1B41] flex items-center gap-2">
                <FileText className="h-4 w-4 text-indigo-500" />
                Document Details
              </SheetTitle>
              <SheetDescription className="text-[#5B5C8A]">
                {detail?.filename ?? "Loading..."}
              </SheetDescription>
            </SheetHeader>
            {!detail ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="h-5 w-5 animate-spin text-[#9BA3C2]" />
              </div>
            ) : (
              <div className="mt-6 space-y-5 px-4">
                <StatusBadge status={detail.status} />
                <div className="grid grid-cols-2 gap-4">
                  <Stat label="Pages" value={detail.page_count ?? "—"} />
                  <Stat label="Chunks" value={detail.chunk_count ?? "—"} />
                  <Stat label="Size" value={fmtBytes(detail.size_bytes)} />
                  <Stat label="Uploaded" value={new Date(detail.created_at).toLocaleDateString()} />
                </div>
                <div className="space-y-3 pt-2 border-t border-purple-100">
                  <InfoRow label="Parent chunks" value={detail.parent_chunks?.toString() ?? "—"} tooltip="Larger context chunks used for retrieval" />
                  <InfoRow label="Child chunks" value={detail.child_chunks?.toString() ?? "—"} tooltip="Smaller chunks used for fine-grained matching" />
                </div>
                <div className="pt-2 border-t border-purple-100">
                  <div className="text-xs text-[#9BA3C2] mb-2">SHA256</div>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-xs font-mono text-[#1A1B41] glass-strong rounded-lg px-3 py-2 truncate">
                      {detail.sha256}
                    </code>
                    <button
                      onClick={() => { navigator.clipboard?.writeText(detail.sha256); toast.success("Copied!"); }}
                      className="p-2 rounded-lg text-[#9BA3C2] hover:text-[#00F2FE] hover:bg-purple-50 transition-colors"
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
                <button
                  onClick={() => { setViewDocId(null); navigate({ to: "/chat" }); }}
                  className="w-full text-white px-4 py-2.5 rounded-xl text-sm font-semibold active:scale-95 transition-all neon-gradient" style={{ background: "linear-gradient(135deg, #00F2FE, #F62681)" }}
                >
                  Ask a Question
                </button>
              </div>
            )}
          </SheetContent>
        </Sheet>

        {/* Delete confirm */}
        <Dialog open={!!deleteDoc} onOpenChange={(o) => !o && setDeleteDoc(null)}>
          <DialogContent className="glass-opaque text-[#1A1B41] border-0">
            <DialogHeader>
              <DialogTitle className="text-[#1A1B41]">Delete document?</DialogTitle>
              <DialogDescription className="text-[#5B5C8A]">
                {deleteDoc?.filename} will be permanently removed from your knowledge base.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <button
                onClick={() => setDeleteDoc(null)}
                className="glass text-[#1A1B41] px-4 py-2 rounded-xl text-sm font-medium transition-colors hover:opacity-80"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-2 bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50 transition-colors"
              >
                {deleting && <Loader2 className="h-3 w-3 animate-spin" />}
                Delete
              </button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Upload sheet */}
        <Sheet open={uploadOpen} onOpenChange={(o) => { setUploadOpen(o); if (!o) { setPickedFiles([]); setDescription(""); } }}>
          <SheetContent className="glass-opaque text-[#1A1B41] w-full sm:max-w-md border-0">
            <SheetHeader>
              <SheetTitle className="text-[#1A1B41]">Upload PDF</SheetTitle>
              <SheetDescription className="text-[#5B5C8A]">
                Add a new document to your knowledge base.
              </SheetDescription>
            </SheetHeader>
            <div className="mt-6 space-y-4 px-4">
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-purple-200 hover:border-[#00F2FE] rounded-xl p-8 text-center cursor-pointer transition-colors hover:bg-purple-50/40"
              >
                {pickedFiles.length > 0 ? (
                  <div className="space-y-2">
                    {pickedFiles.map((f, i) => (
                      <div key={i} className="flex items-center justify-center gap-3">
                        <FileText className="h-5 w-5 text-indigo-500 shrink-0" />
                        <div className="text-left">
                          <div className="text-sm font-medium text-[#1A1B41]">{f.name}</div>
                          <div className="text-xs text-[#9BA3C2]">{fmtBytes(f.size)}</div>
                        </div>
                      </div>
                    ))}
                    <div className="text-xs text-[#9BA3C2] mt-2">Click to change selection</div>
                  </div>
                ) : (
                  <>
                    <Upload className="h-8 w-8 text-slate-300 mx-auto mb-3" />
                    <div className="text-sm font-medium text-slate-600">Click to select PDFs</div>
                    <div className="text-xs text-[#9BA3C2] mt-1">You can select multiple files</div>
                  </>
                )}
                <input ref={fileInputRef} type="file" accept=".pdf" multiple className="hidden" onChange={(e) => setPickedFiles(Array.from(e.target.files ?? []))} />
              </div>
              <div>
                <label className="text-xs font-medium text-[#5B5C8A] mb-1.5 block">Description (optional)</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  placeholder="Briefly describe this document..."
                  className="w-full glass rounded-xl px-3 py-2 text-sm text-[#1A1B41] focus:outline-none resize-none transition-all"
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => setUploadOpen(false)}
                  className="flex-1 glass text-[#1A1B41] px-4 py-2 rounded-xl text-sm font-medium transition-colors hover:opacity-80"
                >
                  Cancel
                </button>
                <button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="flex-1 flex items-center justify-center gap-2 disabled:opacity-60 text-white px-4 py-2 rounded-xl text-sm font-semibold active:scale-95 transition-all neon-gradient" style={{ background: "linear-gradient(135deg, #00F2FE, #F62681)" }}
                >
                  {uploading && <Loader2 className="h-4 w-4 animate-spin" />}
                  {uploading ? "Uploading…" : pickedFiles.length > 1 ? `Upload ${pickedFiles.length} Files` : "Start Upload"}
                </button>
              </div>
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </TooltipProvider>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="glass-strong rounded-xl p-3">
      <div className="text-xs text-[#9BA3C2]">{label}</div>
      <div className="text-sm font-semibold text-[#1A1B41] mt-1">{value}</div>
    </div>
  );
}

function InfoRow({ label, value, tooltip }: { label: string; value: string; tooltip: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-1.5 text-xs text-[#5B5C8A]">
        {label}
        <Tooltip>
          <TooltipTrigger asChild>
            <button className="text-slate-300 hover:text-[#5B5C8A] transition-colors">
              <Info className="h-3 w-3" />
            </button>
          </TooltipTrigger>
          <TooltipContent className="bg-slate-800 border-slate-700 text-white text-xs">
            {tooltip}
          </TooltipContent>
        </Tooltip>
      </div>
      <div className="text-sm font-medium text-[#1A1B41]">{value}</div>
    </div>
  );
}
