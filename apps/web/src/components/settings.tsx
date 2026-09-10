"use client";
import { useState } from "react";
import { Cpu, Database, ShieldCheck, Save, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, useResource } from "@/lib/api";
import { PageHeader, Loading, ErrorState, Notice } from "./shared";
import { useUser } from "./shell";
interface Settings {
  organization_name: string;
  currency: string;
  price_weight: number;
  lead_time_weight: number;
  reliability_weight: number;
  fit_weight: number;
  anomaly_threshold: string;
  lead_time_behavior: string;
  ai_mode: string;
  ai_model: string;
  ai_provider?: string;
  ai_connection?: string;
  ai_connection_detail?: string;
  ocr_provider: string;
  storage_provider: string;
}
export function SettingsPage() {
  const r = useResource<Settings>("/settings/scoring");
  if (r.error) return <ErrorState error={r.error} retry={r.reload} />;
  if (!r.data) return <Loading />;
  return <SettingsEditor initial={r.data} />;
}
function SettingsEditor({ initial }: { initial: Settings }) {
  const [settings, setSettings] = useState(initial),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const admin = useUser()?.role === "Admin";
  const weightKeys = [
    "price_weight",
    "lead_time_weight",
    "reliability_weight",
    "fit_weight",
  ] as const;
  const labels = [
    "Price",
    "Lead time",
    "Historical reliability",
    "Requirements fit",
  ];
  const total = weightKeys.reduce((sum, k) => sum + settings[k], 0);
  return (
    <>
      <PageHeader
        eyebrow="WORKSPACE SETTINGS"
        title="Make the criteria yours."
        description="Transparent rules keep every recommendation consistent."
      >
        <Button
          disabled={!admin || busy || total !== 100}
          onClick={async () => {
            setBusy(true);
            try {
              const keys = [
                "organization_name",
                "currency",
                ...weightKeys,
                "anomaly_threshold",
                "lead_time_behavior",
              ] as const;
              await api("/settings/scoring", {
                method: "PUT",
                body: JSON.stringify(
                  Object.fromEntries(keys.map((k) => [k, settings[k]])),
                ),
              });
              setMessage(
                "Settings saved. RFQ scores and alerts recalculated; previous recommendations marked stale.",
              );
            } catch (e) {
              setMessage((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <Save size={16} />
          Save settings
        </Button>
      </PageHeader>
      {message && <Notice text={message} onClose={() => setMessage("")} />}
      <div className="settings-grid">
        <div>
          <Card className="section-card">
            <div className="section-heading">
              <div>
                <h2>Supplier scoring</h2>
                <p>
                  Weights must total 100%. Blocking findings prevent eligibility
                  regardless of score.
                </p>
              </div>
            </div>
            <div className="settings-body">
              {weightKeys.map((k, i) => (
                <div className="weight-field" key={k}>
                  <label htmlFor={k}>{labels[i]}</label>
                  <div className="weight-track">
                    <i style={{ width: `${settings[k]}%` }} />
                  </div>
                  <Input
                    id={k}
                    type="number"
                    min="0"
                    max="100"
                    disabled={!admin}
                    value={settings[k]}
                    onChange={(e) =>
                      setSettings({ ...settings, [k]: Number(e.target.value) })
                    }
                  />
                  <span>%</span>
                </div>
              ))}
              <div
                className={`weight-total ${total !== 100 ? "inline-warning" : ""}`}
              >
                Total weighting <strong>{total}%</strong>
              </div>
              <label>
                Price increase alert threshold (%)
                <Input
                  type="number"
                  min="0"
                  max="100"
                  disabled={!admin}
                  value={Number(settings.anomaly_threshold) * 100}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      anomaly_threshold: String(Number(e.target.value) / 100),
                    })
                  }
                />
              </label>
              <p className="muted">
                Compared against the exact six-month average using Decimal
                arithmetic. An increase equal to the threshold triggers an
                alert.
              </p>
            </div>
          </Card>
          <Card className="section-card">
            <div className="section-heading">
              <h2>Organization</h2>
            </div>
            <div className="settings-body">
              <label>
                Company name
                <Input
                  disabled={!admin}
                  value={settings.organization_name}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      organization_name: e.target.value,
                    })
                  }
                />
              </label>
              <label>
                Default currency
                <Input
                  disabled={!admin}
                  maxLength={3}
                  value={settings.currency}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      currency: e.target.value.toUpperCase(),
                    })
                  }
                />
              </label>
              <p className="muted">
                Changing the default does not convert existing quotes. Different
                currencies require review.
              </p>
            </div>
          </Card>
          {admin && <UserManagement />}
        </div>
        <div>
          <Card className="section-card">
            <div className="section-heading">
              <h2>Processing providers</h2>
            </div>
            <div className="provider-list">
              <div>
                <Cpu size={20} />
                <div>
                  <strong>
                    {settings.ai_mode === "demo"
                      ? "DEMO MODE"
                      : settings.ai_mode === "local"
                        ? "LOCAL AI"
                        : "HOSTED AI"}
                  </strong>
                  <p>
                    {settings.ai_model || "Deterministic fixture extraction"}
                  </p>
                  {settings.ai_provider && (
                    <p>
                      {settings.ai_provider} · {settings.ai_connection}
                    </p>
                  )}
                  {settings.ai_connection_detail && (
                    <small>{settings.ai_connection_detail}</small>
                  )}
                </div>
                {settings.ai_connection !== "Unavailable" && (
                  <span className="live-dot" />
                )}
              </div>
              <div>
                <Database size={20} />
                <div>
                  <strong>{settings.storage_provider}</strong>
                  <p>Organization-scoped private documents</p>
                </div>
              </div>
              <div>
                <FileOCR />
                <div>
                  <strong>{settings.ocr_provider}</strong>
                  <p>Scanned PDF and image processing</p>
                </div>
              </div>
            </div>
            <div className="settings-body">
              <p className="muted">
                Provider mode is configured through environment variables. AI
                errors never bypass human review.
              </p>
            </div>
          </Card>
          <Card className="section-card">
            <div className="section-heading">
              <h2>Decision safeguards</h2>
            </div>
            <div className="settings-body">
              <p>
                <ShieldCheck size={18} />
                Human approval required
              </p>
              <p>
                Lead-time ranges use the maximum calendar-day estimate. Missing
                lead time requires review.
              </p>
              <p>
                Unknown costs and incomplete scope are excluded from
                recommendations. Currency conversion is not applied.
              </p>
              <p>
                Supplier emails are saved as drafts. No orders, payments, or
                supplier commitments are created.
              </p>
              <small>
                {admin
                  ? "You have administrator access."
                  : "Only administrators can change these settings."}
              </small>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
function FileOCR() {
  return <ShieldCheck size={20} />;
}
function UserManagement() {
  const [form, setForm] = useState({
      name: "",
      email: "",
      password: "",
      role: "Viewer",
    }),
    [message, setMessage] = useState("");
  const users =
    useResource<{ id: string; name: string; email: string; role: string }[]>(
      "/users",
    );
  return (
    <Card className="section-card">
      <div className="section-heading">
        <h2>
          <Users size={17} />
          Team access
        </h2>
      </div>
      <div className="settings-body">
        {users.data?.map((u) => (
          <div className="team-row" key={u.id}>
            <strong>{u.name}</strong>
            <span>{u.email}</span>
            <small>{u.role}</small>
          </div>
        ))}
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await api("/users", {
                method: "POST",
                body: JSON.stringify(form),
              });
              setMessage("User created.");
              users.reload();
              setForm({ name: "", email: "", password: "", role: "Viewer" });
            } catch (e) {
              setMessage((e as Error).message);
            }
          }}
        >
          {(["name", "email", "password"] as const).map((k) => (
            <label key={k}>
              {k}
              <Input
                type={
                  k === "password"
                    ? "password"
                    : k === "email"
                      ? "email"
                      : "text"
                }
                value={form[k]}
                minLength={k === "password" ? 12 : 2}
                required
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              />
            </label>
          ))}
          <label>
            Role
            <Select
              value={form.role}
              onValueChange={(role) => setForm({ ...form, role })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["Viewer", "Buyer", "Admin"].map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
          <Button type="submit" variant="outline">
            Add team member
          </Button>
          <p role="status">{message}</p>
        </form>
      </div>
    </Card>
  );
}
