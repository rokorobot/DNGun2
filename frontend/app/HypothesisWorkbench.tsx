"use client";

import { Check, ClipboardCopy, FlaskConical, GitBranch, Plus, Sparkles, Wand2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AcquisitionHypothesis,
  activateHypothesis,
  approveHypothesis,
  attachHypothesisEvidence,
  createHypothesis,
  DecisionMaker,
  detachHypothesisEvidence,
  EvidenceEntry,
  generateHypothesis,
  getHypothesis,
  getHypothesisAssistPrompt,
  HypothesisBinding,
  HypothesisDetail,
  listDecisionMakers,
  listEvidenceEntries,
  listHypotheses,
  Offer,
  proposeHypothesis,
  Prospect,
  rejectHypothesis,
  submitHypothesisAssist,
  supersedeHypothesis,
  updateDraftHypothesis
} from "../lib/api";

// MVP 1.3A-5 Hypothesis Workbench. Every rule is enforced by the backend;
// this view only collects input and shows the backend's answer or refusal.

const input = "h-9 w-full border border-[#293733] bg-[#121516] px-2 text-sm text-white";
const area = "w-full border border-[#293733] bg-[#121516] p-2 text-sm text-white";
const label = "mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]";
const button = (tone: "green" | "cyan" | "amber" | "red" | "gray") => {
  const tones = {
    green: "border-[#00a85f] bg-[#06351f] text-[#00e084]",
    cyan: "border-[#00a9d6] bg-[#062633] text-[#00c8ff]",
    amber: "border-[#a8740a] bg-[#2b1f05] text-[#ffb020]",
    red: "border-[#8f3d32] bg-[#24110f] text-[#ff7a6b]",
    gray: "border-[#293733] bg-[#101516] text-[#aebbb4]"
  };
  return `inline-flex h-9 items-center justify-center gap-2 border px-3 font-mono text-xs uppercase disabled:opacity-40 ${tones[tone]}`;
};

const statusTone: Record<string, string> = {
  DRAFT: "text-[#00c8ff] border-[#00a9d6]",
  PROPOSED: "text-[#ffb020] border-[#a8740a]",
  APPROVED: "text-[#00e084] border-[#00a85f]",
  REJECTED: "text-[#ff7a6b] border-[#8f3d32]",
  SUPERSEDED: "text-[#74837c] border-[#293733]"
};

function Badge({ text, tone }: { text: string; tone?: string }) {
  return (
    <span className={`border px-1.5 py-0.5 font-mono text-[10px] uppercase ${tone ?? "border-[#293733] text-[#aebbb4]"}`}>
      {text}
    </span>
  );
}

function Box({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="border border-[#1d2825] bg-[#0b0f10]">
      <div className="flex items-center gap-2 border-b border-[#1d2825] px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.14em] text-white">
        <span className="text-[#00d277]">{icon}</span>
        {title}
      </div>
      <div className="space-y-3 p-4">{children}</div>
    </section>
  );
}

function errorText(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  try {
    const detail = JSON.parse(raw).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => item.msg ?? JSON.stringify(item)).join("; ");
  } catch {
    // not JSON; fall through
  }
  return raw;
}

export default function HypothesisWorkbench({ offers, prospects }: { offers: Offer[]; prospects: Prospect[] }) {
  const [offerId, setOfferId] = useState("");
  const [prospectId, setProspectId] = useState("");
  const [hypotheses, setHypotheses] = useState<AcquisitionHypothesis[]>([]);
  const [selected, setSelected] = useState<HypothesisDetail | null>(null);
  const [decisionMakers, setDecisionMakers] = useState<DecisionMaker[]>([]);
  const [evidence, setEvidence] = useState<EvidenceEntry[]>([]);
  const [notice, setNotice] = useState<{ text: string; ok: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  // New-draft inputs, shared by human create, generator, and AI assist.
  const [statement, setStatement] = useState("");
  const [framing, setFraming] = useState("");
  const [dmId, setDmId] = useState("");
  const [parentId, setParentId] = useState("");
  // AI assist
  const [prompt, setPrompt] = useState("");
  const [pasted, setPasted] = useState("");
  const [modelLabel, setModelLabel] = useState("");

  const detailRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (selected?.id) detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [selected?.id]);

  const ready = Boolean(offerId && prospectId);
  const binding = (): HypothesisBinding => ({
    ...(dmId ? { decision_maker_id: dmId } : {}),
    ...(parentId ? { refines_hypothesis_id: parentId } : {})
  });

  const refresh = useCallback(
    async (selectId?: string) => {
      if (!offerId || !prospectId) return;
      const list = await listHypotheses(offerId, prospectId);
      setHypotheses(list);
      const id = selectId ?? selected?.id;
      setSelected(id && list.some((h) => h.id === id) ? await getHypothesis(id) : null);
    },
    [offerId, prospectId, selected?.id]
  );

  useEffect(() => {
    if (!offerId && offers[0]) setOfferId(offers[0].id);
    if (!prospectId && prospects[0]) setProspectId(prospects[0].id);
  }, [offers, prospects, offerId, prospectId]);

  useEffect(() => {
    setSelected(null);
    setPrompt("");
    setDmId("");
    setParentId("");
    if (!offerId || !prospectId) return;
    void listHypotheses(offerId, prospectId).then(setHypotheses).catch((e) => setNotice({ text: errorText(e), ok: false }));
    void listDecisionMakers(prospectId).then(setDecisionMakers).catch(() => setDecisionMakers([]));
    void listEvidenceEntries().then(setEvidence).catch(() => setEvidence([]));
  }, [offerId, prospectId]);

  async function run(action: () => Promise<unknown>, success: string, selectId?: (result: unknown) => string | undefined) {
    setBusy(true);
    setNotice(null);
    try {
      const result = await action();
      await refresh(selectId?.(result));
      setNotice({ text: success, ok: true });
      return true;
    } catch (error) {
      setNotice({ text: errorText(error), ok: false });
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function copyPrompt() {
    setBusy(true);
    setNotice(null);
    try {
      const result = await getHypothesisAssistPrompt(offerId, prospectId, dmId || undefined);
      setPrompt(result.prompt);
      try {
        await navigator.clipboard.writeText(result.prompt);
        setNotice({ text: "Prompt copied. Paste it into claude.ai, then paste Claude's answer below.", ok: true });
      } catch {
        setNotice({ text: "Prompt ready below. Select it and copy it into claude.ai.", ok: true });
      }
    } catch (error) {
      setNotice({ text: errorText(error), ok: false });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <Box title="Hypothesis Workbench" icon={<FlaskConical size={15} />}>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="block">
            <span className={label}>Offer</span>
            <select className={input} onChange={(e) => setOfferId(e.target.value)} value={offerId}>
              {offers.length === 0 ? <option value="">No offers yet</option> : null}
              {offers.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className={label}>Prospect</span>
            <select className={input} onChange={(e) => setProspectId(e.target.value)} value={prospectId}>
              {prospects.length === 0 ? <option value="">No prospects yet</option> : null}
              {prospects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.company_name} ({p.segment})
                </option>
              ))}
            </select>
          </label>
        </div>
        {notice ? (
          <div
            className={`border p-3 text-sm ${notice.ok ? "border-[#00a85f] bg-[#06231a] text-[#9ff0c8]" : "border-[#8f3d32] bg-[#24110f] text-[#ffad99]"}`}
            role="status"
          >
            {notice.text}
          </div>
        ) : null}
      </Box>

      <div className="space-y-3">
        <div className="grid gap-3 lg:grid-cols-2">
          <Box title="New draft" icon={<Plus size={15} />}>
            <div className="grid gap-3">
              <label className="block">
                <span className={label}>Decision maker (optional)</span>
                <select className={input} onChange={(e) => setDmId(e.target.value)} value={dmId}>
                  <option value="">Company-level</option>
                  {decisionMakers.map((dm) => (
                    <option key={dm.id} value={dm.id}>
                      {dm.name}, {dm.role}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className={label}>Refines (needed with a decision maker)</span>
                <select className={input} onChange={(e) => setParentId(e.target.value)} value={parentId}>
                  <option value="">None</option>
                  {hypotheses
                    .filter((h) => !h.decision_maker_id)
                    .map((h) => (
                      <option key={h.id} value={h.id}>
                        {h.id} · {h.status}
                      </option>
                    ))}
                </select>
              </label>
            </div>
            <label className="block">
              <span className={label}>Statement (write your own)</span>
              <textarea className={area} onChange={(e) => setStatement(e.target.value)} rows={3} value={statement} />
            </label>
            <label className="block">
              <span className={label}>Recipient framing (optional)</span>
              <input className={input} onChange={(e) => setFraming(e.target.value)} value={framing} />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                className={button("green")}
                disabled={!ready || busy || !statement.trim()}
                onClick={async () => {
                  const ok = await run(
                    () =>
                      createHypothesis(offerId, prospectId, {
                        statement: statement.trim(),
                        ...(framing.trim() ? { recipient_framing: framing.trim() } : {}),
                        ...binding()
                      }),
                    "Draft created.",
                    idOf
                  );
                  if (ok) {
                    setStatement("");
                    setFraming("");
                  }
                }}
                type="button"
              >
                <Plus size={14} /> Create draft
              </button>
              <button
                className={button("cyan")}
                disabled={!ready || busy}
                onClick={() => void run(() => generateHypothesis(offerId, prospectId, binding()), "Rule-based draft generated.", idOf)}
                type="button"
              >
                <Wand2 size={14} /> Generate (rules)
              </button>
            </div>
          </Box>

          <Box title="AI assist · your Claude chat" icon={<Sparkles size={15} />}>
            <p className="text-xs leading-5 text-[#aebbb4]">
              1. Copy the prompt. 2. Paste it into claude.ai. 3. Paste Claude&apos;s whole answer here. Uses the decision maker
              and parent chosen above. No API key needed.
            </p>
            <button className={button("cyan")} disabled={!ready || busy} onClick={() => void copyPrompt()} type="button">
              <ClipboardCopy size={14} /> Copy prompt
            </button>
            {prompt ? <textarea className={`${area} font-mono text-xs`} readOnly rows={6} value={prompt} /> : null}
            <label className="block">
              <span className={label}>Claude&apos;s answer</span>
              <textarea className={`${area} font-mono text-xs`} onChange={(e) => setPasted(e.target.value)} rows={5} value={pasted} />
            </label>
            <label className="block">
              <span className={label}>Model label (optional)</span>
              <input className={input} onChange={(e) => setModelLabel(e.target.value)} placeholder="e.g. Claude Opus" value={modelLabel} />
            </label>
            <button
              className={button("green")}
              disabled={!ready || busy || !pasted.trim()}
              onClick={async () => {
                const ok = await run(
                  () =>
                    submitHypothesisAssist(offerId, prospectId, {
                      response: pasted,
                      ...(modelLabel.trim() ? { model: modelLabel.trim() } : {}),
                      ...binding()
                    }),
                  "AI-assisted draft saved. Review it before proposing.",
                  idOf
                );
                if (ok) setPasted("");
              }}
              type="button"
            >
              <Check size={14} /> Save AI draft
            </button>
          </Box>
        </div>

          <Box title={`Hypotheses · ${hypotheses.length}`} icon={<GitBranch size={15} />}>
            {hypotheses.length === 0 ? <p className="text-sm text-[#74837c]">None yet for this offer and prospect.</p> : null}
            {hypotheses.map((h) => (
              <button
                className={`w-full border p-3 text-left ${selected?.id === h.id ? "border-[#00d277] bg-[#082316]" : "border-[#293733] bg-[#101516]"}`}
                key={h.id}
                onClick={() => void getHypothesis(h.id).then(setSelected)}
                type="button"
              >
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-mono text-[11px] text-[#dce8e1]">{h.id}</span>
                  <Badge text={h.status} tone={statusTone[h.status]} />
                  {h.is_active ? <Badge text="active" tone="border-[#00d277] bg-[#082316] text-[#00e084]" /> : null}
                  <Badge text={h.source.replace("_", " ")} />
                  {h.decision_maker_id ? <Badge text="refinement" /> : null}
                  <span className="ml-auto font-mono text-[11px] text-[#74837c]">
                    {h.reasoning_confidence === null ? "conf –" : `conf ${h.reasoning_confidence}`}
                  </span>
                </div>
                <div className="mt-2 line-clamp-2 text-sm text-[#aebbb4]">{h.statement}</div>
              </button>
            ))}
          </Box>

        <div ref={detailRef}>
        {selected ? (
          <HypothesisDetailPane
            busy={busy}
            detail={selected}
            evidence={evidence}
            run={run}
          />
        ) : (
          <Box title="Detail" icon={<FlaskConical size={15} />}>
            <p className="text-sm text-[#74837c]">Select a hypothesis to review it.</p>
          </Box>
        )}
        </div>
      </div>
    </div>
  );
}

function HypothesisDetailPane({
  detail,
  evidence,
  busy,
  run
}: {
  detail: HypothesisDetail;
  evidence: EvidenceEntry[];
  busy: boolean;
  run: (action: () => Promise<unknown>, success: string, selectId?: (result: unknown) => string | undefined) => Promise<boolean>;
}) {
  const [editStatement, setEditStatement] = useState(detail.statement);
  const [editFraming, setEditFraming] = useState(detail.recipient_framing ?? "");
  const [attachId, setAttachId] = useState("");
  const [attachNote, setAttachNote] = useState("");
  const [assessment, setAssessment] = useState("");
  const [reviewNotes, setReviewNotes] = useState("");
  const [successor, setSuccessor] = useState("");

  useEffect(() => {
    setEditStatement(detail.statement);
    setEditFraming(detail.recipient_framing ?? "");
    setAttachId("");
    setAttachNote("");
    setSuccessor("");
  }, [detail.id, detail.statement, detail.recipient_framing]);

  const isDraft = detail.status === "DRAFT";
  const linked = new Set(detail.evidence_links.map((l) => l.evidence_entry_id));
  const attachable = evidence.filter((e) => (e.status ?? "ACTIVE") === "ACTIVE" && !linked.has(e.id));
  const keep = () => detail.id;

  return (
    <Box title={`Detail · ${detail.id}`} icon={<FlaskConical size={15} />}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge text={detail.status} tone={statusTone[detail.status]} />
        {detail.is_active ? <Badge text="active outreach hypothesis" tone="border-[#00d277] bg-[#082316] text-[#00e084]" /> : null}
        <Badge text={`source: ${detail.source}`} />
        {detail.provider ? <Badge text={`via ${detail.provider}${detail.model ? ` · ${detail.model}` : ""}`} /> : null}
        {detail.reviewer_assessment ? <Badge text={`reviewer: ${detail.reviewer_assessment}`} /> : null}
        {detail.superseded_by_id ? <Badge text={`superseded by ${detail.superseded_by_id}`} /> : null}
      </div>

      <div className={`grid gap-3 ${detail.parent ? "md:grid-cols-2" : ""}`}>
        {detail.parent ? (
          <div className="border border-[#293733] bg-[#101516] p-3">
            <div className={label}>Parent {detail.parent.id} · {detail.parent.status}</div>
            <div className="text-sm leading-5 text-[#aebbb4]">{detail.parent.statement}</div>
          </div>
        ) : null}
        <div className="border border-[#293733] bg-[#101516] p-3">
          <div className={label}>Statement{isDraft ? " (editable while DRAFT)" : " (frozen)"}</div>
          {isDraft ? (
            <textarea className={area} onChange={(e) => setEditStatement(e.target.value)} rows={4} value={editStatement} />
          ) : (
            <div className="text-sm leading-5 text-[#dce8e1]">{detail.statement}</div>
          )}
          <div className={`${label} mt-3`}>Recipient framing</div>
          {isDraft ? (
            <input className={input} onChange={(e) => setEditFraming(e.target.value)} value={editFraming} />
          ) : (
            <div className="text-sm text-[#dce8e1]">{detail.recipient_framing ?? "—"}</div>
          )}
          {isDraft ? (
            <button
              className={`${button("gray")} mt-3`}
              disabled={busy || !editStatement.trim()}
              onClick={() =>
                void run(
                  () =>
                    updateDraftHypothesis(detail.id, {
                      statement: editStatement.trim(),
                      recipient_framing: editFraming.trim() || null
                    }),
                  "Draft saved.",
                  keep
                )
              }
              type="button"
            >
              Save draft
            </button>
          ) : null}
        </div>
      </div>

      <div>
        <div className={label}>Evidence · {detail.evidence_links.length} linked</div>
        <div className="space-y-2">
          {detail.evidence_links.length === 0 ? (
            <p className="text-sm text-[#ffb020]">No evidence linked. A hypothesis without evidence cannot be approved.</p>
          ) : null}
          {detail.evidence_links.map((link) => (
            <div className="flex items-start gap-2 border border-[#202c28] bg-[#101516] p-2" key={link.id}>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-mono text-[11px] text-[#dce8e1]">{link.evidence_entry_id}</span>
                  <Badge
                    text={link.evidence.status ?? "ACTIVE"}
                    tone={(link.evidence.status ?? "ACTIVE") === "ACTIVE" ? "border-[#00a85f] text-[#00e084]" : "border-[#8f3d32] text-[#ff7a6b]"}
                  />
                  <Badge text={link.evidence.evidence_type} />
                </div>
                <div className="mt-1 text-sm text-[#aebbb4]">{link.evidence.evidence}</div>
                {link.note ? <div className="mt-1 text-xs text-[#74837c]">{link.note}</div> : null}
              </div>
              {isDraft ? (
                <button
                  aria-label={`Unlink ${link.evidence_entry_id}`}
                  className={button("red")}
                  disabled={busy}
                  onClick={() => void run(() => detachHypothesisEvidence(detail.id, link.evidence_entry_id), "Evidence unlinked.", keep)}
                  type="button"
                >
                  <X size={14} />
                </button>
              ) : null}
            </div>
          ))}
        </div>
        {isDraft ? (
          <div className="mt-2 grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
            <select className={input} onChange={(e) => setAttachId(e.target.value)} value={attachId}>
              <option value="">Link ACTIVE evidence…</option>
              {attachable.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.id} · {e.evidence.slice(0, 60)}
                </option>
              ))}
            </select>
            <input className={input} onChange={(e) => setAttachNote(e.target.value)} placeholder="Why it supports the claim" value={attachNote} />
            <button
              className={button("cyan")}
              disabled={busy || !attachId}
              onClick={() => void run(() => attachHypothesisEvidence(detail.id, attachId, attachNote.trim() || undefined), "Evidence linked.", keep)}
              type="button"
            >
              Link
            </button>
          </div>
        ) : null}
      </div>

      <div>
        <div className={label}>
          Reasoning confidence · {detail.reasoning_confidence === null ? "computed when proposed" : `${detail.reasoning_confidence}/100`}
        </div>
        {detail.reasoning_confidence_explanation.length ? (
          <ul className="space-y-1 border border-[#202c28] bg-[#101516] p-2 font-mono text-[11px] text-[#aebbb4]">
            {detail.reasoning_confidence_explanation.map((line, index) => (
              <li key={index}>{line}</li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="space-y-2 border-t border-[#1d2825] pt-3">
        <div className={label}>Review actions</div>
        {isDraft ? (
          <button
            className={button("amber")}
            disabled={busy}
            onClick={() => void run(() => proposeHypothesis(detail.id), "Proposed. Content, evidence and confidence are now frozen.", keep)}
            type="button"
          >
            Propose for review
          </button>
        ) : null}
        {detail.status === "PROPOSED" ? (
          <div className="grid gap-2 md:grid-cols-[auto_minmax(0,1fr)_auto_auto]">
            <select className={input} onChange={(e) => setAssessment(e.target.value)} value={assessment}>
              <option value="">Assessment…</option>
              <option value="STRONG">Strong</option>
              <option value="ADEQUATE">Adequate</option>
              <option value="WEAK">Weak</option>
            </select>
            <input className={input} onChange={(e) => setReviewNotes(e.target.value)} placeholder="Review notes" value={reviewNotes} />
            <button
              className={button("green")}
              disabled={busy}
              onClick={() =>
                void run(
                  () =>
                    approveHypothesis(detail.id, {
                      ...(assessment ? { reviewer_assessment: assessment } : {}),
                      ...(reviewNotes.trim() ? { review_notes: reviewNotes.trim() } : {})
                    }),
                  "Approved.",
                  keep
                )
              }
              type="button"
            >
              Approve
            </button>
            <button
              className={button("red")}
              disabled={busy}
              onClick={() => void run(() => rejectHypothesis(detail.id, reviewNotes.trim() || undefined), "Rejected. This is final.", keep)}
              type="button"
            >
              Reject
            </button>
          </div>
        ) : null}
        {detail.status === "APPROVED" && !detail.is_active ? (
          <button
            className={button("green")}
            disabled={busy}
            onClick={() => void run(() => activateHypothesis(detail.id), "Activated as the outreach hypothesis.", keep)}
            type="button"
          >
            Make active
          </button>
        ) : null}
        {detail.status === "PROPOSED" || detail.status === "APPROVED" ? (
          <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
            <input
              className={input}
              onChange={(e) => setSuccessor(e.target.value)}
              placeholder="New statement for the replacement (blank = copy current)"
              value={successor}
            />
            <button
              className={button("gray")}
              disabled={busy}
              onClick={() =>
                void run(
                  () => supersedeHypothesis(detail.id, successor.trim() ? { statement: successor.trim() } : {}),
                  "Replacement draft created with no evidence; link evidence before proposing.",
                  idOf
                )
              }
              type="button"
            >
              Supersede
            </button>
          </div>
        ) : null}
        {detail.status === "REJECTED" || detail.status === "SUPERSEDED" ? (
          <p className="text-sm text-[#74837c]">This hypothesis is final and cannot change.</p>
        ) : null}
      </div>

      <details className="border-t border-[#1d2825] pt-3">
        <summary className={`${label} cursor-pointer`}>History · {detail.audit_events.length} events</summary>
        <ul className="mt-2 space-y-1 font-mono text-[11px] text-[#aebbb4]">
          {detail.audit_events.map((event) => (
            <li key={event.id}>
              <span className="text-[#74837c]">{event.created_at.slice(0, 19).replace("T", " ")}</span> {event.event_type}{" "}
              <span className="text-[#5d6b65]">{JSON.stringify(event.detail)}</span>
            </li>
          ))}
        </ul>
      </details>
    </Box>
  );
}

const idOf = (result: unknown) => (result as { id?: string })?.id;
