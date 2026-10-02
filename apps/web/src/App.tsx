import { FormEvent, useEffect, useState } from "react";

const api = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
type Job = { id: string; batch_id: string; status: string; source_filename: string; reused: boolean };
type Profile = { source_name: string; row_count: number; field_profiles: Array<{ name: string; empty_count: number; distinct_count: number }> };
type Issue = { id: number; severity: string; code: string; detail: string };
type Mapping = { id: string; source_name: string; version: number; canonical_entity: string; status: string; created_by: string };

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${api}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: { message?: string } } | null;
    throw new Error(body?.detail?.message ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export default function App() {
  const [job, setJob] = useState<Job | null>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [sourceName, setSourceName] = useState("");
  const [sourceField, setSourceField] = useState("");
  const [targetField, setTargetField] = useState("");
  const [actor, setActor] = useState("");
  const [message, setMessage] = useState("Upload a synthetic CSV, XLSX, or XLSM file to begin.");
  const [busy, setBusy] = useState(false);

  async function load(batchId: string) {
    const [nextProfiles, nextIssues, nextMappings] = await Promise.all([
      get<Profile[]>(`/import-batches/${batchId}/source-profiles`),
      get<Issue[]>(`/import-batches/${batchId}/validation-issues`),
      get<Mapping[]>(`/import-batches/${batchId}/mapping-versions`),
    ]);
    setProfiles(nextProfiles); setIssues(nextIssues); setMappings(nextMappings);
    if (nextProfiles[0]) { setSourceName((value) => value || nextProfiles[0].source_name); setSourceField((value) => value || nextProfiles[0].field_profiles[0]?.name || ""); }
  }

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const timer = window.setInterval(() => {
      get<Job>(`/import-jobs/${job.id}`).then(async (next) => { setJob(next); if (!["queued", "running"].includes(next.status)) await load(next.batch_id); }).catch((error: unknown) => setMessage(error instanceof Error ? error.message : "Could not refresh status."));
    }, 1500);
    return () => window.clearInterval(timer);
  }, [job]);

  const selected = profiles.find((profile) => profile.source_name === sourceName);
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const file = new FormData(event.currentTarget).get("source");
    if (!(file instanceof File) || file.size === 0) return setMessage("Choose a non-empty source file.");
    setBusy(true);
    try { const form = new FormData(); form.append("source", file); const next = await get<Job>("/import-jobs", { method: "POST", body: form }); setJob(next); setProfiles([]); setIssues([]); setMappings([]); setMessage(next.reused ? "Existing active import reused." : "Import accepted; waiting for validation."); if (!["queued", "running"].includes(next.status)) await load(next.batch_id); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Upload failed."); }
    finally { setBusy(false); }
  }
  async function propose(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!job) return; setBusy(true);
    try { await get<Mapping>(`/import-batches/${job.batch_id}/mapping-versions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_name: sourceName, canonical_entity: "invoices", field_mappings: { [sourceField]: targetField }, actor }) }); await load(job.batch_id); setMessage("Draft mapping proposal created."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not create proposal."); }
    finally { setBusy(false); }
  }
  async function review(mapping: Mapping, decision: "approve" | "reject") {
    const reviewer = window.prompt("Reviewer identity", actor); if (!reviewer) return; setBusy(true);
    try { await get<Mapping>(`/mapping-versions/${mapping.id}/review-decisions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, actor: reviewer, note: "Reviewed in Sprint 1 UI" }) }); if (job) await load(job.batch_id); setMessage(`Mapping version ${mapping.version} ${decision}d.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not record decision."); }
    finally { setBusy(false); }
  }

  return <main>
    <p className="eyebrow">SPRINT 1 · IMPORT AND MAPPING REVIEW</p>
    <h1>Review source data before it becomes canonical.</h1>
    <p className="lede">Synthetic data only. Gate 1 controls real-data mapping activation and canonical promotion.</p>
    <p className="notice" role="status">{message}</p>
    <section><h2>1. Upload source</h2><form onSubmit={upload} className="form-row"><label>Source file <input name="source" type="file" accept=".csv,.xlsx,.xlsm" /></label><button disabled={busy}>{busy ? "Working…" : "Upload"}</button></form>{job && <p><strong>{job.source_filename}</strong> · <span data-testid="job-status">{job.status}</span>{job.reused ? " · reused" : ""}</p>}</section>
    {job && <section><h2>2. Validation evidence</h2>{profiles.map((profile) => <article key={profile.source_name} className="card"><h3>{profile.source_name} <small>{profile.row_count} rows</small></h3><ul>{profile.field_profiles.map((field) => <li key={field.name}>{field.name} · {field.empty_count} empty · {field.distinct_count} distinct</li>)}</ul></article>)}{issues.length > 0 && <ul className="issues">{issues.map((issue) => <li key={issue.id}><strong>{issue.severity}: {issue.code}</strong> — {issue.detail}</li>)}</ul>}{job.status === "awaiting_mapping" && profiles.length === 0 && <p>Loading profiles…</p>}</section>}
    {job?.status === "awaiting_mapping" && selected && <section><h2>3. Propose and review mapping</h2><form onSubmit={propose} className="form-grid"><label>Source <select value={sourceName} onChange={(event) => { setSourceName(event.target.value); setSourceField(""); }}><option value="">Select</option>{profiles.map((profile) => <option key={profile.source_name}>{profile.source_name}</option>)}</select></label><label>Source field <select value={sourceField} onChange={(event) => setSourceField(event.target.value)}><option value="">Select</option>{selected.field_profiles.map((field) => <option key={field.name}>{field.name}</option>)}</select></label><label>Canonical field <input value={targetField} onChange={(event) => setTargetField(event.target.value)} required /></label><label>Author <input value={actor} onChange={(event) => setActor(event.target.value)} required /></label><button disabled={busy || !sourceName || !sourceField}>Create draft</button></form><ul className="mappings">{mappings.map((mapping) => <li key={mapping.id}><strong>{mapping.source_name} v{mapping.version}</strong> → {mapping.canonical_entity} · {mapping.status} · {mapping.created_by}{mapping.status === "draft" && <span><button onClick={() => review(mapping, "approve")} disabled={busy}>Approve</button><button onClick={() => review(mapping, "reject")} disabled={busy}>Reject</button></span>}</li>)}</ul></section>}
    <footer>No model metrics or business outcomes are claimed in this build.</footer>
  </main>;
}
