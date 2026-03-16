import os
import json
import requests
import anthropic
from dotenv import load_dotenv
from hubspot import HubSpot
from hubspot.crm.contacts import ApiException

load_dotenv()

# ── ICP Definition ────────────────────────────────────────────────────────────

ICP = {
    "description": "B2B SaaS companies looking to automate their sales workflows",
    "ideal_industries": ["Software", "Technology", "SaaS", "FinTech", "MarTech"],
    "ideal_job_titles": ["VP of Sales", "Head of Revenue", "Sales Operations", "CRO", "CEO"],
    "ideal_company_size": "50-500 employees",
    "ideal_signals": [
        "Uses CRM tools like HubSpot or Salesforce",
        "Has a dedicated sales team",
        "Raised funding in the last 2 years",
        "Hiring for sales roles",
    ],
    "disqualifiers": [
        "Freelancer or solo operator",
        "Non-profit",
        "Government",
        "Student or job seeker",
    ],
    "scoring_rubric": {
        "10": "Perfect fit — matches all ICP criteria, strong buying signals",
        "7-9": "Good fit — matches most criteria, worth pursuing",
        "4-6": "Partial fit — some alignment, nurture or qualify further",
        "1-3": "Poor fit — few signals, low priority",
    },
}

# ── HubSpot ───────────────────────────────────────────────────────────────────

def fetch_contacts(limit=50):
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if not token:
        raise ValueError("HUBSPOT_ACCESS_TOKEN not set in environment")

    client = HubSpot(access_token=token)
    properties = [
        "firstname", "lastname", "email", "jobtitle",
        "company", "industry", "numemployees", "website",
        "lifecyclestage", "country",
    ]
    try:
        response = client.crm.contacts.basic_api.get_page(
            limit=limit, properties=properties, archived=False
        )
        return [_contact_to_dict(c) for c in response.results]
    except ApiException as e:
        print(f"HubSpot error: {e}")
        return []


def _contact_to_dict(contact) -> dict:
    p = contact.properties or {}
    return {
        "id": contact.id,
        "name": f"{p.get('firstname', '')} {p.get('lastname', '')}".strip(),
        "email": p.get("email", ""),
        "job_title": p.get("jobtitle", ""),
        "company": p.get("company", ""),
        "industry": p.get("industry", ""),
        "num_employees": p.get("numemployees", ""),
        "website": p.get("website", ""),
        "lifecycle_stage": p.get("lifecyclestage", ""),
        "country": p.get("country", ""),
    }

# ── Hunter.io Enrichment ──────────────────────────────────────────────────────

HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY")


def _extract_domain(lead: dict) -> str:
    """Pull domain from website or email."""
    website = lead.get("website", "")
    if website:
        return website.replace("https://", "").replace("http://", "").split("/")[0]
    email = lead.get("email", "")
    if "@" in email:
        return email.split("@")[1]
    return ""


def enrich_with_hunter(lead: dict) -> dict:
    """Add company data from Hunter.io domain search. Returns lead unchanged on failure."""
    if not HUNTER_API_KEY:
        return lead

    domain = _extract_domain(lead)
    if not domain:
        return lead

    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": HUNTER_API_KEY, "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})

        enriched = lead.copy()
        if not enriched.get("industry") and data.get("industry"):
            enriched["industry"] = data["industry"]
        if not enriched.get("num_employees") and data.get("employees"):
            enriched["num_employees"] = str(data["employees"])
        if not enriched.get("country") and data.get("country"):
            enriched["country"] = data["country"]

        # Extra signals for Claude to use
        enriched["hunter_data"] = {
            "organization": data.get("organization", ""),
            "description": data.get("description", ""),
            "twitter": data.get("twitter", ""),
            "linkedin": data.get("linkedin_url", ""),
            "technologies": data.get("technologies", [])[:10],
            "emails_found": data.get("emails", [{}])[0].get("value", "") if data.get("emails") else "",
        }
        return enriched

    except Exception as e:
        print(f"    Hunter.io lookup failed for {domain}: {e}")
        return lead


# ── Claude Scoring ────────────────────────────────────────────────────────────

claude = anthropic.Anthropic()


def score_lead(lead: dict) -> dict:
    prompt = f"""You are an expert B2B sales qualification specialist.

Score the following lead against our Ideal Customer Profile (ICP) on a scale of 1-10.

## ICP Definition
{json.dumps(ICP, indent=2)}

## Lead Data
{json.dumps(lead, indent=2)}

## Instructions
- Analyze how well this lead matches the ICP
- Assign a score from 1-10 using the scoring rubric
- Be concise but specific about why

Respond with a JSON object in this exact format:
{{
  "score": <integer 1-10>,
  "reasoning": "<2-3 sentence explanation>",
  "top_signals": ["<signal 1>", "<signal 2>"],
  "disqualifiers_found": ["<disqualifier if any>"]
}}"""

    response = claude.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    text = next(b.text for b in response.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip().rstrip("```").strip()

    result = json.loads(text)
    return {
        "id": lead["id"],
        "name": lead["name"],
        "email": lead["email"],
        "company": lead["company"],
        "job_title": lead["job_title"],
        "score": result.get("score", 0),
        "reasoning": result.get("reasoning", ""),
        "top_signals": result.get("top_signals", []),
        "disqualifiers_found": result.get("disqualifiers_found", []),
    }

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== HubSpot Lead Enrichment + ICP Scorer ===\n")

    print("Fetching contacts from HubSpot...")
    leads = fetch_contacts(limit=50)
    if not leads:
        print("No contacts found. Check your HUBSPOT_ACCESS_TOKEN.")
        return
    print(f"Found {len(leads)} contacts.\n")

    print("Enriching leads with Hunter.io...")
    leads = [enrich_with_hunter(lead) for lead in leads]
    print("Enrichment complete.\n")

    print("Scoring leads against ICP...")
    results = []
    for i, lead in enumerate(leads, 1):
        label = lead.get("name") or lead.get("email") or lead["id"]
        print(f"  {i}/{len(leads)}: {label}...")
        try:
            results.append(score_lead(lead))
        except Exception as e:
            print(f"    ✗ Error: {e}")

    results.sort(key=lambda x: x["score"], reverse=True)

    # Print summary table
    print(f"\n{'RANK':<5} {'NAME':<25} {'COMPANY':<20} {'SCORE'}")
    print("-" * 60)
    for i, r in enumerate(results, 1):
        name = (r['name'] or '')[:24]
        company = (r['company'] or '')[:19]
        print(f"{i:<5} {name:<25} {company:<20} {r['score']}/10")

    # Top 3 details
    print("\n--- Top 3 Details ---")
    for r in results[:3]:
        print(f"\n{r['name'] or ''} @ {r['company'] or ''} — {r['score']}/10")
        print(f"  {r['reasoning']}")
        if r["top_signals"]:
            print(f"  Signals: {', '.join(r['top_signals'])}")
        if r["disqualifiers_found"]:
            print(f"  Disqualifiers: {', '.join(r['disqualifiers_found'])}")

    # Save output
    os.makedirs("data", exist_ok=True)
    out_path = "data/scored_leads.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
