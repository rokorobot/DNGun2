"use client";

import {
  Activity,
  BarChart3,
  BookOpenCheck,
  CheckSquare,
  ClipboardList,
  FileText,
  Gauge,
  LineChart,
  Plus,
  Radar,
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
  approveOfferProposal,
  calculateScore,
  CampaignBatch,
  CampaignBatchProspect,
  CampaignIntelligenceReport,
  CampaignOutcome,
  createCampaignOutcome,
  createEvidenceEntry,
  createOffer,
  createProspect,
  EvidenceEntry,
  evaluateOffer,
  getAlphaSignalRules,
  getCampaignIntelligenceMarkdown,
  getCampaignIntelligenceReport,
  getLearningMarkdown,
  getLearningSummary,
  getOfferIntelligenceProfile,
  listCampaignBatches,
  listCampaignBatchProspects,
  listCampaignOutcomes,
  listOfferProposals,
  listOffers,
  listProspectAlphaSignals,
  listProspects,
  listProspectScores,
  listEvidenceEntries,
  listSignals,
  Prospect,
  ProspectAlphaSignal,
  ProspectScore,
  Segment,
  Signal,
  LearningSummary,
  Offer,
  OfferEvaluationProposal,
  OfferIntelligenceProfile,
  rejectOfferProposal,
  updateCampaignOutcome
} from "../lib/api";

const segments: Segment[] = ["AI_AUTOMATION", "REVOPS", "SEO", "WEBFLOW"];
type View = "inbox" | "scoring" | "report" | "evidence" | "outcomes" | "learning" | "offers";

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
  const [campaignBatches, setCampaignBatches] = useState<CampaignBatch[]>([]);
  const [selectedCampaignBatchId, setSelectedCampaignBatchId] = useState("");
  const [campaignBatchProspects, setCampaignBatchProspects] = useState<CampaignBatchProspect[]>([]);
  const [campaignOutcomes, setCampaignOutcomes] = useState<CampaignOutcome[]>([]);
  const [learningSummary, setLearningSummary] = useState<LearningSummary | null>(null);
  const [learningMarkdown, setLearningMarkdown] = useState("");
  const [offers, setOffers] = useState<Offer[]>([]);
  const [selectedOfferId, setSelectedOfferId] = useState("");
  const [offerProposals, setOfferProposals] = useState<OfferEvaluationProposal[]>([]);
  const [selectedOfferProposal, setSelectedOfferProposal] = useState<OfferEvaluationProposal | null>(null);
  const [offerProfile, setOfferProfile] = useState<OfferIntelligenceProfile | null>(null);
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

  async function refreshCampaignWorkbench(batchId = selectedCampaignBatchId) {
    setLoading(true);
    setMessage("");
    try {
      const batches = await listCampaignBatches();
      setCampaignBatches(batches);
      const activeBatchId = batchId || batches[0]?.id || "";
      if (!selectedCampaignBatchId && activeBatchId) setSelectedCampaignBatchId(activeBatchId);
      if (activeBatchId) {
        const [members, outcomes] = await Promise.all([
          listCampaignBatchProspects(activeBatchId),
          listCampaignOutcomes(activeBatchId)
        ]);
        setCampaignBatchProspects(members);
        setCampaignOutcomes(outcomes);
      } else {
        setCampaignBatchProspects([]);
        setCampaignOutcomes([]);
      }
    } catch (error) {
      setMessage(readError(error));
    } finally {
      setLoading(false);
    }
  }

  async function refreshLearning() {
    setLoading(true);
    setMessage("");
    try {
      const [summary, reportText] = await Promise.all([
        getLearningSummary(),
        getLearningMarkdown()
      ]);
      setLearningSummary(summary);
      setLearningMarkdown(reportText);
    } catch (error) {
      setMessage(readError(error));
    } finally {
      setLoading(false);
    }
  }

  async function refreshOffers(offerId = selectedOfferId) {
    setLoading(true);
    setMessage("");
    try {
      const nextOffers = await listOffers();
      setOffers(nextOffers);
      const activeOfferId = offerId || nextOffers[0]?.id || "";
      if (!selectedOfferId && activeOfferId) setSelectedOfferId(activeOfferId);
      if (activeOfferId) {
        const proposals = await listOfferProposals(activeOfferId);
        setOfferProposals(proposals);
        setSelectedOfferProposal(proposals[0] ?? null);
        try {
          setOfferProfile(await getOfferIntelligenceProfile(activeOfferId));
        } catch {
          setOfferProfile(null);
        }
      } else {
        setOfferProposals([]);
        setSelectedOfferProposal(null);
        setOfferProfile(null);
      }
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
    void refreshCampaignWorkbench();
    void refreshLearning();
    void refreshOffers();
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
    if (view === "outcomes") void refreshCampaignWorkbench();
    if (view === "learning") void refreshLearning();
    if (view === "offers") void refreshOffers();
  }, [view]);

  useEffect(() => {
    if (selectedCampaignBatchId) void refreshCampaignWorkbench(selectedCampaignBatchId);
  }, [selectedCampaignBatchId]);

  useEffect(() => {
    if (selectedOfferId) void refreshOffers(selectedOfferId);
  }, [selectedOfferId]);

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
              void refreshCampaignWorkbench();
              void refreshLearning();
              void refreshOffers();
            }}
          />

          <nav className="grid gap-2 md:grid-cols-7">
            <NavButton active={view === "offers"} onClick={() => setView("offers")}>
              <Radar size={15} /> Offer Intelligence
            </NavButton>
            <NavButton active={view === "inbox"} onClick={() => setView("inbox")}>
              <ClipboardList size={15} /> Prospect Inbox
            </NavButton>
            <NavButton active={view === "scoring"} onClick={() => setView("scoring")}>
              <Terminal size={15} /> Prospect Intelligence
            </NavButton>
            <NavButton active={view === "report"} onClick={() => setView("report")}>
              <BarChart3 size={15} /> Campaign Report
            </NavButton>
            <NavButton active={view === "outcomes"} onClick={() => setView("outcomes")}>
              <CheckSquare size={15} /> Campaign Outcomes
            </NavButton>
            <NavButton active={view === "learning"} onClick={() => setView("learning")}>
              <LineChart size={15} /> Learning Intelligence
            </NavButton>
            <NavButton active={view === "evidence"} onClick={() => setView("evidence")}>
              <BookOpenCheck size={15} /> Evidence Ledger
            </NavButton>
          </nav>

          {message ? <div className="border border-[#8f3d32] bg-[#24110f] p-3 text-sm text-[#ffad99]">{message}</div> : null}

          {view === "offers" ? (
            <OfferIntelligenceWorkspace
              offers={offers}
              profile={offerProfile}
              proposals={offerProposals}
              selectedOfferId={selectedOfferId}
              selectedProposal={selectedOfferProposal}
              onOfferChange={setSelectedOfferId}
              onProposalChange={setSelectedOfferProposal}
              onRefresh={async (offerId) => {
                await refreshOffers(offerId ?? selectedOfferId);
              }}
              setMessage={setMessage}
            />
          ) : null}
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
          {view === "outcomes" ? (
            <CampaignOutcomeWorkbench
              batches={campaignBatches}
              batchProspects={campaignBatchProspects}
              outcomes={campaignOutcomes}
              prospects={prospects}
              selectedBatchId={selectedCampaignBatchId}
              onBatchChange={setSelectedCampaignBatchId}
              onUpdated={async () => {
                await refreshCampaignWorkbench(selectedCampaignBatchId);
                await refreshReport();
                await refreshEvidenceEntries();
              }}
              setMessage={setMessage}
            />
          ) : null}
          {view === "learning" ? (
            <LearningIntelligenceWorkspace
              markdown={learningMarkdown}
              onRefresh={refreshLearning}
              summary={learningSummary}
            />
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

function OfferIntelligenceWorkspace({
  offers,
  profile,
  proposals,
  selectedOfferId,
  selectedProposal,
  onOfferChange,
  onProposalChange,
  onRefresh,
  setMessage
}: {
  offers: Offer[];
  profile: OfferIntelligenceProfile | null;
  proposals: OfferEvaluationProposal[];
  selectedOfferId: string;
  selectedProposal: OfferEvaluationProposal | null;
  onOfferChange: (offerId: string) => void;
  onProposalChange: (proposal: OfferEvaluationProposal | null) => void;
  onRefresh: (offerId?: string) => Promise<void>;
  setMessage: (message: string) => void;
}) {
  const [mode, setMode] = useState<"DETERMINISTIC" | "LLM_ASSISTED">("DETERMINISTIC");

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      const offer = await createOffer({
        name: String(form.get("name") || ""),
        description: optionalString(form.get("description")),
        estimated_value: optionalNumber(form.get("estimated_value"))
      });
      event.currentTarget.reset();
      onOfferChange(offer.id);
      await onRefresh(offer.id);
    } catch (error) {
      setMessage(readError(error));
    }
  }

  async function evaluate() {
    if (!selectedOfferId) return;
    setMessage("");
    try {
      const proposal = await evaluateOffer(selectedOfferId, mode);
      onProposalChange(proposal);
      await onRefresh(selectedOfferId);
    } catch (error) {
      setMessage(readError(error));
    }
  }

  async function approve(reviewNotes?: string) {
    if (!selectedOfferId || !selectedProposal) return;
    setMessage("");
    try {
      await approveOfferProposal(
        selectedOfferId,
        selectedProposal.id,
        reviewNotes
      );
      await onRefresh(selectedOfferId);
    } catch (error) {
      setMessage(readError(error));
    }
  }

  async function reject(reviewNotes?: string) {
    if (!selectedOfferId || !selectedProposal) return;
    setMessage("");
    try {
      const proposal = await rejectOfferProposal(
        selectedOfferId,
        selectedProposal.id,
        reviewNotes
      );
      onProposalChange(proposal);
      await onRefresh(selectedOfferId);
    } catch (error) {
      setMessage(readError(error));
    }
  }

  return (
    <Panel title="Offer Intelligence" icon={<Radar size={15} />} action="human approval required">
      <div className="grid gap-4 2xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="space-y-4">
          <form className="space-y-3 border border-[#202c28] bg-[#09100f] p-4" onSubmit={create}>
            <ConsoleField label="Domain Name" name="name" required />
            <ConsoleField label="Description" name="description" />
            <ConsoleField label="Estimated Value" name="estimated_value" />
            <button className="inline-flex h-9 w-full items-center justify-center gap-2 border border-[#00a85f] bg-[#06351f] px-3 font-mono text-xs uppercase text-[#00e084]" type="submit">
              <Save size={14} /> Create Offer
            </button>
          </form>

          <section className="border border-[#202c28] bg-[#0b0f10] p-4">
            <label className="block">
              <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">Offer</span>
              <select className="h-9 w-full border border-[#293733] bg-[#121516] px-2 font-mono text-xs text-white" onChange={(event) => onOfferChange(event.target.value)} value={selectedOfferId}>
                <option value="">NO_OFFER</option>
                {offers.map((offer) => (
                  <option key={offer.id} value={offer.id}>{offer.name} / {offer.status}</option>
                ))}
              </select>
            </label>
            <label className="mt-3 block">
              <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">Evaluation Mode</span>
              <select className="h-9 w-full border border-[#293733] bg-[#121516] px-2 font-mono text-xs text-white" onChange={(event) => setMode(event.target.value as "DETERMINISTIC" | "LLM_ASSISTED")} value={mode}>
                <option value="DETERMINISTIC">DETERMINISTIC</option>
                <option value="LLM_ASSISTED">LLM_ASSISTED</option>
              </select>
            </label>
            <button className="mt-3 inline-flex h-9 w-full items-center justify-center gap-2 border border-[#00a9d6] bg-[#062633] px-3 font-mono text-xs uppercase text-[#00c8ff]" onClick={() => void evaluate()} type="button">
              <Radar size={14} /> Generate Proposal
            </button>
          </section>

          <section className="border border-[#202c28] bg-[#0b0f10] p-4">
            <div className="mb-2 font-mono text-xs font-bold uppercase tracking-[0.14em] text-white">Proposals</div>
            <div className="space-y-2">
              {proposals.map((proposal) => (
                <button className={`w-full border p-3 text-left ${selectedProposal?.id === proposal.id ? "border-[#00d277] bg-[#082316]" : "border-[#293733] bg-[#101516]"}`} key={proposal.id} onClick={() => onProposalChange(proposal)} type="button">
                  <div className="flex items-center justify-between gap-2 font-mono text-xs">
                    <span className="text-white">{proposal.primary_category}</span>
                    <span className="text-[#ffb020]">{proposal.status}</span>
                  </div>
                  <div className="mt-2 font-mono text-[10px] text-[#74837c]">{proposal.provider} / {proposal.mode}</div>
                </button>
              ))}
            </div>
          </section>
        </div>

        <div className="space-y-4">
          <OfferProposalPreview proposal={selectedProposal} />
          <OfferReviewPanel onApprove={approve} onReject={reject} proposal={selectedProposal} />
          <ApprovedOfferProfile profile={profile} />
        </div>
      </div>
    </Panel>
  );
}

function OfferProposalPreview({ proposal }: { proposal: OfferEvaluationProposal | null }) {
  if (!proposal) {
    return (
      <section className="border border-[#202c28] bg-[#0b0f10] p-6 text-center font-mono text-xs uppercase text-[#74837c]">
        No proposal selected
      </section>
    );
  }
  const proposed = proposal.proposed_profile_json;
  return (
    <section className="border border-[#202c28] bg-[#0b0f10]">
      <div className="border-b border-[#202c28] px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.12em] text-white">Proposal Preview</div>
      <div className="space-y-4 p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <InfoLine label="Category" value={proposal.primary_category} />
          <InfoLine label="Confidence" value={`${proposal.confidence_label} / ${Math.round(proposal.confidence_score * 100)}%`} />
          <InfoLine label="Value Range" value={proposed.predicted_value_range} />
        </div>
        <ReasonBlock title="Commercial Hypothesis" value={proposed.commercial_hypothesis} />
        <MiniList title="Reasoning" values={proposal.reasoning} />
        <MiniList title="Alternative Categories" values={proposal.alternative_categories} />
        <OfferProfileLists proposed={proposed} />
      </div>
    </section>
  );
}

function OfferProfileLists({ proposed }: { proposed: OfferEvaluationProposal["proposed_profile_json"] }) {
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <MiniList title="Buyer Profiles" values={proposed.buyer_profiles.map((buyer) => `${buyer.profile_name}: ${buyer.rationale}`)} />
      <MiniList title="Signal Profiles" values={proposed.signal_profiles.map((signal) => `T${signal.tier} ${signal.signal_name}: ${signal.rationale}`)} />
      <MiniList title="PDM" values={[`${proposed.pdm.code} / ${proposed.pdm.name}`, proposed.pdm.summary, ...proposed.pdm.target_segments]} />
    </div>
  );
}

function OfferReviewPanel({
  onApprove,
  onReject,
  proposal
}: {
  onApprove: (reviewNotes?: string) => void;
  onReject: (reviewNotes?: string) => void;
  proposal: OfferEvaluationProposal | null;
}) {
  const [reviewNotes, setReviewNotes] = useState("");
  return (
    <section className="border border-[#202c28] bg-[#09100f] p-4">
      <label className="block">
        <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">Review Notes</span>
        <input className="h-9 w-full border border-[#293733] bg-[#121516] px-2 text-sm text-white" onChange={(event) => setReviewNotes(event.target.value)} value={reviewNotes} />
      </label>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        <button className="inline-flex h-9 items-center justify-center gap-2 border border-[#00a85f] bg-[#06351f] px-3 font-mono text-xs uppercase text-[#00e084] disabled:opacity-40" disabled={!proposal || proposal.status !== "PENDING_REVIEW"} onClick={() => void onApprove(reviewNotes || undefined)} type="button">
          <ShieldCheck size={14} /> Approve
        </button>
        <button className="inline-flex h-9 items-center justify-center gap-2 border border-[#8f3d32] bg-[#24110f] px-3 font-mono text-xs uppercase text-[#ffad99] disabled:opacity-40" disabled={!proposal || proposal.status !== "PENDING_REVIEW"} onClick={() => void onReject(reviewNotes || undefined)} type="button">
          Reject
        </button>
      </div>
    </section>
  );
}

function ApprovedOfferProfile({ profile }: { profile: OfferIntelligenceProfile | null }) {
  if (!profile) {
    return (
      <section className="border border-[#202c28] bg-[#0b0f10] p-6 text-center font-mono text-xs uppercase text-[#74837c]">
        No approved offer profile
      </section>
    );
  }
  return (
    <section className="border border-[#00a85f] bg-[#071f14]">
      <div className="border-b border-[#00a85f] px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.12em] text-white">Approved Offer Profile</div>
      <div className="space-y-4 p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <InfoLine label="Offer" value={profile.offer.name} />
          <InfoLine label="Category" value={profile.profile.offer_category} />
          <InfoLine label="Value" value={profile.profile.predicted_value_range} />
        </div>
        <ReasonBlock title="Commercial Hypothesis" value={profile.profile.commercial_hypothesis} />
        <OfferProfileLists proposed={{
          primary_category: profile.profile.offer_category,
          confidence_score: 1,
          confidence_label: "APPROVED",
          commercial_hypothesis: profile.profile.commercial_hypothesis,
          predicted_value_range: profile.profile.predicted_value_range,
          target_segments: profile.profile.target_segments,
          buyer_profiles: profile.buyerProfiles,
          signal_profiles: profile.signalProfiles,
          pdm: profile.pdm,
          reasoning: [],
          alternative_categories: []
        }} />
      </div>
    </section>
  );
}

function MiniList({ title, values }: { title: string; values: string[] }) {
  return (
    <section className="border border-[#293733] bg-[#101516] p-3">
      <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-[#00c8ff]">{title}</div>
      <div className="space-y-2">
        {values.map((value) => (
          <div className="text-sm text-[#dce8e1]" key={value}>{value}</div>
        ))}
      </div>
    </section>
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

function LearningIntelligenceWorkspace({
  summary,
  markdown,
  onRefresh
}: {
  summary: LearningSummary | null;
  markdown: string;
  onRefresh: () => Promise<void>;
}) {
  return (
    <Panel title="Learning Intelligence" icon={<LineChart size={15} />} action="evidence validation">
      <div className="mb-4 flex justify-end">
        <button className="inline-flex h-9 items-center gap-2 border border-[#00a9d6] bg-[#062633] px-3 font-mono text-xs uppercase text-[#00c8ff]" onClick={() => void onRefresh()} type="button">
          <RefreshCw size={14} /> Refresh Learning
        </button>
      </div>

      <div className="grid gap-4 2xl:grid-cols-2">
        <LearningList
          empty="No validated signal winners yet"
          items={summary?.topPerformingSignals ?? []}
          title="Top Performing Signals"
          type="signal"
        />
        <LearningList
          empty="No weak signal patterns yet"
          items={summary?.weakSignals ?? []}
          title="Weak Signals"
          type="signal"
        />
        <LearningList
          empty="No validated Alpha Signals yet"
          items={summary?.topAlphaSignals ?? []}
          title="Top Alpha Signals"
          type="alpha"
        />
        <LearningList
          empty="No weak Alpha Signals yet"
          items={summary?.weakAlphaSignals ?? []}
          title="Weak Alpha Signals"
          type="alpha"
        />
      </div>

      <section className="mt-4 border border-[#202c28] bg-[#0b0f10]">
        <div className="border-b border-[#202c28] px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.12em] text-white">
          Score Band Validation
        </div>
        <div className="overflow-auto">
          <table className="w-full min-w-[820px] border-collapse">
            <thead className="bg-[#0d1413]">
              <tr>
                <Th>Band</Th>
                <Th>Prospects</Th>
                <Th>Contacted</Th>
                <Th>Reply</Th>
                <Th>Call</Th>
                <Th>Pilot</Th>
                <Th>Confidence</Th>
                <Th>Recommendation</Th>
              </tr>
            </thead>
            <tbody>
              {(summary?.scoreBandValidation ?? []).map((band) => (
                <tr className="bg-[#080d0d]" key={band.scoreBand}>
                  <Td mono>{band.scoreBand}</Td>
                  <Td mono>{band.prospectsInBand}</Td>
                  <Td mono>{band.contacted}</Td>
                  <Td mono>{formatRate(band.replyRate)}</Td>
                  <Td mono>{formatRate(band.callRate)}</Td>
                  <Td mono>{formatRate(band.pilotRate)}</Td>
                  <Td mono>{band.confidence}</Td>
                  <Td mono>{band.recommendation}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="mt-4 grid gap-4 2xl:grid-cols-2">
        <section className="border border-[#202c28] bg-[#0b0f10]">
          <div className="border-b border-[#202c28] px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.12em] text-white">
            Recommended Rule Changes
          </div>
          <div className="space-y-2 p-4">
            {(summary?.recommendedRuleChanges ?? []).map((item) => (
              <div className="border border-[#293733] bg-[#101516] p-3 text-sm text-[#dce8e1]" key={item}>
                {item}
              </div>
            ))}
          </div>
        </section>
        <ConsolePre title="Learning Report Preview" value={markdown || "No learning report loaded."} />
      </div>
    </Panel>
  );
}

function LearningList({
  empty,
  items,
  title,
  type
}: {
  empty: string;
  items: Array<LearningSummary["topPerformingSignals"][number] | LearningSummary["topAlphaSignals"][number]>;
  title: string;
  type: "signal" | "alpha";
}) {
  return (
    <section className="border border-[#202c28] bg-[#0b0f10]">
      <div className="border-b border-[#202c28] px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.12em] text-white">
        {title}
      </div>
      <div className="space-y-2 p-4">
        {items.map((item) => {
          const isSignal = "signalType" in item;
          const name = isSignal ? item.signalType : `${item.code} ${item.name}`;
          const seen = isSignal ? item.timesSeen : item.timesMatched;
          return (
            <div className="border border-[#293733] bg-[#101516] p-3" key={name}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="font-mono text-sm font-bold text-white">{name}</div>
                <div className="font-mono text-xs text-[#00c8ff]">{item.recommendation}</div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-5">
                <InfoLine label={type === "signal" ? "Times Seen" : "Matched"} value={seen} />
                <InfoLine label="Contacted" value={item.contacted} />
                <InfoLine label="Reply" value={formatRate(item.replyRate)} />
                <InfoLine label="Call" value={formatRate(item.callRate)} />
                <InfoLine label="Pilot" value={formatRate(item.pilotRate)} />
              </div>
              <div className="mt-2 font-mono text-[10px] uppercase text-[#74837c]">
                Confidence // {item.confidence}
              </div>
            </div>
          );
        })}
        {items.length === 0 ? (
          <div className="border border-[#202c28] bg-[#080d0d] p-4 text-center font-mono text-xs uppercase text-[#74837c]">
            {empty}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function CampaignOutcomeWorkbench({
  batches,
  batchProspects,
  outcomes,
  prospects,
  selectedBatchId,
  onBatchChange,
  onUpdated,
  setMessage
}: {
  batches: CampaignBatch[];
  batchProspects: CampaignBatchProspect[];
  outcomes: CampaignOutcome[];
  prospects: Prospect[];
  selectedBatchId: string;
  onBatchChange: (batchId: string) => void;
  onUpdated: () => Promise<void>;
  setMessage: (message: string) => void;
}) {
  const prospectById = new Map(prospects.map((prospect) => [prospect.id, prospect]));
  const outcomeByProspect = new Map<string, CampaignOutcome>();
  for (const outcome of outcomes) {
    if (!outcomeByProspect.has(outcome.prospect_id)) outcomeByProspect.set(outcome.prospect_id, outcome);
  }
  const activeBatch = batches.find((batch) => batch.id === selectedBatchId) ?? null;
  const contacted = outcomes.filter((outcome) => outcome.contacted).length;
  const replied = outcomes.filter((outcome) => outcome.replied).length;
  const pilots = outcomes.filter((outcome) => outcome.paid_pilot).length;

  async function submit(event: FormEvent<HTMLFormElement>, prospectId: string, existing?: CampaignOutcome) {
    event.preventDefault();
    if (!selectedBatchId) return;
    setMessage("");
    const form = new FormData(event.currentTarget);
    const payload = {
      campaign_batch_id: selectedBatchId,
      prospect_id: prospectId,
      contacted: form.get("contacted") === "on",
      replied: form.get("replied") === "on",
      call_booked: form.get("call_booked") === "on",
      proposal_requested: form.get("proposal_requested") === "on",
      paid_pilot: form.get("paid_pilot") === "on",
      lost_deal: form.get("lost_deal") === "on",
      outcome_notes: optionalString(form.get("outcome_notes"))
    };
    try {
      if (existing) {
        await updateCampaignOutcome(existing.id, payload);
      } else {
        await createCampaignOutcome(payload);
      }
      await onUpdated();
    } catch (error) {
      setMessage(readError(error));
    }
  }

  return (
    <Panel title="Campaign Outcome Workbench" icon={<CheckSquare size={15} />} action="learning loop">
      <div className="mb-4 grid gap-3 md:grid-cols-4">
        <Metric label="Batch Prospects" value={batchProspects.length} tone="green" />
        <Metric label="Contacted" value={contacted} />
        <Metric label="Replies" value={replied} />
        <Metric label="Paid Pilots" value={pilots} tone={pilots ? "green" : "cyan"} />
      </div>

      <div className="mb-4 grid gap-3 border border-[#202c28] bg-[#09100f] p-4 md:grid-cols-[minmax(0,1fr)_220px_160px]">
        <label className="block">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">Campaign Batch</span>
          <select
            className="h-9 w-full border border-[#293733] bg-[#121516] px-2 font-mono text-xs text-white"
            onChange={(event) => onBatchChange(event.target.value)}
            value={selectedBatchId}
          >
            {batches.map((batch) => (
              <option key={batch.id} value={batch.id}>
                {batch.name}
              </option>
            ))}
          </select>
        </label>
        <InfoLine label="Status" value={activeBatch?.status ?? "NO_BATCH"} />
        <InfoLine label="Batch ID" value={activeBatch?.id ?? "-"} />
      </div>

      <div className="space-y-3">
        {batchProspects.map((member) => {
          const prospect = prospectById.get(member.prospect_id);
          const outcome = outcomeByProspect.get(member.prospect_id);
          return (
            <form
              className="border border-[#202c28] bg-[#080d0d] p-4"
              key={member.id}
              onSubmit={(event) => void submit(event, member.prospect_id, outcome)}
            >
              <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="font-mono text-sm font-bold text-white">{prospect?.company_name ?? "Unknown Prospect"}</div>
                  <div className="mt-1 font-mono text-[11px] text-[#74837c]">
                    {member.prospect_id} / {prospect?.segment ?? "NO_SEGMENT"} / {outcome?.id ?? "NO_OUTCOME"}
                  </div>
                </div>
                <button className="inline-flex h-8 items-center gap-2 border border-[#00a85f] bg-[#06351f] px-3 font-mono text-xs uppercase text-[#00e084]" type="submit">
                  <Save size={13} /> {outcome ? "Update" : "Record"}
                </button>
              </div>

              <div className="grid gap-2 xl:grid-cols-[repeat(6,minmax(0,1fr))_minmax(220px,1.5fr)]">
                <OutcomeToggle defaultChecked={outcome?.contacted ?? false} label="Contacted" name="contacted" />
                <OutcomeToggle defaultChecked={outcome?.replied ?? false} label="Replied" name="replied" />
                <OutcomeToggle defaultChecked={outcome?.call_booked ?? false} label="Call Booked" name="call_booked" />
                <OutcomeToggle defaultChecked={outcome?.proposal_requested ?? false} label="Proposal" name="proposal_requested" />
                <OutcomeToggle defaultChecked={outcome?.paid_pilot ?? false} label="Paid Pilot" name="paid_pilot" />
                <OutcomeToggle defaultChecked={outcome?.lost_deal ?? false} label="Lost Deal" name="lost_deal" />
                <label className="block">
                  <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">Outcome Notes</span>
                  <input
                    className="h-9 w-full border border-[#293733] bg-[#121516] px-2 text-sm text-white"
                    defaultValue={outcome?.outcome_notes ?? ""}
                    name="outcome_notes"
                  />
                </label>
              </div>
            </form>
          );
        })}
        {batchProspects.length === 0 ? (
          <div className="border border-[#202c28] bg-[#080d0d] p-6 text-center font-mono text-xs uppercase text-[#74837c]">
            No prospects assigned to selected campaign batch
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

function OutcomeToggle({ defaultChecked, label, name }: { defaultChecked: boolean; label: string; name: string }) {
  return (
    <label className="flex h-9 items-center gap-2 border border-[#293733] bg-[#101516] px-3 font-mono text-[10px] uppercase text-[#dce8e1]">
      <input className="h-3.5 w-3.5 accent-[#00d277]" defaultChecked={defaultChecked} name={name} type="checkbox" />
      <span>{label}</span>
    </label>
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

function optionalNumber(value: FormDataEntryValue | null) {
  const text = String(value || "").trim();
  return text ? Number(text) : undefined;
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
