"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowUpRight, Check } from "lucide-react";
import { api } from "@/lib/api";
import { stateSchema, userSchema } from "@/lib/contracts";

export function AuthForm({ signup = false }: { signup?: boolean }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await api(signup ? "/auth/signup" : "/auth/login", userSchema, {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
        }),
      });
      const state = await api("/onboarding", stateSchema);
      router.push(state.complete ? "/dashboard" : "/onboarding");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-grid">
      <aside className="auth-story">
        <Link className="wordmark" href="/">
          apply<span>os</span>
          <i>↗</i>
        </Link>
        <div>
          <p className="eyebrow light">
            A little clarity. A lot of possibility.
          </p>
          <h1>
            Your next chapter
            <br />
            <em>starts with you.</em>
          </h1>
          <p>
            A thoughtful home for your experience, your ambitions, and the
            opportunities ahead.
          </p>
          <ul>
            <li>
              <Check size={16} /> Your experience, accurately represented
            </li>
            <li>
              <Check size={16} /> Preferences that stay in your control
            </li>
            <li>
              <Check size={16} /> A job search with a clear next step
            </li>
          </ul>
        </div>
        <small>Built for the beginning of something good.</small>
      </aside>
      <main id="main" className="auth-main">
        <div className="auth-card">
          <p className="eyebrow">
            {signup ? "Make room for what’s next" : "Good to see you again"}
          </p>
          <h2>{signup ? "Start your workspace." : "Welcome back."}</h2>
          <p>
            {signup
              ? "Create an account, then bring your resume. We’ll help you review the details."
              : "Sign in to pick up where you left off."}
          </p>
          <form
            onSubmit={submit}
            aria-describedby={error ? "auth-error" : undefined}
          >
            <label>
              Email address
              <input
                name="email"
                type="email"
                autoComplete="email"
                required
                maxLength={320}
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete={signup ? "new-password" : "current-password"}
                required
                minLength={12}
                maxLength={128}
              />
            </label>
            <p className="hint">
              At least 12 characters. Spaces and passphrases are welcome.
            </p>
            {error && (
              <p className="error" id="auth-error" role="alert">
                {error}
              </p>
            )}
            <button disabled={busy} className="wide">
              {busy ? "One moment…" : signup ? "Create account" : "Sign in"}
              <ArrowUpRight size={18} />
            </button>
          </form>
          <p className="auth-switch">
            {signup ? "Already have an account?" : "New around here?"}{" "}
            <Link href={signup ? "/login" : "/signup"}>
              {signup ? "Sign in" : "Create an account"}
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
