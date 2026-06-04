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
