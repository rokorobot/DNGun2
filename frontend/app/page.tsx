"use client";

import {
  Activity,
  BarChart3,
  BookOpenCheck,
  ClipboardList,
  FileText,
  Gauge,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  Terminal
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  addSignal,
  AlphaSignalRule,
  calculateScore,
  CampaignIntelligenceReport,
  createEvidenceEntry,
  createProspect,
  EvidenceEntry,
  getAlphaSignalRules,
  getCampaignIntelligenceMarkdown,
  getCampaignIntelligenceReport,
  listProspectAlphaSignals,
  listProspects,
  listProspectScores,
  listEvidenceEntries,
  listSignals,
  Prospect,
  ProspectAlphaSignal,
  ProspectScore,
  Segment,
  Signal
} from "../lib/api";

const segments: Segment[] = ["AI_AUTOMATION", "REVOPS", "SEO", "WEBFLOW"];
type View = "inbox" | "scoring" | "report" | "evidence";

export default function Home() {
  const [view, setView] = useState<View>("scoring");
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [selectedProspectId, setSelectedProspectId] = useState("");
  const [signals, setSignals] = useState<Signal[]>([]);
  const [score, setScore] = useState<ProspectScore | null>(null);
  const [prospectAlphaSignals, setProspectAlphaSignals] = useState<ProspectAlphaSignal[]>([]);
  const [report, setReport] = useState<CampaignIntelligenceReport | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [evidenceEntries, setEvidenceEntries] = useState<EvidenceEntry[]>([]);
  const [alphaRules, setAlphaRules] = useState<AlphaSignalRule[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const selectedProspect = useMemo(
    () => prospects.find((prospect) => prospect.id === selectedProspectId) ?? null,
    [prospects, selectedProspectId]
  );

  async function refreshProspects() {
    setLoading(true);
    setMessage("");
    try {
      const data = await listProspects();
      setProspects(data);
      if (!selectedProspectId && data.length > 0) setSelectedProspectId(data[0].id);
    } catch (error) {
      setMessage(readError(error));
    } finally {
      setLoading(false);
    }
  }

  async function refreshProspectIntelligence(prospectId: string) {
    if (!prospectId) return;
    const [nextSignals, scores, alphaMatches] = await Promise.all([
      listSignals(prospectId),
      listProspectScores(prospectId),
      listProspectAlphaSignals(prospectId)
    ]);
    setSignals(nextSignals);
    setScore(scores[0] ?? null);
    setProspectAlphaSignals(alphaMatches);
  }

  async function refreshReport() {
    setLoading(true);
    setMessage("");
    try {
      const [jsonReport, markdownReport] = await Promise.all([
        getCampaignIntelligenceReport(),
        getCampaignIntelligenceMarkdown()
      ]);
      setReport(jsonReport);
      setMarkdown(markdownReport);
    } catch (error) {
      setMessage(readError(error));
    } finally {
      setLoading(false);
    }
  }

  async function refreshEvidenceEntries() {
    setLoading(true);
    setMessage("");
    try {
      setEvidenceEntries(await listEvidenceEntries());
    } catch (error) {
      setMessage(readError(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshProspects();
    void refreshReport();
    void refreshEvidenceEntries();
    void getAlphaSignalRules().then(setAlphaRules).catch((error) => setMessage(readError(error)));
  }, []);

  useEffect(() => {
    if (selectedProspectId) {
      void refreshProspectIntelligence(selectedProspectId);
    }
  }, [selectedProspectId]);

  useEffect(() => {
    if (view === "report") void refreshReport();
    if (view === "evidence") void refreshEvidenceEntries();
  }, [view]);

  const activeSegment = selectedProspect?.segment ?? "AI_AUTOMATION";

  return (
    <main className="min-h-screen bg-[#050707] p-2 text-[#e4ebe6]">
      <header className="mb-3 border border-[#1d2825] bg-[#0d1111] px-5 py-4 shadow-[0_0_40px_rgba(0,255,150,0.04)]">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="grid h-10 w-10 place-items-center border border-[#0c5] bg-[#052116] text-[#00e084]">
              <ShieldCheck size={22} />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="font-mono text-lg font-bold tracking-[0.16em] text-white">
                  DNGUN
                </h1>
                <span className="border border-[#0c5] bg-[#07351f] px-2 py-0.5 font-mono text-[10px] text-[#00e084]">
                  MVP 0.3
                </span>
              </div>
              <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.18em] text-[#6f7f78]">
                Prospect intelligence operating console
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-6 font-mono text-xs uppercase">
            <HeaderStatus label="Active Segment" value={activeSegment} tone="cyan" />
            <HeaderStatus label="System Status" value="EVIDENCE_SAFE // ONLINE" tone="green" />
          </div>
        </div>
      </header>

      <section className="grid gap-3 xl:grid-cols-[330px_minmax(0,1fr)_430px]">
        <aside className="space-y-3">
          <Panel title="Prospect Inbox" icon={<ClipboardList size={15} />} action={`${prospects.length} records`}>
            <ProspectForm
              onCreated={async (prospect) => {
                await refreshProspects();
                setSelectedProspectId(prospect.id);
                setView("scoring");
              }}
              setMessage={setMessage}
            />
          </Panel>

          <Panel title="Prospect Banks" icon={<Target size={15} />} action={loading ? "sync" : "ready"}>
            <div className="max-h-[460px] space-y-2 overflow-auto pr-1">
              {prospects.map((prospect) => (
                <button
                  className={`w-full border p-3 text-left transition ${
                    prospect.id === selectedProspectId
                      ? "border-[#00d277] bg-[#082316]"
                      : "border-[#1d2825] bg-[#0b0f10] hover:border-[#52655e]"
                  }`}
                  key={prospect.id}
                  onClick={() => {
                    setSelectedProspectId(prospect.id);
                    setView("scoring");
                  }}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-mono text-sm font-semibold text-white">
                      {prospect.company_name}
                    </div>
                    <span className="font-mono text-[10px] text-[#00d277]">{prospect.segment}</span>
                  </div>
                  <div className="mt-2 font-mono text-[11px] text-[#71827a]">{prospect.id}</div>
                  <div className="mt-2 text-xs text-[#9aa8a1]">
                    {prospect.founder_name || "No founder"} · {prospect.status}
                  </div>
                </button>
              ))}
            </div>
          </Panel>
        </aside>

        <section className="space-y-3">
          <TelemetryStrip
            report={report}
            prospects={prospects.length}
            selected={selectedProspectId || "none"}
            loading={loading}
            onRefresh={() => {
              void refreshProspects();
              void refreshReport();
              void refreshEvidenceEntries();
            }}
          />

          <nav className="grid gap-2 md:grid-cols-4">
            <NavButton active={view === "inbox"} onClick={() => setView("inbox")}>
              <ClipboardList size={15} /> Prospect Inbox
            </NavButton>
            <NavButton active={view === "scoring"} onClick={() => setView("scoring")}>
              <Terminal size={15} /> Prospect Intelligence
            </NavButton>
            <NavButton active={view === "report"} onClick={() => setView("report")}>
              <BarChart3 size={15} /> Campaign Report
            </NavButton>
            <NavButton active={view === "evidence"} onClick={() => setView("evidence")}>
              <BookOpenCheck size={15} /> Evidence Ledger
            </NavButton>
          </nav>

          {message ? <div className="border border-[#8f3d32] bg-[#24110f] p-3 text-sm text-[#ffad99]">{message}</div> : null}

          {view === "inbox" ? <InboxOverview prospects={prospects} /> : null}
          {view === "scoring" ? (
            <ScoringWorkspace
              alphaRules={alphaRules}
              prospect={selectedProspect}
              prospects={prospects}
              selectedProspectId={selectedProspectId}
              signals={signals}
              score={score}
              prospectAlphaSignals={prospectAlphaSignals}
              onProspectChange={setSelectedProspectId}
              onSignalAdded={async () => {
                if (selectedProspectId) await refreshProspectIntelligence(selectedProspectId);
              }}
              onScore={(nextScore) => {
                setScore(nextScore);
                if (selectedProspectId) void refreshProspectIntelligence(selectedProspectId);
              }}
              setMessage={setMessage}
            />
          ) : null}
          {view === "report" ? (
            <ReportWorkspace markdown={markdown} onRefresh={refreshReport} report={report} />
          ) : null}
          {view === "evidence" ? (
            <EvidenceLedgerWorkspace
              entries={evidenceEntries}
              onCreated={async () => {
                await refreshEvidenceEntries();
                await refreshReport();
              }}
              setMessage={setMessage}
            />
          ) : null}
        </section>

        <aside className="space-y-3">
          <AlphaSignalsPanel alphaRules={alphaRules} matches={prospectAlphaSignals} score={score} />
          <EvidenceDiagnostics report={report} />
          <SignalSimulator />
        </aside>
      </section>
    </main>
  );
}

function ProspectForm({
  onCreated,
  setMessage
}: {
  onCreated: (prospect: Prospect) => Promise<void>;
  setMessage: (message: string) => void;
}) {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      const prospect = await createProspect({
        company_name: String(form.get("company_name") || ""),
        segment: String(form.get("segment") || "AI_AUTOMATION") as Segment,
        website: optionalString(form.get("website")),
        founder_name: optionalString(form.get("founder_name")),
        contact_path: optionalString(form.get("contact_path"))
      });
      event.currentTarget.reset();
      await onCreated(prospect);
    } catch (error) {
      setMessage(readError(error));
    }
  }

  return (
    <form className="space-y-3" onSubmit={submit}>
      <ConsoleField label="Company" name="company_name" required />
      <ConsoleField label="Website" name="website" />
      <label className="block">
        <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">
          Segment
        </span>
        <select className="h-9 w-full border border-[#293733] bg-[#121516] px-2 font-mono text-xs text-white" name="segment">
          {segments.map((segment) => (
            <option key={segment} value={segment}>{segment}</option>
          ))}
        </select>
      </label>
      <ConsoleField label="Founder" name="founder_name" />
      <ConsoleField label="Contact Path" name="contact_path" />
      <button className="inline-flex h-9 w-full items-center justify-center gap-2 border border-[#00b86b] bg-[#07351f] font-mono text-xs uppercase text-[#00e084]" type="submit">
        <Save size={14} /> Save Prospect
      </button>
    </form>
  );
}

function InboxOverview({ prospects }: { prospects: Prospect[] }) {
  return (
    <Panel title="Inbox Register" icon={<ClipboardList size={15} />} action={`${prospects.length} prospects`}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[740px] text-sm">
          <thead>
            <tr>
              <Th>Company</Th>
              <Th>Segment</Th>
              <Th>Founder</Th>
              <Th>Status</Th>
              <Th>ID</Th>
            </tr>
          </thead>
          <tbody>
            {prospects.map((prospect) => (
              <tr key={prospect.id}>
                <Td>{prospect.company_name}</Td>
                <Td>{prospect.segment}</Td>
                <Td>{prospect.founder_name || "—"}</Td>
                <Td>{prospect.status}</Td>
                <Td mono>{prospect.id}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ScoringWorkspace({
  alphaRules,
  prospect,
  prospectAlphaSignals,
  prospects,
  selectedProspectId,
  signals,
  score,
  onProspectChange,
  onSignalAdded,
  onScore,
  setMessage
}: {
  alphaRules: AlphaSignalRule[];
  prospect: Prospect | null;
  prospectAlphaSignals: ProspectAlphaSignal[];
  prospects: Prospect[];
  selectedProspectId: string;
  signals: Signal[];
  score: ProspectScore | null;
  onProspectChange: (id: string) => void;
  onSignalAdded: () => Promise<void>;
  onScore: (score: ProspectScore) => void;
  setMessage: (message: string) => void;
}) {
  async function submitSignal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProspectId) return;
    setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      await addSignal(selectedProspectId, {
        signal_type: String(form.get("signal_type") || ""),
        tier: Number(form.get("tier")) as 1 | 2 | 3,
        score: Number(form.get("score")),
        notes: optionalString(form.get("notes"))
      });
      event.currentTarget.reset();
      await onSignalAdded();
    } catch (error) {
      setMessage(readError(error));
    }
  }

  async function scoreProspect() {
    if (!selectedProspectId) return;
    try {
      onScore(await calculateScore(selectedProspectId));
    } catch (error) {
      setMessage(readError(error));
    }
  }

  return (
    <Panel title="Prospect Intelligence" icon={<Terminal size={15} />} action={prospect?.segment ?? "no prospect"}>
      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-4">
          <label className="block">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">Company</span>
            <select className="h-10 w-full border border-[#293733] bg-[#121516] px-2 font-mono text-sm text-white" onChange={(event) => onProspectChange(event.target.value)} value={selectedProspectId}>
              <option value="">Select prospect</option>
              {prospects.map((item) => <option key={item.id} value={item.id}>{item.company_name}</option>)}
            </select>
          </label>

          {prospect ? (
            <IntelligenceBrief
              prospect={prospect}
              score={score}
              signals={signals}
              alphaMatches={prospectAlphaSignals}
            />
          ) : null}

          <section className="border border-[#202c28] bg-[#0b0f10]">
            <div className="border-b border-[#202c28] px-4 py-3 font-mono text-xs uppercase tracking-[0.12em] text-white">
              Signals
            </div>
            <div className="divide-y divide-[#202c28]">
              {signals.map((signal) => (
                <div className="grid gap-2 px-4 py-3 md:grid-cols-[1fr_80px_80px]" key={signal.id}>
                  <div>
                    <div className="font-mono text-sm text-white">{signal.signal_type}</div>
                    <div className="mt-1 text-xs text-[#74837c]">{signal.notes || "No notes"}</div>
                  </div>
                  <div className="font-mono text-xs text-[#00c8ff]">TIER {signal.tier}</div>
                  <div className="font-mono text-xs text-[#00e084]">SCORE {signal.score}</div>
                </div>
              ))}
            </div>
          </section>

          {prospectAlphaSignals.length ? <ProspectAlphaMatches matches={prospectAlphaSignals} /> : null}
          {score ? <ScoreReadout score={score} /> : null}
        </div>

        <form className="border border-[#202c28] bg-[#0b0f10] p-4" onSubmit={submitSignal}>
          <div className="mb-3 flex items-center gap-2 font-mono text-xs uppercase tracking-[0.12em] text-white">
            <SlidersHorizontal size={14} /> Signal Injector
          </div>
          <ConsoleField label="Signal Type" name="signal_type" required />
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">Tier</span>
              <select className="h-9 w-full border border-[#293733] bg-[#121516] px-2 font-mono text-xs text-white" name="tier">
                <option value="1">TIER 1</option>
                <option value="2">TIER 2</option>
                <option value="3">TIER 3</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">Score</span>
              <input className="h-9 w-full border border-[#293733] bg-[#121516] px-2 font-mono text-xs text-white" max={5} min={0} name="score" required type="number" />
            </label>
          </div>
          <label className="mt-3 block">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">Notes</span>
            <textarea className="min-h-24 w-full border border-[#293733] bg-[#121516] p-2 text-sm text-white" name="notes" />
          </label>
          <button className="mt-3 inline-flex h-9 w-full items-center justify-center gap-2 border border-[#00b86b] bg-[#07351f] font-mono text-xs uppercase text-[#00e084]" disabled={!selectedProspectId} type="submit">
            <Plus size={14} /> Add Signal
          </button>
          <button className="mt-2 inline-flex h-9 w-full items-center justify-center gap-2 border border-[#00a9d6] bg-[#062633] font-mono text-xs uppercase text-[#00c8ff]" disabled={!selectedProspectId} onClick={() => void scoreProspect()} type="button">
            <Activity size={14} /> Calculate Score
          </button>
          <div className="mt-4 space-y-2">
            {alphaRules.slice(0, 3).map((rule) => (
              <div className="border border-[#202c28] bg-[#101516] p-2" key={rule.code}>
                <div className="font-mono text-xs text-[#ffb020]">{rule.code}</div>
                <div className="mt-1 text-xs text-[#aebbb4]">{rule.name}</div>
              </div>
            ))}
          </div>
        </form>
      </div>
    </Panel>
  );
}

function IntelligenceBrief({
  prospect,
  score,
  signals,
  alphaMatches
}: {
  prospect: Prospect;
  score: ProspectScore | null;
  signals: Signal[];
  alphaMatches: ProspectAlphaSignal[];
}) {
  const topSignals = signals.slice(0, 4);
  const decision = score?.decision ?? "UNSCORED";
  const decisionTone =
    decision === "CONTACT_NOW" ? "green" : decision === "DISQUALIFY" ? "red" : "amber";

  return (
    <section className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_260px]">
      <div className="border border-[#202c28] bg-[#0b0f10] p-4">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">
              Selected Prospect
            </div>
            <h2 className="mt-1 text-2xl font-semibold text-white">{prospect.company_name}</h2>
            <div className="mt-2 font-mono text-xs text-[#00c8ff]">{prospect.id}</div>
          </div>
          <Metric label="Decision" value={decision} tone={decisionTone} />
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <InfoLine label="Founder" value={prospect.founder_name || "Unknown"} />
          <InfoLine label="Segment" value={prospect.segment} />
          <InfoLine label="Contact Path" value={prospect.contact_path || "Not captured"} />
          <InfoLine label="Team Size" value={prospect.team_size ?? "Unknown"} />
          <InfoLine label="Offer Estimate" value={prospect.offer_value_estimate ?? "Unknown"} />
          <InfoLine label="Status" value={prospect.status} />
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <ReasonBlock
            title="Why Contact?"
            value={
              alphaMatches.length
                ? `${alphaMatches.length} Alpha Signal match${alphaMatches.length === 1 ? "" : "es"} detected.`
                : topSignals[0]?.signal_type || "Add signals to establish contact priority."
            }
          />
          <ReasonBlock
            title="Why Now?"
            value={
              topSignals.find((signal) => signal.tier === 1)?.signal_type ||
              "No Tier 1 urgency signal captured yet."
            }
          />
          <ReasonBlock
            title="Evidence"
            value={
              score
                ? `${score.explanation.length} provenance item${score.explanation.length === 1 ? "" : "s"} explain the score.`
                : `${signals.length} signal${signals.length === 1 ? "" : "s"} captured.`
            }
          />
        </div>
      </div>

      <div className="border border-[#202c28] bg-[#0b0f10] p-4">
        <div className="mb-3 font-mono text-xs uppercase tracking-[0.12em] text-white">
          Latest Score
        </div>
        <div className="grid gap-2">
          <Metric label="Base Score" value={score?.base_score ?? "-"} />
          <Metric label="Alpha Bonus" value={score ? `+${score.alpha_bonus}` : "-"} />
          <Metric label="Final Score" value={score?.final_score ?? "-"} tone={decisionTone} />
        </div>
      </div>
    </section>
  );
}

function ScoreReadout({ score }: { score: ProspectScore }) {
  const disqualifiers = score.explanation.filter((item) => item.source_type === "DISQUALIFIER");
  return (
    <section className="border border-[#202c28] bg-[#0b0f10]">
      <div className="grid gap-3 border-b border-[#202c28] p-4 md:grid-cols-5">
        <Metric label="Base Score" value={score.base_score} />
        <Metric label="Alpha Bonus" value={`+${score.alpha_bonus}`} />
        <Metric label="Final Score" value={score.final_score} />
        <Metric label="Decision" value={score.decision} tone={score.decision === "CONTACT_NOW" ? "green" : score.decision === "DISQUALIFY" ? "red" : "amber"} />
        <Metric label="Alpha Signals" value={score.alpha_matches.length ? score.alpha_matches.join(" ") : "NONE"} />
      </div>
      <div className="p-4">
        <div className="mb-3 font-mono text-xs uppercase tracking-[0.12em] text-white">Provenance Drawer</div>
        {disqualifiers.length ? (
          <div className="mb-3 border border-[#78332d] bg-[#210f0d] p-3">
            <div className="font-mono text-xs uppercase text-[#ff5d55]">
              Disqualification Provenance
            </div>
            {disqualifiers.map((item) => (
              <div className="mt-2 text-sm text-[#ffd1ca]" key={item.source_code}>
                {item.label}: {item.notes}
              </div>
            ))}
          </div>
        ) : null}
        <div className="space-y-2">
          {score.explanation.map((item, index) => (
            <details className="border border-[#202c28] bg-[#101516] p-3" key={`${item.source_code}-${index}`} open>
              <summary className="cursor-pointer list-none">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-sm text-white">{item.label}</span>
                  <span className="font-mono text-xs text-[#00c8ff]">{item.source_type} // {item.impact}</span>
                </div>
              </summary>
              <div className="mt-2 font-mono text-xs text-[#74837c]">
                {item.tier ? `TIER_${item.tier}` : item.source_code}
                {item.notes ? ` // ${item.notes}` : ""}
              </div>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

function ProspectAlphaMatches({ matches }: { matches: ProspectAlphaSignal[] }) {
  return (
    <section className="border border-[#202c28] bg-[#0b0f10]">
      <div className="border-b border-[#202c28] px-4 py-3 font-mono text-xs uppercase tracking-[0.12em] text-white">
        Alpha Matches
      </div>
      <div className="grid gap-2 p-4 md:grid-cols-3">
        {matches.map((match) => (
          <div className="border border-[#00a85f] bg-[#071f14] p-3" key={match.id}>
            <div className="font-mono text-sm text-[#00e084]">{match.alpha_signal_code}</div>
            <div className="mt-1 text-sm text-white">{match.alpha_signal_name}</div>
            <div className="mt-2 font-mono text-xs text-[#ffb020]">+{match.bonus_score}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function AlphaSignalsPanel({ alphaRules, matches, score }: { alphaRules: AlphaSignalRule[]; matches: ProspectAlphaSignal[]; score: ProspectScore | null }) {
  const matchedCodes = new Set([
    ...matches.map((match) => match.alpha_signal_code),
    ...(score?.alpha_matches ?? [])
  ]);
  return (
    <Panel title="Alpha Signals" icon={<Gauge size={15} />} action="rule registry">
      <div className="grid gap-2">
        {alphaRules.map((rule) => (
          <div className={`border p-3 ${matchedCodes.has(rule.code) ? "border-[#00d277] bg-[#082316]" : "border-[#202c28] bg-[#0b0f10]"}`} key={rule.code}>
            <div className="flex items-start justify-between gap-2">
              <div className="font-mono text-sm text-white">{rule.code}</div>
              <div className="font-mono text-xs text-[#ffb020]">+{rule.bonus_score}</div>
            </div>
            <div className="mt-2 text-sm text-[#dbe5df]">{rule.name}</div>
            <div className="mt-2 font-mono text-[10px] uppercase text-[#00d277]">
              {rule.validation_status || "HYPOTHESIS"}
            </div>
            <div className="mt-2 text-xs text-[#74837c]">{rule.required_signals.join(" + ")}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function EvidenceDiagnostics({ report }: { report: CampaignIntelligenceReport | null }) {
  const confidence = report?.confidence_after ?? 0;
  return (
    <Panel title="Evidence Diagnostics" icon={<ShieldCheck size={15} />} action="sys_monitor">
      <div className="grid gap-4 md:grid-cols-[120px_1fr] xl:grid-cols-1">
        <div className="mx-auto grid h-32 w-32 place-items-center rounded-full border-4 border-[#16d695] bg-[#07130f] shadow-[0_0_25px_rgba(22,214,149,0.16)]">
          <div className="text-center">
            <div className="font-mono text-3xl font-bold text-[#18e6a3]">{confidence || "—"}</div>
            <div className="font-mono text-[10px] uppercase text-[#74837c]">confidence</div>
          </div>
        </div>
        <div className="space-y-3">
          <MetricBar label="Reply Rate" value={report?.reply_rate ?? 0} />
          <MetricBar label="Call Rate" value={report?.call_booked_rate ?? 0} />
          <MetricBar label="Proposal Rate" value={report?.proposal_requested_rate ?? 0} />
          <MetricBar label="Pilot Rate" value={report?.paid_pilot_rate ?? 0} />
        </div>
      </div>
    </Panel>
  );
}

function SignalSimulator() {
  return (
    <Panel title="Signal Simulator" icon={<SlidersHorizontal size={15} />} action="later">
      <div className="grid grid-cols-2 gap-2">
        {["+ Founder Content", "+ Hiring SDR", "+ Service Launch", "+ Case Study", "+ Funding", "- Remove Signal"].map((label) => (
          <button className="border border-[#3a4540] bg-[#101516] px-2 py-3 font-mono text-[10px] uppercase text-[#cbd7d1]" key={label} type="button">
            {label}
          </button>
        ))}
      </div>
    </Panel>
  );
}

function ReportWorkspace({ report, markdown, onRefresh }: { report: CampaignIntelligenceReport | null; markdown: string; onRefresh: () => Promise<void> }) {
  return (
    <Panel title="Campaign Intelligence Report" icon={<BarChart3 size={15} />} action="deterministic">
      <div className="mb-4 flex justify-end">
        <button className="inline-flex h-9 items-center gap-2 border border-[#00a9d6] bg-[#062633] px-3 font-mono text-xs uppercase text-[#00c8ff]" onClick={() => void onRefresh()} type="button">
          <RefreshCw size={14} /> Refresh Report
        </button>
      </div>
      {report ? (
        <div className="mb-4 grid gap-3 md:grid-cols-5">
          <Metric label="Prospects" value={report.total_prospects} />
          <Metric label="Contacted" value={report.contacted_count} />
          <Metric label="Reply Rate" value={formatRate(report.reply_rate)} />
          <Metric label="Call Rate" value={formatRate(report.call_booked_rate)} />
          <Metric label="Pilot Rate" value={formatRate(report.paid_pilot_rate)} />
        </div>
      ) : null}
      <div className="grid gap-4 2xl:grid-cols-2">
        <ConsolePre title="JSON Report" value={report ? JSON.stringify(report, null, 2) : "No report loaded."} />
        <ConsolePre title="Markdown Preview" value={markdown || "No markdown loaded."} />
      </div>
    </Panel>
  );
}

function EvidenceLedgerWorkspace({
  entries,
  onCreated,
  setMessage
}: {
  entries: EvidenceEntry[];
  onCreated: () => Promise<void>;
  setMessage: (message: string) => void;
}) {
  const totalImpact = entries.reduce((sum, entry) => sum + entry.impact, 0);
  const positive = entries.filter((entry) => entry.impact > 0).length;
  const negative = entries.filter((entry) => entry.impact < 0).length;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      await createEvidenceEntry({
        evidence_type: String(form.get("evidence_type") || ""),
        evidence: String(form.get("evidence") || ""),
        impact: Number(form.get("impact") || 0),
        source: optionalString(form.get("source"))
      });
      event.currentTarget.reset();
      await onCreated();
    } catch (error) {
      setMessage(readError(error));
    }
  }

  return (
    <Panel title="Evidence Ledger" icon={<BookOpenCheck size={15} />} action="external reality">
      <div className="mb-4 grid gap-3 md:grid-cols-4">
        <Metric label="Entries" value={entries.length} tone="green" />
        <Metric label="Positive" value={positive} />
        <Metric label="Negative" value={negative} tone={negative ? "red" : "cyan"} />
        <Metric label="Net Impact" value={formatSigned(totalImpact)} tone={totalImpact < 0 ? "red" : "green"} />
      </div>

      <form className="mb-4 grid gap-3 border border-[#202c28] bg-[#09100f] p-4 xl:grid-cols-[190px_1fr_120px_190px_auto]" onSubmit={submit}>
        <label className="block">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">Evidence Type</span>
          <select className="h-9 w-full border border-[#293733] bg-[#121516] px-2 font-mono text-xs text-white" name="evidence_type" required>
            <option value="MARKET_INTEREST">MARKET_INTEREST</option>
            <option value="REVENUE">REVENUE</option>
            <option value="VALIDATION">VALIDATION</option>
            <option value="NEGATIVE">NEGATIVE</option>
            <option value="DELIVERY">DELIVERY</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">Evidence</span>
          <input className="h-9 w-full border border-[#293733] bg-[#121516] px-2 text-sm text-white" name="evidence" required />
        </label>
        <label className="block">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">Impact</span>
          <input className="h-9 w-full border border-[#293733] bg-[#121516] px-2 font-mono text-xs text-white" name="impact" required type="number" />
        </label>
        <ConsoleField label="Source" name="source" />
        <button className="inline-flex h-9 self-end items-center justify-center gap-2 border border-[#00a85f] bg-[#06351f] px-3 font-mono text-xs uppercase text-[#00e084]" type="submit">
          <Save size={14} /> Record
        </button>
      </form>

      <div className="overflow-auto border border-[#202c28]">
        <table className="w-full min-w-[980px] border-collapse">
          <thead className="bg-[#0d1413]">
            <tr>
              <Th>Created</Th>
              <Th>Type</Th>
              <Th>Impact</Th>
              <Th>Source</Th>
              <Th>Linked</Th>
              <Th>Evidence</Th>
              <Th>ID</Th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const link = evidenceLink(entry.source);
              return (
                <tr className="bg-[#080d0d] hover:bg-[#0d1514]" key={entry.id}>
                  <Td mono>{formatDate(entry.created_at)}</Td>
                  <Td mono>{entry.evidence_type}</Td>
                  <Td mono>
                    <span className={entry.impact < 0 ? "text-[#ff5d55]" : "text-[#00e084]"}>
                      {formatSigned(entry.impact)}
                    </span>
                  </Td>
                  <Td mono>{entry.source || "UNSOURCED"}</Td>
                  <Td mono>
                    <span className={link === "UNLINKED" ? "text-[#74837c]" : "text-[#00c8ff]"}>{link}</span>
                  </Td>
                  <Td>{entry.evidence}</Td>
                  <Td mono>{entry.id}</Td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {entries.length === 0 ? (
          <div className="border-t border-[#202c28] p-6 text-center font-mono text-xs uppercase text-[#74837c]">
            No evidence entries recorded
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

function TelemetryStrip({ report, prospects, selected, loading, onRefresh }: { report: CampaignIntelligenceReport | null; prospects: number; selected: string; loading: boolean; onRefresh: () => void }) {
  return (
    <section className="grid gap-2 md:grid-cols-[repeat(5,minmax(0,1fr))_auto]">
      <Metric label="Prospects" value={prospects} />
      <Metric label="Campaigns" value="1" />
      <Metric label="Evidence" value={report?.evidence_entries_created ?? "—"} />
      <Metric label="Confidence" value={report?.confidence_after ? `${report.confidence_after}%` : "—"} />
      <Metric label="Rule Registry" value="ACTIVE" tone="green" />
      <button className="inline-flex h-full min-h-14 items-center justify-center gap-2 border border-[#293733] bg-[#101516] px-4 font-mono text-xs uppercase text-[#dbe5df]" onClick={onRefresh} type="button">
        <RefreshCw size={14} /> {loading ? "Sync" : selected === "none" ? "Refresh" : "Refresh"}
      </button>
    </section>
  );
}

function Panel({ title, icon, action, children }: { title: string; icon: React.ReactNode; action?: string; children: React.ReactNode }) {
  return (
    <section className="border border-[#1d2825] bg-[#0b0f10] shadow-[0_0_0_1px_rgba(255,255,255,0.01),0_16px_60px_rgba(0,0,0,0.35)]">
      <div className="flex items-center justify-between border-b border-[#1d2825] px-4 py-3">
        <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-[0.14em] text-white">
          <span className="text-[#00d277]">{icon}</span>
          {title}
        </div>
        {action ? <div className="font-mono text-[10px] uppercase text-[#74837c]">{action}</div> : null}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function NavButton({ active, children, onClick }: { active: boolean; children: React.ReactNode; onClick: () => void }) {
  return (
    <button className={`inline-flex h-10 items-center justify-center gap-2 border font-mono text-xs uppercase ${active ? "border-[#00d277] bg-[#082316] text-white" : "border-[#293733] bg-[#101516] text-[#aebbb4]"}`} onClick={onClick} type="button">
      {children}
    </button>
  );
}

function HeaderStatus({ label, value, tone }: { label: string; value: string; tone: "green" | "cyan" }) {
  return (
    <div className="border-l border-[#293733] pl-5">
      <div className="text-[10px] text-[#74837c]">{label}</div>
      <div className={tone === "green" ? "text-[#00e084]" : "text-[#00c8ff]"}>{value}</div>
    </div>
  );
}

function InfoLine({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border border-[#202c28] bg-[#101516] p-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-[#74837c]">{label}</div>
      <div className="mt-2 break-words text-sm text-[#dce8e1]">{value}</div>
    </div>
  );
}

function ReasonBlock({ title, value }: { title: string; value: string }) {
  return (
    <div className="border border-[#293733] bg-[#101516] p-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-[#00c8ff]">{title}</div>
      <div className="mt-2 text-sm leading-5 text-[#dce8e1]">{value}</div>
    </div>
  );
}

function ConsoleField({ label, name, required = false }: { label: string; name: string; required?: boolean }) {
  return (
    <label className="block">
      <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">{label}</span>
      <input className="h-9 w-full border border-[#293733] bg-[#121516] px-2 text-sm text-white" name={name} required={required} />
    </label>
  );
}

function Metric({ label, value, tone = "cyan" }: { label: string; value: string | number; tone?: "green" | "cyan" | "amber" | "red" }) {
  const color = tone === "green" ? "text-[#00e084]" : tone === "amber" ? "text-[#ffb020]" : tone === "red" ? "text-[#ff5d55]" : "text-[#dbe5df]";
  return (
    <div className="border border-[#202c28] bg-[#101516] p-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-[#74837c]">{label}</div>
      <div className={`mt-2 break-words font-mono text-lg font-bold ${color}`}>{value}</div>
    </div>
  );
}

function MetricBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1 flex justify-between font-mono text-[10px] uppercase text-[#74837c]">
        <span>{label}</span>
        <span className="text-[#00e084]">{formatRate(value)}</span>
      </div>
      <div className="h-1.5 bg-[#18201e]">
        <div className="h-1.5 bg-[#00d277]" style={{ width: `${Math.min(value * 100, 100)}%` }} />
      </div>
    </div>
  );
}

function ConsolePre({ title, value }: { title: string; value: string }) {
  return (
    <section className="border border-[#202c28] bg-[#0b0f10]">
      <div className="flex items-center gap-2 border-b border-[#202c28] px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.12em] text-white">
        <FileText size={14} /> {title}
      </div>
      <pre className="max-h-[560px] overflow-auto whitespace-pre-wrap p-4 font-mono text-xs leading-6 text-[#dce8e1]">{value}</pre>
    </section>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="border-b border-[#202c28] px-3 py-2 text-left font-mono text-[10px] uppercase tracking-[0.12em] text-[#00d277]">{children}</th>;
}

function Td({ children, mono = false }: { children: React.ReactNode; mono?: boolean }) {
  return <td className={`border-b border-[#202c28] px-3 py-3 text-[#dce8e1] ${mono ? "font-mono text-xs" : "text-sm"}`}>{children}</td>;
}

function optionalString(value: FormDataEntryValue | null) {
  const text = String(value || "").trim();
  return text ? text : undefined;
}

function readError(error: unknown) {
  return error instanceof Error ? error.message : "Request failed";
}

function formatRate(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatSigned(value: number) {
  return value > 0 ? `+${value}` : String(value);
}

function formatDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function evidenceLink(source?: string | null) {
  if (!source) return "UNLINKED";
  const normalized = source.toUpperCase();
  if (normalized.startsWith("P-")) return "PROSPECT";
  if (normalized.startsWith("CB-")) return "CAMPAIGN";
  if (normalized.startsWith("CO-")) return "OUTCOME";
  return "SOURCE";
}
