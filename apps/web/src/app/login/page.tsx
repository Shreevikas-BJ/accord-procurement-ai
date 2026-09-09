"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Layers3, ShieldCheck, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("buyer@apex.example");
  const [password, setPassword] = useState("Demo2026!accord");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand">
          <Layers3 size={26} /> accord<span>PROCUREMENT</span>
        </div>
        <div>
          <div className="eyebrow">A clearer way to buy</div>
          <h1>
            Turn supplier quotes
            <br />
            into confident
            <br />
            <em>decisions.</em>
          </h1>
          <p>
            Pricing, delivery, and supplier performance.
            <br />
            One workspace. Every decision grounded in evidence.
          </p>
          <div className="login-points">
            {[
              "Compare the complete cost",
              "Catch pricing and delivery risks",
              "Keep your team in control",
            ].map((t) => (
              <p key={t}>
                <Check size={17} />
                {t}
              </p>
            ))}
          </div>
        </div>
        <small>AI handles quote analysis. Your team makes the decision.</small>
      </section>
      <section className="login-form">
        <div className="login-box">
          <div className="eyebrow">APEX INDUSTRIAL MANUFACTURING</div>
          <h2>Welcome to your workspace</h2>
          <p className="muted">
            Sign in to review quotes and move decisions forward.
          </p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                await api("/auth/login", {
                  method: "POST",
                  body: JSON.stringify({ email, password }),
                });
                router.push("/");
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Email address
              <Input
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label>
              Password
              <Input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            {error && (
              <p role="alert" className="error-box">
                {error}
              </p>
            )}
            <Button disabled={busy} className="w-full" type="submit">
              {busy ? "Signing in…" : "Sign in"}
              <ArrowRight size={16} />
            </Button>
          </form>
          <div className="demo-note">
            <ShieldCheck size={19} />
            <div>
              <strong>Local demo workspace</strong>
              <p>
                Demo credentials are filled in. No API keys or cloud services
                required.
              </p>
              <small>
                Admin: admin@apex.example · Viewer: viewer@apex.example
                <br />
                Password for all demo users: Demo2026!accord
              </small>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
