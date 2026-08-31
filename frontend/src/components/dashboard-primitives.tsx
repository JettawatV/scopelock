export function money(value: number, signed = false) {
  const prefix = signed && value > 0 ? "+" : "";
  return `${prefix}${new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value)}`;
}

export function time(value?: string | null) {
  if (!value) return "Pending";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function humanize(value: string) {
  return value.toLowerCase().replaceAll("_", " ");
}

function statusTone(status: string) {
  if (["PASS", "COMPLETED", "APPROVED", "ACCEPTED", "SENT"].includes(status)) {
    return "status-positive";
  }
  if (["FAILED", "SEND_FAILED", "NEEDS_REVIEW", "REJECTED"].includes(status)) {
    return "status-negative";
  }
  if (["AWAITING_USER_REVIEW", "READY_TO_FINALIZE", "BUFFERED"].includes(status)) {
    return "status-action";
  }
  return "status-neutral";
}

export function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-extrabold uppercase tracking-[0.08em] ${statusTone(status)}`}
    >
      {humanize(status)}
    </span>
  );
}

export function EmptyState({ children }: { children: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--line)] bg-[var(--surface-soft)] px-5 py-8 text-center text-sm text-[var(--muted)]">
      {children}
    </div>
  );
}
