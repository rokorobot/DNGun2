from __future__ import annotations

import re


def generate_offer_hypothesis(domain_name: str) -> dict:
    domain = _normalize_domain(domain_name)
    tokens = _tokens(domain)
    category = _category(tokens)
    segments = _segments(category)
    return {
        "offer_category": category,
        "commercial_hypothesis": _hypothesis(domain, category),
        "predicted_value_range": _value_range(category),
        "target_segments": segments,
        "buyer_profiles": _buyer_profiles(category),
        "signal_profiles": _signal_profiles(category),
        "pdm": _pdm(domain, category, segments),
    }


def _normalize_domain(domain_name: str) -> str:
    return domain_name.strip().replace("https://", "").replace("http://", "").split("/")[0]


def _tokens(domain: str) -> set[str]:
    stem = domain.split(".")[0].lower()
    split_tokens = {token for token in re.split(r"[^a-z0-9]+", stem) if token}
    compact_tokens = {token for token in re.findall(r"[a-z]+|[0-9]+", stem)}
    return split_tokens | compact_tokens


def _category(tokens: set[str]) -> str:
    joined = " ".join(sorted(tokens))
    if any(token in joined for token in ["robot", "humanoid", "automation"]):
        return "Robotics Marketplace"
    if any(token in joined for token in ["chat", "agent", "copilot", "ai"]):
        return "AI Workflow Product"
    if any(token in joined for token in ["nft", "folio", "wallet", "token"]):
        return "Digital Asset Portfolio"
    if any(token in joined for token in ["notebook", "knowledge", "lm"]):
        return "Knowledge Productivity Tool"
    if any(token in joined for token in ["rent", "lease"]):
        return "Equipment Leasing Platform"
    return "Domain-Led Digital Offer"


def _segments(category: str) -> list[str]:
    mapping = {
        "Robotics Marketplace": ["Robotics", "Automation", "Humanoids"],
        "AI Workflow Product": ["AI Automation", "RevOps", "Productivity"],
        "Digital Asset Portfolio": ["Web3", "Creator Tools", "Fintech"],
        "Knowledge Productivity Tool": ["Knowledge Work", "AI Productivity", "Education"],
        "Equipment Leasing Platform": ["Leasing", "Robotics", "Operations"],
    }
    return mapping.get(category, ["Startups", "Agencies", "Operators"])


def _hypothesis(domain: str, category: str) -> str:
    templates = {
        "Robotics Marketplace": f"{domain} can position as a commercial marketplace or category hub for robotics buyers, distributors, and automation operators.",
        "AI Workflow Product": f"{domain} can anchor a focused AI workflow product for teams buying automation, agents, or assistant infrastructure.",
        "Digital Asset Portfolio": f"{domain} can package digital asset tracking, portfolio presentation, or ownership workflows for crypto-native operators.",
        "Knowledge Productivity Tool": f"{domain} can become a knowledge-work product for teams organizing AI-assisted research, notes, and workflows.",
        "Equipment Leasing Platform": f"{domain} can frame a leasing or rental marketplace for expensive operational technology assets.",
    }
    return templates.get(category, f"{domain} can be tested as a category-defining digital offer for buyers already showing budget and urgency.")


def _value_range(category: str) -> str:
    ranges = {
        "Robotics Marketplace": "$15k-$50k",
        "AI Workflow Product": "$10k-$40k",
        "Digital Asset Portfolio": "$5k-$25k",
        "Knowledge Productivity Tool": "$5k-$20k",
        "Equipment Leasing Platform": "$15k-$60k",
    }
    return ranges.get(category, "$5k-$25k")


def _buyer_profiles(category: str) -> list[dict]:
    mapping = {
        "Robotics Marketplace": [
            ("Robotics Startup Founder", "Needs category authority, buyer trust, and commercial distribution surface."),
            ("Robot Distributor", "Can use the domain as a demand capture and marketplace asset."),
            ("Automation Integrator", "Benefits from a memorable vertical domain for robotics implementation offers."),
            ("Humanoid Company", "May value category positioning as humanoid demand matures."),
        ],
        "AI Workflow Product": [
            ("AI Automation Founder", "Needs a clear product surface for automation buyers."),
            ("RevOps Automation Consultant", "Can package the domain around measurable workflow outcomes."),
            ("B2B SaaS Operator", "May use the domain as a product line or acquisition channel."),
        ],
        "Digital Asset Portfolio": [
            ("Web3 Product Founder", "Needs trustable naming around asset ownership and portfolio views."),
            ("Creator Tool Operator", "Can use the domain to frame collections, provenance, or digital identity."),
            ("Fintech Builder", "May adapt the domain for alternative asset tracking."),
        ],
    }
    rows = mapping.get(category, [
        ("Startup Founder", "Needs a memorable domain for a focused commercial wedge."),
        ("Agency Operator", "Can package the domain into a verticalized service offer."),
        ("Product Studio", "Can validate the domain as a product concept or acquisition asset."),
    ])
    return [
        {"profile_name": name, "rationale": rationale, "priority": index + 1}
        for index, (name, rationale) in enumerate(rows)
    ]


def _signal_profiles(category: str) -> list[dict]:
    mapping = {
        "Robotics Marketplace": [
            ("Robotics hiring", 1, "Hiring indicates active budget and growth in the category."),
            ("Distribution expansion", 1, "Expansion signals need for demand capture and partner visibility."),
            ("Fundraising", 2, "Fresh capital can support category asset acquisition."),
            ("Warehouse automation growth", 2, "Operational robotics demand supports marketplace positioning."),
        ],
        "AI Workflow Product": [
            ("AI automation service launch", 1, "New offers need strong naming and demand capture."),
            ("Founder posts about agents", 1, "Public narrative indicates category commitment."),
            ("Hiring automation roles", 2, "Hiring suggests budget and execution urgency."),
            ("Case studies mentioning ROI", 2, "ROI language signals commercial maturity."),
        ],
    }
    rows = mapping.get(category, [
        ("Founder category content", 1, "Founder narrative indicates possible strategic fit."),
        ("New service launch", 1, "Launch activity can create naming and positioning needs."),
        ("Recent funding", 2, "Capital event may support asset purchase."),
        ("Visible buyer channel", 3, "Contactability makes validation practical."),
    ])
    return [
        {"signal_name": name, "tier": tier, "rationale": rationale}
        for name, tier, rationale in rows
    ]


def _pdm(domain: str, category: str, segments: list[str]) -> dict:
    slug = re.sub(r"[^A-Z0-9]+", "-", category.upper()).strip("-")
    return {
        "code": f"PDM-{slug}",
        "name": f"{category} Buyer Model",
        "summary": f"Discovery model for identifying likely buyers of {domain} based on category fit, commercial urgency, and observable buying signals.",
        "target_segments": segments,
    }
