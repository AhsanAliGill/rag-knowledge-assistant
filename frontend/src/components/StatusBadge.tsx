import { cn } from "@/lib/utils";

type Status = "pending" | "processing" | "ready" | "failed" | "completed" | "queued";

const styles: Record<Status, string> = {
  pending:    "bg-amber-100 text-amber-700 border-amber-300",
  processing: "bg-blue-100 text-blue-700 border-blue-300",
  ready:      "bg-emerald-100 text-emerald-700 border-emerald-300",
  failed:     "bg-red-100 text-red-600 border-red-300",
  completed:  "bg-emerald-100 text-emerald-700 border-emerald-300",
  queued:     "bg-slate-100 text-slate-600 border-slate-300",
};

export function StatusBadge({ status, className }: { status: Status; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border capitalize",
        styles[status],
        className,
      )}
    >
      {status === "processing" && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-500 opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-blue-500" />
        </span>
      )}
      {status}
    </span>
  );
}
