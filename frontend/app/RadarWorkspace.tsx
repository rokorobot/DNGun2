"use client";

import { Check, ExternalLink, Pencil, Radar, Satellite, Upload, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  acceptOpportunity,
  dismissOpportunity,
  importPortfolio,
  listOpportunities,
  listPortfolio,
  Opportunity,
  PortfolioDomain,
  scanRadar,
  SegmentRegistry,
  updateWatchProfile
} from "../lib/api";

// MVP 2.0 Opportunity Radar: portfolio -> news scan -> matched buyers -> accept as prospect.

const input = "h-9 w-full border border-[#293733] bg-[#121516] px-2 text-sm text-white";
const label = "mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-[#74837c]";
const button = (tone: "green" | "cyan" | "red" | "gray") =>
  `inline-flex h-9 items-center justify-center gap-2 border px-3 font-mono text-xs uppercase disabled:opacity-40 ${
    {
      green: "border-[#00a85f] bg-[#06351f] text-[#00e084]",
      cyan: "border-[#00a9d6] bg-[#062633] text-[#00c8ff]",
      red: "border-[#8f3d32] bg-[#24110f] text-[#ff7a6b]",
      gray: "border-[#293733] bg-[#101516] text-[#aebbb4]"
    }[tone]
  }`;

const SCAN_SECONDS_PER_QUERY = 6;

function Box({ title, icon, action, children }: { title: string; icon: React.ReactNode; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="border border-[#1d2825] bg-[#0b0f10]">
      <div className="flex items-center gap-2 border-b border-[#1d2825] px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.14em] text-white">
        <span className="text-[#00d277]">{icon}</span>
        {title}
        {action ? <span className="ml-auto">{action}</span> : null}
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
    // not JSON
  }
  return raw;
}

const splitList = (value: string) =>
  value
    .split(/[,;|]/)
    .map((part) => part.trim())
    .filter(Boolean);

export default function RadarWorkspace({ segments, onProspectCreated }: { segments: SegmentRegistry[]; onProspectCreated: () => void }) {
  const [portfolio, setPortfolio] = useState<PortfolioDomain[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [importText, setImportText] = useState("");
  const [notice, setNotice] = useState<{ text: string; ok: boolean } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [domains, opps] = await Promise.all([listPortfolio(), listOpportunities("NEW")]);
    setPortfolio(domains);
    setOpportunities(opps);
  }, []);

  useEffect(() => {
    void refresh().catch((error) => setNotice({ text: errorText(error), ok: false }));
  }, [refresh]);

  async function run(key: string, action: () => Promise<string>) {
    setBusy(key);
    setNotice(null);
    try {
      const text = await action();
      await refresh();
      setNotice({ text, ok: true });
    } catch (error) {
      setNotice({ text: errorText(error), ok: false });
    } finally {
      setBusy(null);
    }
  }

  const scanText = (summary: Awaited<ReturnType<typeof scanRadar>>) =>
    `Scanned ${summary.domains} domain(s), ${summary.articles} article(s): ${summary.new_opportunities} new opportunity(ies).` +
    (summary.errors.length ? ` ${summary.errors.length} search(es) failed: ${summary.errors[0]}` : "");

  const queriesForAll = portfolio.reduce((total, row) => total + Math.max(1, row.markets.length), 0);

  return (
    <div className="space-y-3">
      {notice ? (
        <div
          className={`border p-3 text-sm ${notice.ok ? "border-[#00a85f] bg-[#06231a] text-[#9ff0c8]" : "border-[#8f3d32] bg-[#24110f] text-[#ffad99]"}`}
          role="status"
        >
          {notice.text}
        </div>
      ) : null}

      <Box
        title={`Opportunities · ${opportunities.length} new`}
        icon={<Satellite size={15} />}
        action={
          <button
            className={button("cyan")}
            disabled={busy !== null || portfolio.length === 0}
            onClick={() => void run("scan-all", async () => scanText(await scanRadar()))}
            title={`About ${queriesForAll * SCAN_SECONDS_PER_QUERY} seconds`}
            type="button"
          >
            <Radar size={14} /> {busy === "scan-all" ? "Scanning…" : `Scan all (~${Math.ceil((queriesForAll * SCAN_SECONDS_PER_QUERY) / 60)} min)`}
          </button>
        }
      >
        {opportunities.length === 0 ? (
          <p className="text-sm text-[#74837c]">
            No new opportunities. Import domains below, then scan. The radar looks at the last 7 days of news.
          </p>
        ) : null}
        {opportunities.map((opp) => (
          <OpportunityCard
            busy={busy !== null}
            key={opp.id}
            onAccept={(data) =>
              void run(opp.id, async () => {
                await acceptOpportunity(opp.id, data);
                onProspectCreated();
                return `${data.company_name} added as a prospect, with the news as a signal and evidence.`;
              })
            }
            onDismiss={() =>
              void run(opp.id, async () => {
                await dismissOpportunity(opp.id);
                return "Dismissed.";
              })
            }
            opportunity={opp}
            segments={segments}
          />
        ))}
      </Box>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Box title={`Portfolio · ${portfolio.length} domains`} icon={<Radar size={15} />}>
          {portfolio.length === 0 ? <p className="text-sm text-[#74837c]">No domains yet.</p> : null}
          <div className="space-y-2">
            {portfolio.map((row) =>
              editing === row.offer_id ? (
                <ProfileEditor
                  busy={busy !== null}
                  key={row.offer_id}
                  onCancel={() => setEditing(null)}
                  onSave={(data) =>
                    void run(row.offer_id, async () => {
                      await updateWatchProfile(row.offer_id, data);
                      setEditing(null);
                      return `Watch profile for ${row.domain} saved.`;
                    })
                  }
                  row={row}
                />
              ) : (
                <div className="flex flex-wrap items-center gap-2 border border-[#202c28] bg-[#101516] p-2" key={row.offer_id}>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm text-white">{row.domain}</span>
                      {row.new_opportunities ? (
                        <span className="border border-[#00d277] px-1.5 font-mono text-[10px] text-[#00e084]">{row.new_opportunities} new</span>
                      ) : null}
                      {row.price ? <span className="font-mono text-[11px] text-[#74837c]">{row.price.toLocaleString()}</span> : null}
                    </div>
                    <div className="mt-1 text-xs text-[#aebbb4]">
                      <span className="text-[#74837c]">watch:</span> {row.keywords.join(", ")} <span className="text-[#74837c]">· in</span>{" "}
                      {row.markets.join(", ")}
                      {row.origin === "AUTO" ? <span className="text-[#5d6b65]"> (auto)</span> : null}
                    </div>
                    <div className="text-[11px] text-[#5d6b65]">
                      {row.last_scanned_at ? `last scan ${row.last_scanned_at.slice(0, 16).replace("T", " ")}` : "never scanned"}
                    </div>
                  </div>
                  <button aria-label={`Edit ${row.domain}`} className={button("gray")} disabled={busy !== null} onClick={() => setEditing(row.offer_id)} type="button">
                    <Pencil size={13} />
                  </button>
                  <button
                    className={button("cyan")}
                    disabled={busy !== null}
                    onClick={() => void run(row.offer_id, async () => scanText(await scanRadar([row.offer_id])))}
                    type="button"
                  >
                    {busy === row.offer_id ? "Scanning…" : "Scan"}
                  </button>
                </div>
              )
            )}
          </div>
        </Box>

        <Box title="Import domains" icon={<Upload size={15} />}>
          <p className="text-xs leading-5 text-[#aebbb4]">
            One domain per line, or a CSV with a header row. Optional columns: <span className="font-mono">price, markets, keywords, industry, notes</span>.
            Markets: country codes (DE, US, CZ…), regions (DACH, EU, NORDICS, CEE) or GLOBAL. Left empty, they come from the domain ending.
          </p>
          <label className="block">
            <span className={label}>Paste or load a file</span>
            <textarea
              className="w-full border border-[#293733] bg-[#121516] p-2 font-mono text-xs text-white"
              onChange={(e) => setImportText(e.target.value)}
              placeholder={"domain;price;markets\nrobotstore.app;12000;DACH, US\nsolarlease.de"}
              rows={7}
              value={importText}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <label className={`${button("gray")} cursor-pointer`}>
              Load file
              <input
                accept=".csv,.txt,text/csv,text/plain"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (file) setImportText(await file.text());
                  e.target.value = "";
                }}
                type="file"
              />
            </label>
            <button
              className={button("green")}
              disabled={busy !== null || !importText.trim()}
              onClick={() =>
                void run("import", async () => {
                  const result = await importPortfolio(importText);
                  setImportText("");
                  return (
                    `Imported ${result.created.length} new, updated ${result.updated.length}.` +
                    (result.invalid.length ? ` Skipped ${result.invalid.length}: ${result.invalid.slice(0, 5).join(", ")}` : "")
                  );
                })
              }
              type="button"
            >
              <Upload size={14} /> Import
            </button>
          </div>
        </Box>
      </div>
    </div>
  );
}

function OpportunityCard({
  opportunity,
  segments,
  busy,
  onAccept,
  onDismiss
}: {
  opportunity: Opportunity;
  segments: SegmentRegistry[];
  busy: boolean;
  onAccept: (data: { company_name: string; segment: string; website?: string }) => void;
  onDismiss: () => void;
}) {
  const [company, setCompany] = useState(opportunity.company_name ?? "");
  const [segment, setSegment] = useState(segments[0]?.code ?? "");
  const [website, setWebsite] = useState("");
  useEffect(() => {
    if (!segment && segments[0]) setSegment(segments[0].code);
  }, [segments, segment]);

  const strong = opportunity.match_type === "NAME";
  return (
    <div className={`border p-3 ${strong ? "border-[#00a85f] bg-[#071a12]" : "border-[#293733] bg-[#101516]"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-lg font-bold text-[#00e084]">{opportunity.score}</span>
        <span className="font-mono text-sm text-white">{opportunity.domain}</span>
        <span className="border border-[#293733] px-1.5 font-mono text-[10px] uppercase text-[#aebbb4]">{opportunity.event_type ?? "mention"}</span>
        {strong ? <span className="border border-[#00d277] px-1.5 font-mono text-[10px] uppercase text-[#00e084]">name match</span> : null}
        <span className="ml-auto font-mono text-[11px] text-[#74837c]">
          {opportunity.news.source_domain} · {opportunity.news.source_country ?? ""} · {opportunity.news.published_at?.slice(0, 10)}
        </span>
      </div>
      <a className="mt-2 flex items-start gap-1 text-sm text-[#dce8e1] hover:text-[#00c8ff]" href={opportunity.news.url} rel="noreferrer" target="_blank">
        {opportunity.news.title} <ExternalLink className="mt-1 shrink-0" size={12} />
      </a>
      <ul className="mt-1 font-mono text-[11px] text-[#74837c]">
        {opportunity.explanation.map((line, index) => (
          <li key={index}>{line}</li>
        ))}
      </ul>
      <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)_auto_auto]">
        <input aria-label="Company name" className={input} onChange={(e) => setCompany(e.target.value)} placeholder="Company name" value={company} />
        <select aria-label="Segment" className={input} onChange={(e) => setSegment(e.target.value)} value={segment}>
          {segments.map((s) => (
            <option key={s.code} value={s.code}>
              {s.label}
            </option>
          ))}
        </select>
        <input aria-label="Website" className={input} onChange={(e) => setWebsite(e.target.value)} placeholder="Website" value={website} />
        <button
          className={button("green")}
          disabled={busy || !company.trim() || !segment}
          onClick={() => onAccept({ company_name: company.trim(), segment, ...(website.trim() ? { website: website.trim() } : {}) })}
          type="button"
        >
          <Check size={14} /> Accept
        </button>
        <button className={button("red")} disabled={busy} onClick={onDismiss} type="button">
          <X size={14} /> Dismiss
        </button>
      </div>
    </div>
  );
}

function ProfileEditor({
  row,
  busy,
  onSave,
  onCancel
}: {
  row: PortfolioDomain;
  busy: boolean;
  onSave: (data: { keywords: string[]; markets: string[]; industry: string | null }) => void;
  onCancel: () => void;
}) {
  const [keywords, setKeywords] = useState(row.keywords.join(", "));
  const [markets, setMarkets] = useState(row.markets.join(", "));
  const [industry, setIndustry] = useState(row.industry ?? "");
  return (
    <div className="space-y-2 border border-[#00a9d6] bg-[#081a20] p-2">
      <div className="font-mono text-sm text-white">{row.domain}</div>
      <div className="grid gap-2 md:grid-cols-3">
        <label className="block">
          <span className={label}>Keywords</span>
          <input className={input} onChange={(e) => setKeywords(e.target.value)} value={keywords} />
        </label>
        <label className="block">
          <span className={label}>Markets</span>
          <input className={input} onChange={(e) => setMarkets(e.target.value)} placeholder="GLOBAL, DACH, US…" value={markets} />
        </label>
        <label className="block">
          <span className={label}>Industry</span>
          <input className={input} onChange={(e) => setIndustry(e.target.value)} value={industry} />
        </label>
      </div>
      <div className="flex gap-2">
        <button
          className={button("green")}
          disabled={busy}
          onClick={() => onSave({ keywords: splitList(keywords), markets: splitList(markets), industry: industry.trim() || null })}
          type="button"
        >
          Save
        </button>
        <button className={button("gray")} onClick={onCancel} type="button">
          Cancel
        </button>
      </div>
    </div>
  );
}
