"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main id="main" className="error-page">
      <p className="eyebrow">ApplyOS</p>
      <h1>Let’s try that again.</h1>
      <p>
        The server couldn’t complete your request. Your saved information is
        still on your account.
      </p>
      <button onClick={reset}>Try again</button>
    </main>
  );
}
