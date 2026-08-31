import { ArrowRight, CheckCircle2, LoaderCircle, Mail, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { OperatorApp, type ReviewerSession } from "@/components/operator-app";
import {
  clearReviewerSession,
  completeReviewerLink,
  loadReviewerConfig,
  pendingReviewerEmail,
  refreshReviewerToken,
  sendReviewerLink,
  storedReviewerToken,
  type FirebaseWebConfig,
  type ReviewerToken,
} from "@/lib/reviewer-auth";

function clearSignInCode(): void {
  const url = new URL(window.location.href);
  url.searchParams.delete("mode");
  url.searchParams.delete("oobCode");
  url.searchParams.delete("apiKey");
  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
}

export function ReviewerApp() {
  const [config, setConfig] = useState<FirebaseWebConfig | null>(null);
  const [session, setSession] = useState<ReviewerToken | null>(null);
  const [email, setEmail] = useState(() => pendingReviewerEmail());
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [linkReady, setLinkReady] = useState(false);

  const signInCode = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("mode") === "signIn" ? params.get("oobCode") : null;
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const loadedConfig = await loadReviewerConfig();
        if (!active) return;
        setConfig(loadedConfig);
        const stored = storedReviewerToken();
        if (stored && stored.expiresAt > Date.now() + 60_000) {
          setSession(stored);
          setBusy(false);
          return;
        }
        if (stored) {
          try {
            const refreshed = await refreshReviewerToken(loadedConfig, stored);
            if (active) setSession(refreshed);
          } catch {
            clearReviewerSession();
          }
        }
        if (active) setBusy(false);
      } catch (caught) {
        if (!active) return;
        setError(caught instanceof Error ? caught.message : "Reviewer sign-in is unavailable.");
        setBusy(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!session || !config) return;
    const refreshIn = Math.max(5_000, session.expiresAt - Date.now() - 60_000);
    const timer = window.setTimeout(() => {
      void refreshReviewerToken(config, session)
        .then(setSession)
        .catch(() => {
          clearReviewerSession();
          setSession(null);
          setError("Your reviewer session expired. Request a new email link to continue.");
        });
    }, refreshIn);
    return () => window.clearTimeout(timer);
  }, [config, session]);

  useEffect(() => {
    if (!signInCode || !config || session || !email.trim()) return;
    let active = true;
    setLinkReady(true);
    setBusy(true);
    void completeReviewerLink(config, email, signInCode)
      .then((next) => {
        if (!active) return;
        clearSignInCode();
        setSession(next);
        setMessage("Reviewer access verified.");
        setError(null);
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "This sign-in link is invalid or expired.");
      })
      .finally(() => {
        if (active) {
          setBusy(false);
          setLinkReady(false);
        }
      });
    return () => {
      active = false;
    };
  }, [config, email, session, signInCode]);

  const requestLink = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!config || !email.trim()) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (signInCode) {
        const next = await completeReviewerLink(config, email, signInCode);
        clearSignInCode();
        setSession(next);
        setMessage("Reviewer access verified.");
        return;
      }
      await sendReviewerLink(config, email);
      setMessage("Check your email for a secure reviewer link. You can close this page and return later.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The sign-in link could not be sent.");
    } finally {
      setBusy(false);
    }
  };

  if (session) {
    const reviewerSession: ReviewerSession = { token: session.token, email: session.email };
    return <OperatorApp view="overview" reviewerSession={reviewerSession} onReviewerSignOut={() => { clearReviewerSession(); setSession(null); setMessage(null); }} />;
  }

  return (
    <main className="reviewer-gate min-h-screen bg-white px-5 py-10 sm:px-8 sm:py-16">
      <section className="mx-auto flex min-h-[70vh] max-w-[520px] items-center">
        <div className="panel w-full p-7 sm:p-10">
          <div className="flex items-center gap-3">
            <span className="grid size-11 place-items-center rounded-xl bg-[var(--ink)] text-white"><ShieldCheck size={20} /></span>
            <div><p className="eyebrow">ScopeLock</p><p className="text-xs font-extrabold uppercase tracking-[0.16em] text-[var(--muted)]">Reviewer workspace</p></div>
          </div>
          <h1 className="mt-8 text-3xl font-black tracking-[-0.045em]">Open the demo workspace</h1>
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">Use your email to receive a password-free reviewer link. No operator API key or access to your personal inbox is required.</p>
          <div className="mt-6 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-4 text-sm leading-6 text-[var(--ink)]">
            <p className="font-extrabold">How the async demo works</p>
            <p className="mt-1 text-[var(--muted)]">After signing in, send your test requirement to the dedicated ScopeLock demo inbox. The dashboard only shows the project created from this signed-in email.</p>
          </div>
          <form className="mt-7 space-y-4" onSubmit={requestLink}>
            <label className="block"><span className="text-sm font-extrabold">Reviewer email</span><span className="relative mt-2 block"><Mail size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" /><input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" className="min-h-12 w-full rounded-lg border border-[var(--line-strong)] bg-white pl-10 pr-3 text-sm outline-none ring-offset-2 focus:border-[var(--ink)] focus:ring-2 focus:ring-[var(--line-dark)]" /></span></label>
            {signInCode && !email.trim() ? <p className="text-xs font-semibold text-[var(--muted)]">Enter the same email address that requested this sign-in link to finish.</p> : null}
            <button type="submit" disabled={busy || !config || linkReady} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-[var(--ink)] px-4 text-sm font-extrabold text-white hover:bg-black disabled:cursor-wait disabled:opacity-50">{busy ? <LoaderCircle size={17} className="animate-spin" /> : <ArrowRight size={17} />} {signInCode ? "Complete reviewer sign-in" : "Email me a sign-in link"}</button>
          </form>
          {message ? <p className="mt-5 flex items-start gap-2 rounded-lg border border-[var(--line)] bg-[var(--surface-muted)] px-4 py-3 text-sm font-bold"><CheckCircle2 size={17} className="mt-0.5 shrink-0" />{message}</p> : null}
          {error ? <p role="alert" className="mt-5 rounded-lg border border-[var(--line-dark)] bg-[var(--surface-muted)] px-4 py-3 text-sm font-bold text-[var(--ink)]">{error}</p> : null}
          <p className="mt-7 text-center text-xs font-semibold leading-5 text-[var(--muted)]">This is a scoped review session for the ScopeLock demo, not a Gmail client.</p>
        </div>
      </section>
    </main>
  );
}
