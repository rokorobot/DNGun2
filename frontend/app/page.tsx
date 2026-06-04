"use client";

import {
  Activity,
  BarChart3,
  BookOpenCheck,
  CheckSquare,
  ClipboardList,
  Edit2,
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
  Terminal,
  Trash2
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  addSignal,
  AlphaSignalRule,
  approveOfferProposal,
  calculateOfferProspectFits,
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
  listSegments,
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
  OfferProspectFit,
  rejectOfferProposal,
  listOfferProspectFits,
  updateCampaignOutcome,
  SegmentRegistry,
  DecisionMaker,
  listDecisionMakers,
  createDecisionMaker,
  updateDecisionMaker,
  deleteDecisionMaker,
  ContactPath,
  ContactPathType,
  listContactPaths,
  createContactPath,
  updateContactPath,
  deleteContactPath
} from "../lib/api";

type View = "inbox" | "scoring" | "report" | "evidence" | "outcomes" | "learning" | "offers";

export default function Home() {
  const [view, setView] = useState<View>("scoring");
  const [segments, setSegments] = useState<SegmentRegistry[]>([]);
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
  const [offerFits, setOfferFits] = useState<OfferProspectFit[]>([]);
  const [alphaRules, setAlphaRules] = useState<AlphaSignalRule[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [filterPdmCode, setFilterPdmCode] = useState("");
  const [filterOfferId, setFilterOfferId] = useState("");
  const [decisionMakers, setDecisionMakers] = useState<DecisionMaker[]>([]);

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

  async function refreshSegments() {
    setLoading(true);
    setMessage("");
    try {
      const data = await listSegments();
      setSegments(data);
    } catch (error) {
      setMessage(readError(error));
    } finally {
      setLoading(false);
    }
  }

  async function refreshProspectIntelligence(prospectId: string) {
    if (!prospectId) return;
    const [nextSignals, scores, alphaMatches, dms] = await Promise.all([
      listSignals(prospectId),
      listProspectScores(prospectId),
      listProspectAlphaSignals(prospectId),
      listDecisionMakers(prospectId)
    ]);
    setSignals(nextSignals);
    setScore(scores[0] ?? null);
    setProspectAlphaSignals(alphaMatches);
    setDecisionMakers(dms);
  }

  async function refreshReport(pdmCode = filterPdmCode, offerId = filterOfferId) {
    setLoading(true);
    setMessage("");
    try {
      const [jsonReport, markdownReport] = await Promise.all([
        getCampaignIntelligenceReport(pdmCode, offerId),
        getCampaignIntelligenceMarkdown(pdmCode, offerId)
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

  async function refreshLearning(pdmCode = filterPdmCode, offerId = filterOfferId) {
    setLoading(true);
    setMessage("");
    try {
      const [summary, reportText] = await Promise.all([
        getLearningSummary(pdmCode, offerId),
        getLearningMarkdown(pdmCode, offerId)
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
        setOfferFits(await listOfferProspectFits(activeOfferId));
      } else {
        setOfferProposals([]);
        setSelectedOfferProposal(null);
        setOfferProfile(null);
        setOfferFits([]);
      }
    } catch (error) {
      setMessage(readError(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshSegments();
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
    if (view === "report") void refreshReport(filterPdmCode, filterOfferId);
    if (view === "evidence") void refreshEvidenceEntries();
    if (view === "outcomes") void refreshCampaignWorkbench();
    if (view === "learning") void refreshLearning(filterPdmCode, filterOfferId);
    if (view === "offers") void refreshOffers();
  }, [view, filterPdmCode, filterOfferId]);

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
              segments={segments}
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
              fits={offerFits}
              offers={offers}
              profile={offerProfile}
              prospects={prospects}
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
              decisionMakers={decisionMakers}
              onProspectChange={setSelectedProspectId}
              onSignalAdded={async () => {
                if (selectedProspectId) await refreshProspectIntelligence(selectedProspectId);
              }}
              onScore={(nextScore) => {
                setScore(nextScore);
                if (selectedProspectId) void refreshProspectIntelligence(selectedProspectId);
              }}
              onDecisionMakersChange={async () => {
                if (selectedProspectId) await refreshProspectIntelligence(selectedProspectId);
              }}
              setMessage={setMessage}
            />
          ) : null}
          {view === "report" ? (
            <ReportWorkspace
              markdown={markdown}
              onRefresh={refreshReport}
              report={report}
              filterPdmCode={filterPdmCode}
              filterOfferId={filterOfferId}
              onPdmChange={setFilterPdmCode}
              onOfferChange={setFilterOfferId}
              offers={offers}
              segments={segments}
            />
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
              filterPdmCode={filterPdmCode}
              filterOfferId={filterOfferId}
              onPdmChange={setFilterPdmCode}
              onOfferChange={setFilterOfferId}
              offers={offers}
              segments={segments}
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
  fits,
  profile,
  prospects,
  proposals,
  selectedOfferId,
  selectedProposal,
  onOfferChange,
  onProposalChange,
  onRefresh,
  setMessage
}: {
  offers: Offer[];
  fits: OfferProspectFit[];
  profile: OfferIntelligenceProfile | null;
  prospects: Prospect[];
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

  async function calculateFits() {
    if (!selectedOfferId) return;
    setMessage("");
    try {
      await calculateOfferProspectFits(selectedOfferId);
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
          <OfferProspectFitPanel
            fits={fits}
            onCalculate={calculateFits}
            profile={profile}
            prospects={prospects}
          />
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

function OfferProspectFitPanel({
  fits,
  onCalculate,
  profile,
  prospects
}: {
  fits: OfferProspectFit[];
  onCalculate: () => Promise<void>;
  profile: OfferIntelligenceProfile | null;
  prospects: Prospect[];
}) {
  const prospectById = new Map(prospects.map((prospect) => [prospect.id, prospect]));
  return (
    <section className="border border-[#202c28] bg-[#0b0f10]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#202c28] px-4 py-3">
        <div className="font-mono text-xs font-bold uppercase tracking-[0.12em] text-white">
          Offer-to-Prospect Fit
        </div>
        <button className="inline-flex h-8 items-center justify-center gap-2 border border-[#00a9d6] bg-[#062633] px-3 font-mono text-xs uppercase text-[#00c8ff] disabled:opacity-40" disabled={!profile} onClick={() => void onCalculate()} type="button">
          <Radar size={13} /> Calculate Prospect Fit
        </button>
      </div>
      <div className="overflow-auto">
        <table className="w-full min-w-[980px] border-collapse">
          <thead className="bg-[#0d1413]">
            <tr>
              <Th>Prospect</Th>
              <Th>Decision</Th>
              <Th>Total</Th>
              <Th>Segment</Th>
              <Th>Buyer</Th>
              <Th>Signal</Th>
              <Th>Explanation</Th>
            </tr>
          </thead>
          <tbody>
            {fits.map((fit) => {
              const prospect = prospectById.get(fit.prospect_id);
              return (
                <tr className="bg-[#080d0d] hover:bg-[#0d1514]" key={fit.id}>
                  <Td>
                    <div className="font-mono text-sm text-white">{prospect?.company_name ?? fit.prospect_id}</div>
                    <div className="mt-1 font-mono text-[10px] text-[#74837c]">{fit.prospect_id}</div>
                  </Td>
                  <Td mono>
                    <span className={fit.decision === "STRONG_FIT" ? "text-[#00e084]" : fit.decision === "DISQUALIFIED" ? "text-[#ff5d55]" : "text-[#ffb020]"}>
                      {fit.decision}
                    </span>
                  </Td>
                  <Td mono>{fit.total_fit_score}</Td>
                  <Td mono>{fit.segment_fit_score}</Td>
                  <Td mono>{fit.buyer_profile_fit_score}</Td>
                  <Td mono>{fit.signal_fit_score}</Td>
                  <Td>
                    <details>
                      <summary className="cursor-pointer font-mono text-xs uppercase text-[#00c8ff]">Open</summary>
                      <div className="mt-2 space-y-1">
                        {fit.explanation.map((item) => (
                          <div className="text-xs text-[#dce8e1]" key={item}>{item}</div>
                        ))}
                      </div>
                    </details>
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {fits.length === 0 ? (
          <div className="border-t border-[#202c28] p-6 text-center font-mono text-xs uppercase text-[#74837c]">
            No offer-prospect fits calculated
          </div>
        ) : null}
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
  setMessage,
  segments
}: {
  onCreated: (prospect: Prospect) => Promise<void>;
  setMessage: (message: string) => void;
  segments: SegmentRegistry[];
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
          {segments.map((seg) => (
            <option key={seg.code} value={seg.code}>{seg.label}</option>
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
  decisionMakers,
  onProspectChange,
  onSignalAdded,
  onScore,
  onDecisionMakersChange,
  setMessage
}: {
  alphaRules: AlphaSignalRule[];
  prospect: Prospect | null;
  prospectAlphaSignals: ProspectAlphaSignal[];
  prospects: Prospect[];
  selectedProspectId: string;
  signals: Signal[];
  score: ProspectScore | null;
  decisionMakers: DecisionMaker[];
  onProspectChange: (id: string) => void;
  onSignalAdded: () => Promise<void>;
  onScore: (score: ProspectScore) => void;
  onDecisionMakersChange: () => Promise<void>;
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
            <>
              <IntelligenceBrief
                prospect={prospect}
                score={score}
                signals={signals}
                alphaMatches={prospectAlphaSignals}
              />
              <div className="mt-4">
                <DecisionMakersSection
                  prospect={prospect}
                  decisionMakers={decisionMakers}
                  onRefresh={onDecisionMakersChange}
                  setMessage={setMessage}
                />
              </div>
            </>
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

function DecisionMakersSection({
  prospect,
  decisionMakers,
  onRefresh,
  setMessage
}: {
  prospect: Prospect;
  decisionMakers: DecisionMaker[];
  onRefresh: () => Promise<void>;
  setMessage: (message: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [editingDm, setEditingDm] = useState<DecisionMaker | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    role: "",
    email: "",
    linkedin: "",
    entry_source: "MANUAL"
  });

  // Contact Path states
  const [isPathOpen, setIsPathOpen] = useState(false);
  const [editingPath, setEditingPath] = useState<ContactPath | null>(null);
  const [activeDmIdForPath, setActiveDmIdForPath] = useState("");
  const [pathFormData, setPathFormData] = useState({
    type: "EMAIL" as ContactPathType,
    value: "",
    source: "MANUAL",
    confidence: 100,
    verified: false,
    last_verified_at: ""
  });

  function openAddModal() {
    setEditingDm(null);
    setFormData({
      name: "",
      role: "",
      email: "",
      linkedin: "",
      entry_source: "MANUAL"
    });
    setIsOpen(true);
  }

  function handleEdit(dm: DecisionMaker) {
    setEditingDm(dm);
    setFormData({
      name: dm.name,
      role: dm.role,
      email: dm.email || "",
      linkedin: dm.linkedin || "",
      entry_source: dm.entry_source || "MANUAL"
    });
    setIsOpen(true);
  }

  function closeModal() {
    setIsOpen(false);
    setEditingDm(null);
  }

  // Contact Path Handlers
  function openAddPathModal(dmId: string) {
    setActiveDmIdForPath(dmId);
    setEditingPath(null);
    setPathFormData({
      type: "EMAIL",
      value: "",
      source: "MANUAL",
      confidence: 100,
      verified: false,
      last_verified_at: ""
    });
    setIsPathOpen(true);
  }

  function handleEditPath(path: ContactPath) {
    setEditingPath(path);
    setActiveDmIdForPath(path.decision_maker_id);
    setPathFormData({
      type: path.type,
      value: path.value,
      source: path.source || "MANUAL",
      confidence: path.confidence || 100,
      verified: path.verified || false,
      last_verified_at: path.last_verified_at || ""
    });
    setIsPathOpen(true);
  }

  function closePathModal() {
    setIsPathOpen(false);
    setEditingPath(null);
    setActiveDmIdForPath("");
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMessage("");
    try {
      if (editingDm) {
        await updateDecisionMaker(editingDm.id, {
          name: formData.name,
          role: formData.role,
          email: formData.email || undefined,
          linkedin: formData.linkedin || undefined,
          entry_source: formData.entry_source
        });
      } else {
        await createDecisionMaker(prospect.id, {
          name: formData.name,
          role: formData.role,
          email: formData.email || undefined,
          linkedin: formData.linkedin || undefined,
          entry_source: formData.entry_source
        });
      }
      setIsOpen(false);
      setEditingDm(null);
      await onRefresh();
    } catch (error) {
      setMessage(readError(error));
    }
  }

  async function handlePathSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMessage("");
    try {
      if (editingPath) {
        await updateContactPath(editingPath.id, {
          type: pathFormData.type,
          value: pathFormData.value,
          source: pathFormData.source,
          confidence: pathFormData.confidence,
          verified: pathFormData.verified,
          last_verified_at: pathFormData.last_verified_at || undefined
        });
      } else {
        await createContactPath(activeDmIdForPath, {
          type: pathFormData.type,
          value: pathFormData.value,
          source: pathFormData.source,
          confidence: pathFormData.confidence,
          verified: pathFormData.verified,
          last_verified_at: pathFormData.last_verified_at || undefined
        });
      }
      setIsPathOpen(false);
      setEditingPath(null);
      await onRefresh();
    } catch (error) {
      setMessage(readError(error));
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Are you sure you want to delete this decision maker?")) return;
    setMessage("");
    try {
      await deleteDecisionMaker(id);
      await onRefresh();
    } catch (error) {
      setMessage(readError(error));
    }
  }

  async function handleDeletePath(id: string) {
    if (!confirm("Are you sure you want to delete this contact path?")) return;
    setMessage("");
    try {
      await deleteContactPath(id);
      await onRefresh();
    } catch (error) {
      setMessage(readError(error));
    }
  }

  return (
    <section className="border border-[#202c28] bg-[#0b0f10]">
      <div className="flex items-center justify-between border-b border-[#202c28] px-4 py-3">
        <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-[0.12em] text-white">
          <Target size={14} className="text-[#00e084]" />
          Decision Makers (Buyer Authority)
        </div>
        <button
          className="inline-flex h-7 items-center justify-center gap-1 border border-[#00b86b] bg-[#07351f] px-3 font-mono text-[10px] uppercase text-[#00e084] hover:bg-[#00b86b] hover:text-black transition-colors"
          onClick={openAddModal}
          type="button"
        >
          <Plus size={10} /> Add Contact
        </button>
      </div>

      <div className="p-4">
        {decisionMakers.length === 0 ? (
          <div className="p-8 text-center text-[#74837c] font-mono text-xs border border-[#202c28] bg-[#101516]/30">
            NO DECISION MAKERS CAPTURED FOR THIS PROSPECT.
            <div className="mt-2 text-[10px] text-[#54635c]">
              Use "Add Contact" above to manually insert key personnel.
            </div>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {decisionMakers.map((dm) => (
              <div key={dm.id} className="border border-[#202c28] bg-[#101516] p-4 flex flex-col justify-between hover:border-[#00e084]/40 transition-colors">
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-semibold text-white">{dm.name}</div>
                      <div className="font-mono text-xs text-[#00c8ff]">{dm.role}</div>
                    </div>
                    <div className={`px-2 py-1 border font-mono text-xs font-bold ${
                      dm.authority_score >= 90 ? "border-[#00e084] bg-[#00e084]/10 text-[#00e084]" :
                      dm.authority_score >= 50 ? "border-[#ffb020] bg-[#ffb020]/10 text-[#ffb020]" :
                      "border-[#ff5d55] bg-[#ff5d55]/10 text-[#ff5d55]"
                    }`}>
                      {dm.authority_score} PTS
                    </div>
                  </div>
                  
                  {dm.acquisition_rationale && (
                    <div className="mt-3 text-xs text-[#74837c] bg-[#0b0f10] p-2 border border-[#202c28] leading-relaxed">
                      {dm.acquisition_rationale}
                    </div>
                  )}

                  {/* Contact Paths subsection */}
                  <div className="mt-4 border-t border-[#202c28]/60 pt-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-[#74837c]">
                        Contact Paths ({dm.contact_paths?.length || 0})
                      </div>
                      <button
                        onClick={() => openAddPathModal(dm.id)}
                        className="font-mono text-[9px] uppercase text-[#00e084] hover:text-white transition-colors"
                        type="button"
                      >
                        + Add Path
                      </button>
                    </div>
                    
                    <div className="space-y-1.5">
                      {dm.contact_paths && dm.contact_paths.length > 0 ? (
                        dm.contact_paths.map((path) => (
                          <div key={path.id} className="group/path flex items-center justify-between border border-[#202c28] bg-[#0b0f10] px-2 py-1 hover:border-[#00e084]/20 transition-colors">
                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              <span className="font-mono text-[8px] text-[#00c8ff] border border-[#00c8ff]/20 bg-[#00c8ff]/5 px-1.5 py-0.2">
                                {path.type}
                              </span>
                              <span className="font-mono break-all text-white max-w-[150px] md:max-w-none">
                                {path.type === "EMAIL" ? (
                                  <a href={`mailto:${path.value}`} className="hover:underline">{path.value}</a>
                                ) : path.type === "LINKEDIN" ? (
                                  <a href={path.value.startsWith("http") ? path.value : `https://${path.value}`} target="_blank" rel="noopener noreferrer" className="hover:underline">{path.value}</a>
                                ) : (
                                  <span>{path.value}</span>
                                )}
                              </span>
                              {path.verified ? (
                                <span className="text-[#00e084] font-mono text-[8px]" title={path.last_verified_at ? `Verified at ${path.last_verified_at}` : "Verified"}>
                                  ✓ [V]
                                </span>
                              ) : (
                                <span className="text-[#ff5d55] font-mono text-[8px]">[U]</span>
                              )}
                              <span className="text-[10px] text-[#74837c]">
                                ({path.confidence}%)
                              </span>
                            </div>

                            <div className="flex items-center gap-1 opacity-0 group-hover/path:opacity-100 transition-opacity">
                              <button
                                onClick={() => handleEditPath(path)}
                                className="font-mono text-[8px] uppercase text-[#aebbb4] hover:text-[#00e084] transition-colors"
                                type="button"
                              >
                                Edit
                              </button>
                              <span className="text-[#202c28] text-[8px]">|</span>
                              <button
                                onClick={() => handleDeletePath(path.id)}
                                className="font-mono text-[8px] uppercase text-[#74837c] hover:text-[#ff5d55] transition-colors"
                                type="button"
                              >
                                Del
                              </button>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-[10px] text-[#54635c] italic font-mono">
                          No contact channels defined.
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-[#202c28]/50 pt-3">
                  <div className="flex items-center gap-2">
                    {dm.email && (
                      <a href={`mailto:${dm.email}`} className="font-mono text-[10px] text-[#00e084] border border-[#00e084]/20 bg-[#00e084]/5 px-2 py-0.5 hover:bg-[#00e084]/20 transition-colors">
                        EMAIL
                      </a>
                    )}
                    {dm.linkedin && (
                      <a href={dm.linkedin} target="_blank" rel="noopener noreferrer" className="font-mono text-[10px] text-[#00c8ff] border border-[#00c8ff]/20 bg-[#00c8ff]/5 px-2 py-0.5 hover:bg-[#00c8ff]/20 transition-colors">
                        LINKEDIN
                      </a>
                    )}
                    <span className="font-mono text-[9px] text-[#74837c] uppercase">
                      src: {dm.entry_source}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleEdit(dm)}
                      className="font-mono text-[10px] uppercase text-[#aebbb4] hover:text-[#00e084] transition-colors flex items-center gap-1"
                      type="button"
                    >
                      <Edit2 size={10} /> Edit
                    </button>
                    <span className="text-[#202c28]">|</span>
                    <button
                      onClick={() => handleDelete(dm.id)}
                      className="font-mono text-[10px] uppercase text-[#74837c] hover:text-[#ff5d55] transition-colors flex items-center gap-1"
                      type="button"
                    >
                      <Trash2 size={10} /> Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-md border border-[#1d2825] bg-[#0d1111] p-6 shadow-[0_0_50px_rgba(0,255,150,0.1)]">
            <div className="mb-4 flex items-center justify-between border-b border-[#1d2825] pb-3">
              <h3 className="font-mono text-sm font-bold uppercase tracking-[0.14em] text-[#00d277]">
                {editingDm ? "Edit Decision Maker" : "Add Decision Maker"}
              </h3>
              <button
                onClick={closeModal}
                className="text-[#74837c] hover:text-white font-mono text-xs transition-colors"
                type="button"
              >
                [CLOSE]
              </button>
            </div>
            
            <form onSubmit={handleSubmit} className="space-y-4">
              <label className="block">
                <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">
                  Full Name *
                </span>
                <input
                  className="h-9 w-full border border-[#293733] bg-[#121516] px-3 text-sm text-white focus:border-[#00e084] focus:outline-none transition-colors"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  placeholder="e.g. Jane Doe"
                />
              </label>

              <label className="block">
                <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">
                  Role/Title *
                </span>
                <input
                  className="h-9 w-full border border-[#293733] bg-[#121516] px-3 text-sm text-white focus:border-[#00e084] focus:outline-none transition-colors"
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  required
                  placeholder="e.g. Founder & CEO"
                />
              </label>

              <label className="block">
                <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">
                  Email Address
                </span>
                <input
                  className="h-9 w-full border border-[#293733] bg-[#121516] px-3 text-sm text-white focus:border-[#00e084] focus:outline-none transition-colors"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  type="email"
                  placeholder="e.g. jane@company.com"
                />
              </label>

              <label className="block">
                <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">
                  LinkedIn URL
                </span>
                <input
                  className="h-9 w-full border border-[#293733] bg-[#121516] px-3 text-sm text-white focus:border-[#00e084] focus:outline-none transition-colors"
                  value={formData.linkedin}
                  onChange={(e) => setFormData({ ...formData, linkedin: e.target.value })}
                  placeholder="e.g. https://linkedin.com/in/janedoe"
                />
              </label>

              <label className="block">
                <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">
                  Entry Source
                </span>
                <select
                  className="h-9 w-full border border-[#293733] bg-[#121516] px-2 font-mono text-xs text-white focus:border-[#00e084] focus:outline-none transition-colors"
                  value={formData.entry_source}
                  onChange={(e) => setFormData({ ...formData, entry_source: e.target.value })}
                >
                  <option value="MANUAL">MANUAL</option>
                  <option value="APOLLO">APOLLO</option>
                  <option value="ROCKETREACH">ROCKETREACH</option>
                  <option value="HUNTER">HUNTER</option>
                  <option value="LINKEDIN">LINKEDIN</option>
                  <option value="WEBSITE">WEBSITE</option>
                </select>
              </label>

              <div className="flex justify-end gap-3 pt-3 border-t border-[#1d2825]">
                <button
                  onClick={closeModal}
                  className="h-9 px-4 border border-[#293733] bg-[#101516] text-[#aebbb4] font-mono text-xs uppercase hover:text-white transition-colors"
                  type="button"
                >
                  Cancel
                </button>
                <button
                  className="h-9 px-4 border border-[#00b86b] bg-[#07351f] text-[#00e084] font-mono text-xs uppercase hover:bg-[#00b86b] hover:text-black transition-colors"
                  type="submit"
                >
                  Save Contact
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isPathOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-md border border-[#1d2825] bg-[#0d1111] p-6 shadow-[0_0_50px_rgba(0,255,150,0.1)]">
            <div className="mb-4 flex items-center justify-between border-b border-[#1d2825] pb-3">
              <h3 className="font-mono text-sm font-bold uppercase tracking-[0.14em] text-[#00d277]">
                {editingPath ? "Edit Contact Path" : "Add Contact Path"}
              </h3>
              <button
                onClick={closePathModal}
                className="text-[#74837c] hover:text-white font-mono text-xs transition-colors"
                type="button"
              >
                [CLOSE]
              </button>
            </div>

            <form onSubmit={handlePathSubmit} className="space-y-4">
              <label className="block">
                <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">
                  Path Type *
                </span>
                <select
                  className="h-9 w-full border border-[#293733] bg-[#121516] px-2 font-mono text-xs text-white focus:border-[#00e084] focus:outline-none transition-colors"
                  value={pathFormData.type}
                  onChange={(e) => setPathFormData({ ...pathFormData, type: e.target.value as ContactPathType })}
                >
                  <option value="EMAIL">EMAIL</option>
                  <option value="LINKEDIN">LINKEDIN</option>
                  <option value="PHONE">PHONE</option>
                  <option value="WEBSITE_FORM">WEBSITE_FORM</option>
                </select>
              </label>

              <label className="block">
                <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">
                  Address / Value *
                </span>
                <input
                  className="h-9 w-full border border-[#293733] bg-[#121516] px-3 text-sm text-white focus:border-[#00e084] focus:outline-none transition-colors"
                  value={pathFormData.value}
                  onChange={(e) => setPathFormData({ ...pathFormData, value: e.target.value })}
                  required
                  placeholder="e.g. name@domain.com or URL"
                />
              </label>

              <label className="block">
                <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">
                  Data Source
                </span>
                <select
                  className="h-9 w-full border border-[#293733] bg-[#121516] px-2 font-mono text-xs text-white focus:border-[#00e084] focus:outline-none transition-colors"
                  value={pathFormData.source}
                  onChange={(e) => setPathFormData({ ...pathFormData, source: e.target.value })}
                >
                  <option value="MANUAL">MANUAL</option>
                  <option value="APOLLO">APOLLO</option>
                  <option value="ROCKETREACH">ROCKETREACH</option>
                  <option value="HUNTER">HUNTER</option>
                  <option value="LINKEDIN">LINKEDIN</option>
                  <option value="WEBSITE">WEBSITE</option>
                </select>
              </label>

              <label className="block">
                <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">
                  Confidence Score (0-100) *
                </span>
                <input
                  type="number"
                  min="0"
                  max="100"
                  className="h-9 w-full border border-[#293733] bg-[#121516] px-3 text-sm text-white focus:border-[#00e084] focus:outline-none transition-colors"
                  value={pathFormData.confidence}
                  onChange={(e) => setPathFormData({ ...pathFormData, confidence: Number(e.target.value) })}
                  required
                />
              </label>

              <div className="flex items-center gap-6 py-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    className="accent-[#00e084]"
                    checked={pathFormData.verified}
                    onChange={(e) => {
                      const nowStr = e.target.checked ? new Date().toISOString() : "";
                      setPathFormData({
                        ...pathFormData,
                        verified: e.target.checked,
                        last_verified_at: nowStr
                      });
                    }}
                  />
                  <span className="font-mono text-xs text-[#dbe5df] select-none">Verified Channel</span>
                </label>
              </div>

              {pathFormData.verified && (
                <label className="block">
                  <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]">
                    Last Verified Timestamp (ISO)
                  </span>
                  <input
                    className="h-9 w-full border border-[#293733] bg-[#121516] px-3 text-sm text-white focus:border-[#00e084] focus:outline-none transition-colors"
                    value={pathFormData.last_verified_at}
                    onChange={(e) => setPathFormData({ ...pathFormData, last_verified_at: e.target.value })}
                    placeholder="e.g. ISO-8601 string"
                  />
                </label>
              )}

              <div className="flex justify-end gap-3 pt-3 border-t border-[#1d2825]">
                <button
                  onClick={closePathModal}
                  className="h-9 px-4 border border-[#293733] bg-[#101516] text-[#aebbb4] font-mono text-xs uppercase hover:text-white transition-colors"
                  type="button"
                >
                  Cancel
                </button>
                <button
                  className="h-9 px-4 border border-[#00b86b] bg-[#07351f] text-[#00e084] font-mono text-xs uppercase hover:bg-[#00b86b] hover:text-black transition-colors"
                  type="submit"
                >
                  Save Path
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
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

function ReportWorkspace({
  report,
  markdown,
  onRefresh,
  filterPdmCode,
  filterOfferId,
  onPdmChange,
  onOfferChange,
  offers,
  segments
}: {
  report: CampaignIntelligenceReport | null;
  markdown: string;
  onRefresh: (pdmCode?: string, offerId?: string) => Promise<void>;
  filterPdmCode: string;
  filterOfferId: string;
  onPdmChange: (code: string) => void;
  onOfferChange: (id: string) => void;
  offers: Offer[];
  segments: SegmentRegistry[];
}) {
  const uniquePdms = useMemo(() => {
    const pdms = segments.map((s) => s.pdm_code).filter(Boolean);
    return Array.from(new Set(pdms));
  }, [segments]);

  return (
    <Panel title="Campaign Intelligence Report" icon={<BarChart3 size={15} />} action="deterministic">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[#202c28] pb-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase text-[#738a94]">PDM Filter:</span>
            <select
              value={filterPdmCode}
              onChange={(e) => onPdmChange(e.target.value)}
              className="h-8 border border-[#202c28] bg-[#070b0c] px-2 font-mono text-xs text-[#b8c9d0] outline-none focus:border-[#00c8ff]"
            >
              <option value="">ALL PDMs</option>
              {uniquePdms.map((pdm) => (
                <option key={pdm} value={pdm}>
                  {pdm}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase text-[#738a94]">Offer Filter:</span>
            <select
              value={filterOfferId}
              onChange={(e) => onOfferChange(e.target.value)}
              className="h-8 border border-[#202c28] bg-[#070b0c] px-2 font-mono text-xs text-[#b8c9d0] outline-none focus:border-[#00c8ff]"
            >
              <option value="">ALL Offers</option>
              {offers.map((offer) => (
                <option key={offer.id} value={offer.id}>
                  {offer.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button className="inline-flex h-8 items-center gap-2 border border-[#00a9d6] bg-[#062633] px-3 font-mono text-xs uppercase text-[#00c8ff]" onClick={() => void onRefresh(filterPdmCode, filterOfferId)} type="button">
          <RefreshCw size={12} /> Refresh Report
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
  onRefresh,
  filterPdmCode,
  filterOfferId,
  onPdmChange,
  onOfferChange,
  offers,
  segments
}: {
  summary: LearningSummary | null;
  markdown: string;
  onRefresh: (pdmCode?: string, offerId?: string) => Promise<void>;
  filterPdmCode: string;
  filterOfferId: string;
  onPdmChange: (code: string) => void;
  onOfferChange: (id: string) => void;
  offers: Offer[];
  segments: SegmentRegistry[];
}) {
  const uniquePdms = useMemo(() => {
    const pdms = segments.map((s) => s.pdm_code).filter(Boolean);
    return Array.from(new Set(pdms));
  }, [segments]);

  return (
    <Panel title="Learning Intelligence" icon={<LineChart size={15} />} action="evidence validation">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[#202c28] pb-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase text-[#738a94]">PDM Filter:</span>
            <select
              value={filterPdmCode}
              onChange={(e) => onPdmChange(e.target.value)}
              className="h-8 border border-[#202c28] bg-[#070b0c] px-2 font-mono text-xs text-[#b8c9d0] outline-none focus:border-[#00c8ff]"
            >
              <option value="">ALL PDMs</option>
              {uniquePdms.map((pdm) => (
                <option key={pdm} value={pdm}>
                  {pdm}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase text-[#738a94]">Offer Filter:</span>
            <select
              value={filterOfferId}
              onChange={(e) => onOfferChange(e.target.value)}
              className="h-8 border border-[#202c28] bg-[#070b0c] px-2 font-mono text-xs text-[#b8c9d0] outline-none focus:border-[#00c8ff]"
            >
              <option value="">ALL Offers</option>
              {offers.map((offer) => (
                <option key={offer.id} value={offer.id}>
                  {offer.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button className="inline-flex h-8 items-center gap-2 border border-[#00a9d6] bg-[#062633] px-3 font-mono text-xs uppercase text-[#00c8ff]" onClick={() => void onRefresh(filterPdmCode, filterOfferId)} type="button">
          <RefreshCw size={12} /> Refresh Learning
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
