export type Segment = "AI_AUTOMATION" | "REVOPS" | "SEO" | "WEBFLOW";

export type Prospect = {
  id: string;
  company_name: string;
  website?: string | null;
  segment: Segment;
  founder_name?: string | null;
  founder_linkedin?: string | null;
  team_size?: number | null;
  offer_value_estimate?: number | null;
  contact_path?: string | null;
  status: string;
  created_at: string;
};

export type Signal = {
  id: string;
  prospect_id: string;
  signal_type: string;
  tier: 1 | 2 | 3;
  score: number;
  source_url?: string | null;
  observed_at: string;
  notes?: string | null;
  created_at: string;
};

export type ScoreExplanation = {
  source_type: "SIGNAL" | "ALPHA_SIGNAL" | "DISQUALIFIER" | "SCORE_BAND";
  source_code: string;
  label: string;
  tier?: number | null;
  impact: number;
  notes?: string | null;
};

export type ProspectScore = {
  id?: string;
  prospect_id: string;
  tier1_total: number;
  tier2_total: number;
  tier3_total: number;
  base_score: number;
  alpha_matches: string[];
  alpha_bonus: number;
  final_score: number;
  decision: string;
  explanation: ScoreExplanation[];
  calculated_at: string;
};

export type RateSummary = {
  count: number;
  contacted_count: number;
  replied_count: number;
  call_booked_count: number;
  proposal_requested_count: number;
  paid_pilot_count: number;
  reply_rate: number;
  call_booked_rate: number;
  proposal_requested_rate: number;
  paid_pilot_rate: number;
};

export type CampaignIntelligenceReport = {
  total_prospects: number;
  contacted_count: number;
  reply_rate: number;
  call_booked_rate: number;
  proposal_requested_rate: number;
  paid_pilot_rate: number;
  performance_by_score_band: Record<string, RateSummary>;
  performance_by_alpha_signal: Record<string, RateSummary>;
  evidence_entries_created: number;
  confidence_before?: number | null;
  confidence_after?: number | null;
  confidence_delta?: number | null;
};

export type EvidenceEntry = {
  id: string;
  project: string;
  evidence_type: string;
  evidence: string;
  impact: number;
  source?: string | null;
  created_at: string;
};

export type CampaignBatch = {
  id: string;
  name: string;
  segment?: Segment | null;
  status: "DRAFT" | "ACTIVE" | "COMPLETED" | "ARCHIVED";
  notes?: string | null;
  created_at: string;
};

export type CampaignBatchProspect = {
  id: string;
  campaign_batch_id: string;
  prospect_id: string;
  created_at: string;
};

export type CampaignOutcome = {
  id: string;
  campaign_batch_id: string;
  prospect_id: string;
  contacted: boolean;
  replied: boolean;
  call_booked: boolean;
  proposal_requested: boolean;
  paid_pilot: boolean;
  lost_deal: boolean;
  outcome_notes?: string | null;
  recorded_at: string;
};

export type SignalPerformance = {
  signalType: string;
  timesSeen: number;
  contacted: number;
  replied: number;
  callBooked: number;
  proposalRequested: number;
  paidPilot: number;
  replyRate: number;
  callRate: number;
  proposalRate: number;
  pilotRate: number;
  confidence: string;
  recommendation: string;
};

export type AlphaSignalPerformance = {
  code: string;
  name: string;
  timesMatched: number;
  contacted: number;
  replied: number;
  callBooked: number;
  proposalRequested: number;
  paidPilot: number;
  replyRate: number;
  callRate: number;
  proposalRate: number;
  pilotRate: number;
  confidence: string;
  recommendation: string;
};

export type ScoreBandValidation = {
  scoreBand: string;
  prospectsInBand: number;
  contacted: number;
  replied: number;
  callBooked: number;
  proposalRequested: number;
  paidPilot: number;
  replyRate: number;
  callRate: number;
  proposalRate: number;
  pilotRate: number;
  confidence: string;
  recommendation: string;
};

export type LearningSummary = {
  topPerformingSignals: SignalPerformance[];
  weakSignals: SignalPerformance[];
  topAlphaSignals: AlphaSignalPerformance[];
  weakAlphaSignals: AlphaSignalPerformance[];
  scoreBandValidation: ScoreBandValidation[];
  recommendedRuleChanges: string[];
};

export type Offer = {
  id: string;
  name: string;
  offer_type: "DOMAIN_NAME";
  description?: string | null;
  estimated_value?: number | null;
  status: "DRAFT" | "PROPOSED" | "PROFILED" | "VALIDATING" | "ARCHIVED";
  created_at: string;
};

export type OfferEvaluationProposal = {
  id: string;
  offer_id: string;
  provider: string;
  model?: string | null;
  mode: "DETERMINISTIC" | "LLM_ASSISTED";
  raw_domain: string;
  normalized_domain: string;
  primary_category: string;
  confidence_score: number;
  confidence_label: string;
  reasoning: string[];
  alternative_categories: string[];
  proposed_profile_json: {
    primary_category: string;
    confidence_score: number;
    confidence_label: string;
    commercial_hypothesis: string;
    predicted_value_range: string;
    target_segments: string[];
    buyer_profiles: Array<{ profile_name: string; rationale: string; priority: number }>;
    signal_profiles: Array<{ signal_name: string; tier: 1 | 2 | 3; rationale: string }>;
    pdm: { code: string; name: string; summary: string; target_segments: string[] };
    reasoning: string[];
    alternative_categories: string[];
  };
  status: "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "SUPERSEDED";
  created_at: string;
  reviewed_at?: string | null;
  review_notes?: string | null;
};

export type OfferIntelligenceProfile = {
  offer: Offer;
  profile: {
    id: string;
    offer_id: string;
    offer_category: string;
    commercial_hypothesis: string;
    predicted_value_range: string;
    target_segments: string[];
    created_at: string;
  };
  buyerProfiles: Array<{
    id: string;
    offer_id: string;
    profile_name: string;
    rationale: string;
    priority: number;
    created_at: string;
  }>;
  signalProfiles: Array<{
    id: string;
    offer_id: string;
    signal_name: string;
    tier: 1 | 2 | 3;
    rationale: string;
    created_at: string;
  }>;
  pdm: {
    id: string;
    offer_id: string;
    code: string;
    name: string;
    summary: string;
    target_segments: string[];
    created_at: string;
  };
};

export type OfferProspectFit = {
  id: string;
  offer_id: string;
  prospect_id: string;
  segment_fit_score: number;
  buyer_profile_fit_score: number;
  signal_fit_score: number;
  total_fit_score: number;
  decision: "STRONG_FIT" | "POSSIBLE_FIT" | "WEAK_FIT" | "DISQUALIFIED";
  explanation: string[];
  created_at: string;
};

export type AlphaSignalRule = {
  code: string;
  name: string;
  description?: string;
  required_signals: string[];
  bonus_score: number;
  validation_status?: string;
};

export type ProspectAlphaSignal = {
  id: string;
  prospect_id: string;
  alpha_signal_id: string;
  alpha_signal_code: string;
  alpha_signal_name: string;
  bonus_score: number;
  notes?: string | null;
  created_at: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/backend-api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function listProspects() {
  return request<Prospect[]>("/prospects");
}

export function createProspect(data: {
  company_name: string;
  segment: Segment;
  website?: string;
  founder_name?: string;
  contact_path?: string;
}) {
  return request<Prospect>("/prospects", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listSignals(prospectId: string) {
  return request<Signal[]>(`/prospects/${prospectId}/signals`);
}

export function addSignal(
  prospectId: string,
  data: { signal_type: string; tier: 1 | 2 | 3; score: number; notes?: string }
) {
  return request<Signal>(`/prospects/${prospectId}/signals`, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function calculateScore(prospectId: string) {
  return request<ProspectScore>(`/prospects/${prospectId}/score?persist=true`, {
    method: "POST"
  });
}

export function listProspectScores(prospectId: string) {
  return request<ProspectScore[]>(`/prospects/${prospectId}/scores`);
}

export function getCampaignIntelligenceReport() {
  return request<CampaignIntelligenceReport>("/reports/campaign-intelligence");
}

export function listEvidenceEntries() {
  return request<EvidenceEntry[]>("/evidence-entries");
}

export function createEvidenceEntry(data: {
  evidence_type: string;
  evidence: string;
  impact: number;
  source?: string;
}) {
  return request<EvidenceEntry>("/evidence-entries", {
    method: "POST",
    body: JSON.stringify({
      project: "DNGun",
      ...data
    })
  });
}

export function listCampaignBatches() {
  return request<CampaignBatch[]>("/campaign-batches");
}

export function listCampaignBatchProspects(campaignBatchId: string) {
  return request<CampaignBatchProspect[]>(`/campaign-batches/${campaignBatchId}/prospects`);
}

export function listCampaignOutcomes(campaignBatchId?: string) {
  const path = campaignBatchId
    ? `/campaign-outcomes?campaign_batch_id=${encodeURIComponent(campaignBatchId)}`
    : "/campaign-outcomes";
  return request<CampaignOutcome[]>(path);
}

export function createCampaignOutcome(data: CampaignOutcomePayload) {
  return request<CampaignOutcome>("/campaign-outcomes", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function updateCampaignOutcome(campaignOutcomeId: string, data: CampaignOutcomePayload) {
  return request<CampaignOutcome>(`/campaign-outcomes/${campaignOutcomeId}`, {
    method: "PUT",
    body: JSON.stringify(data)
  });
}

export function getLearningSummary() {
  return request<LearningSummary>("/learning/summary");
}

export function createOffer(data: {
  name: string;
  offer_type?: "DOMAIN_NAME";
  description?: string;
  estimated_value?: number;
}) {
  return request<Offer>("/offers", {
    method: "POST",
    body: JSON.stringify({
      offer_type: "DOMAIN_NAME",
      ...data
    })
  });
}

export function listOffers() {
  return request<Offer[]>("/offers");
}

export function evaluateOffer(offerId: string, mode: "DETERMINISTIC" | "LLM_ASSISTED") {
  return request<OfferEvaluationProposal>(`/offers/${offerId}/evaluate`, {
    method: "POST",
    body: JSON.stringify({ mode })
  });
}

export function listOfferProposals(offerId: string) {
  return request<OfferEvaluationProposal[]>(`/offers/${offerId}/proposals`);
}

export function approveOfferProposal(offerId: string, proposalId: string, review_notes?: string) {
  return request<OfferIntelligenceProfile>(`/offers/${offerId}/proposals/${proposalId}/approve`, {
    method: "POST",
    body: JSON.stringify({ review_notes })
  });
}

export function rejectOfferProposal(offerId: string, proposalId: string, review_notes?: string) {
  return request<OfferEvaluationProposal>(`/offers/${offerId}/proposals/${proposalId}/reject`, {
    method: "POST",
    body: JSON.stringify({ review_notes })
  });
}

export function getOfferIntelligenceProfile(offerId: string) {
  return request<OfferIntelligenceProfile>(`/offers/${offerId}/intelligence-profile`);
}

export function calculateOfferProspectFits(offerId: string) {
  return request<OfferProspectFit[]>(`/offers/${offerId}/fit/prospects`, {
    method: "POST"
  });
}

export function listOfferProspectFits(offerId: string) {
  return request<OfferProspectFit[]>(`/offers/${offerId}/fit/prospects`);
}

export async function getLearningMarkdown() {
  const response = await fetch(`${API_BASE}/learning/report.md`, {
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.text();
}

export function getAlphaSignalRules() {
  return request<AlphaSignalRule[]>("/rules/alpha-signals");
}

export function listProspectAlphaSignals(prospectId: string) {
  return request<ProspectAlphaSignal[]>(`/prospects/${prospectId}/alpha-signals`);
}

export async function getCampaignIntelligenceMarkdown() {
  const response = await fetch(`${API_BASE}/reports/campaign-intelligence.md`, {
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.text();
}

export type CampaignOutcomePayload = {
  campaign_batch_id: string;
  prospect_id: string;
  contacted: boolean;
  replied: boolean;
  call_booked: boolean;
  proposal_requested: boolean;
  paid_pilot: boolean;
  lost_deal: boolean;
  outcome_notes?: string;
};
