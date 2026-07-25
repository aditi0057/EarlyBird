"""
discover_boards.py  --  find REAL job boards across Greenhouse / Lever / Ashby.

WHAT IT DOES:
  Takes a big list of candidate companies (name + guessed token), probes each
  across all three providers IN PARALLEL, and keeps only the ones that are real.
  It then writes companies.json (what the monitor reads) and prints a summary
  of how many India engineering roles each has right now.

HOW TO RUN (occasionally, when you want to grow/refresh the company list):
  py discover_boards.py

  Add "--append" to MERGE with your existing companies.json instead of
  overwriting it (keeps any companies you added by hand):
  py discover_boards.py --append
"""

import os
import sys
import json
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from sources import probe
from filters import matches

HERE = os.path.dirname(os.path.abspath(__file__))
COMPANIES_FILE = os.path.join(HERE, "companies.json")

# Which providers to try, in order. First one that answers wins.
SOURCES_TO_TRY = ["greenhouse", "lever", "ashby"]

# Candidate companies: (display name, guessed token, type).
# type drives resume voice later: "tech" | "fintech" | "consulting" | "data".
# Tokens are best guesses (usually the name, lowercased, no spaces). The probe
# throws away the ones that aren't real, so over-guessing is fine.
CANDIDATES = [
    # ---- Infra / dev tools / cloud (tech) ----
    ("Databricks", "databricks", "data"), ("Snowflake", "snowflake", "data"),
    ("Confluent", "confluent", "tech"), ("HashiCorp", "hashicorp", "tech"),
    ("GitLab", "gitlab", "tech"), ("Cloudflare", "cloudflare", "tech"),
    ("Datadog", "datadog", "tech"), ("Elastic", "elastic", "tech"),
    ("MongoDB", "mongodb", "tech"), ("CockroachLabs", "cockroachlabs", "tech"),
    ("Grafana Labs", "grafanalabs", "tech"), ("Temporal", "temporal", "tech"),
    ("Nutanix", "nutanix", "tech"), ("Cohesity", "cohesity", "tech"),
    ("Rubrik", "rubrik", "tech"), ("Druva", "druva", "tech"),
    ("Okta", "okta", "tech"), ("Zscaler", "zscaler", "tech"),
    ("SumoLogic", "sumologic", "tech"), ("Samsara", "samsara", "tech"),
    ("HubSpot", "hubspot", "tech"), ("Twilio", "twilio", "tech"),
    ("Vercel", "vercel", "tech"), ("Netlify", "netlify", "tech"),
    ("Retool", "retool", "tech"), ("Hasura", "hasura", "tech"),
    ("Harness", "harness", "tech"), ("Postman", "postman", "tech"),
    ("BrowserStack", "browserstack", "tech"), ("ClickHouse", "clickhouse", "tech"),
    ("Redpanda", "redpanda", "tech"), ("Timescale", "timescale", "tech"),
    ("Weaviate", "weaviate", "tech"), ("Pinecone", "pinecone", "tech"),
    ("Airbyte", "airbyte", "data"), ("dbt Labs", "dbtlabs", "data"),
    ("Fivetran", "fivetran", "data"), ("Starburst", "starburstdata", "data"),
    ("Sourcegraph", "sourcegraph", "tech"), ("PlanetScale", "planetscale", "tech"),
    ("Supabase", "supabase", "tech"), ("Render", "render", "tech"),
    ("Grafana", "grafana", "tech"), ("Aiven", "aiven", "tech"),

    # ---- AI / ML (tech, high pay) ----
    ("OpenAI", "openai", "tech"), ("Anthropic", "anthropic", "tech"),
    ("Cohere", "cohere", "tech"), ("Mistral AI", "mistralai", "tech"),
    ("Perplexity", "perplexityai", "tech"), ("Hugging Face", "huggingface", "tech"),
    ("Scale AI", "scaleai", "tech"), ("Together AI", "togetherai", "tech"),
    ("Runway", "runwayml", "tech"), ("Hex", "hex", "data"),
    ("Modal", "modal", "tech"), ("Baseten", "baseten", "tech"),
    ("Adept", "adept", "tech"), ("Character AI", "characterai", "tech"),
    ("Anyscale", "anyscale", "tech"), ("LangChain", "langchain", "tech"),

    # ---- Consumer / product / marketplaces (tech) ----
    ("Stripe", "stripe", "fintech"), ("Airbnb", "airbnb", "tech"),
    ("Coinbase", "coinbase", "fintech"), ("Reddit", "reddit", "tech"),
    ("Pinterest", "pinterest", "tech"), ("Dropbox", "dropbox", "tech"),
    ("Figma", "figma", "tech"), ("Notion", "notion", "tech"),
    ("Canva", "canva", "tech"), ("Miro", "miro", "tech"),
    ("Grammarly", "grammarly", "tech"), ("Webflow", "webflow", "tech"),
    ("Airtable", "airtable", "tech"), ("Asana", "asana", "tech"),
    ("Discord", "discord", "tech"), ("Roblox", "roblox", "tech"),
    ("Unity", "unity", "tech"), ("DoorDash", "doordash", "tech"),
    ("Instacart", "instacart", "tech"), ("Lyft", "lyft", "tech"),
    ("Squarespace", "squarespace", "tech"), ("Wayfair", "wayfair", "tech"),
    ("Zendesk", "zendesk", "tech"), ("Amplitude", "amplitude", "tech"),
    ("Segment", "segment", "tech"), ("Gusto", "gusto", "tech"),
    ("Nextdoor", "nextdoor", "tech"), ("Opendoor", "opendoor", "tech"),
    ("Toast", "toast", "tech"), ("Benchling", "benchling", "tech"),
    ("Gong", "gong", "tech"), ("Sprinklr", "sprinklr", "tech"),
    ("Linear", "linear", "tech"), ("Vanta", "vanta", "tech"),
    ("Mercury", "mercury", "fintech"), ("Deel", "deel", "tech"),
    ("PostHog", "posthog", "tech"), ("Replit", "replit", "tech"),
    ("Loom", "loom", "tech"), ("Calendly", "calendly", "tech"),
    ("1Password", "1password", "tech"), ("Atlassian", "atlassian", "tech"),

    # ---- Fintech (tech voice, finance domain) ----
    ("Plaid", "plaid", "fintech"), ("Robinhood", "robinhood", "fintech"),
    ("Brex", "brex", "fintech"), ("Ramp", "ramp", "fintech"),
    ("Affirm", "affirm", "fintech"), ("Wealthfront", "wealthfront", "fintech"),
    ("Chime", "chime", "fintech"), ("Marqeta", "marqeta", "fintech"),
    ("Wise", "wise", "fintech"), ("Revolut", "revolut", "fintech"),
    ("Flexport", "flexport", "tech"), ("Nubank", "nubank", "fintech"),

    # ---- Indian unicorns / high-pay (tech + fintech) ----
    ("Razorpay", "razorpay", "fintech"), ("PhonePe", "phonepe", "fintech"),
    ("CRED", "cred", "fintech"), ("Groww", "groww", "fintech"),
    ("Zerodha", "zerodha", "fintech"), ("Upstox", "upstox", "fintech"),
    ("Meesho", "meesho", "tech"), ("Zomato", "zomato", "tech"),
    ("Swiggy", "swiggy", "tech"), ("Dream11", "dreamsports", "tech"),
    ("ShareChat", "sharechat", "tech"), ("Urban Company", "urbancompany", "tech"),
    ("Freshworks", "freshworks", "tech"), ("Chargebee", "chargebee", "tech"),
    ("Zeta", "zeta", "fintech"), ("Slice", "slice", "fintech"),
    ("Navi", "navi", "fintech"), ("Jupiter", "jupiter", "fintech"),
    ("AngelOne", "angelone", "fintech"), ("Lenskart", "lenskart", "tech"),
    ("Nykaa", "nykaa", "tech"), ("Delhivery", "delhivery", "tech"),
    ("Rapido", "rapido", "tech"), ("Spinny", "spinny", "tech"),
    ("Cars24", "cars24", "tech"), ("PhysicsWallah", "physicswallah", "tech"),
    ("Unacademy", "unacademy", "tech"), ("Games24x7", "games24x7", "tech"),
    ("MPL", "mpl", "tech"), ("Gameskraft", "gameskraft", "tech"),
    ("Postman India", "getpostman", "tech"), ("Zluri", "zluri", "tech"),
    ("Zepto", "zepto", "tech"), ("Fampay", "fampay", "fintech"),
    ("KhataBook", "khatabook", "fintech"), ("Setu", "setu", "fintech"),

    # ---- Enterprise SaaS (tech) ----
    ("Airbase", "airbase", "fintech"), ("Rippling", "rippling", "tech"),
    ("Notion Labs", "notionlabs", "tech"), ("Coda", "coda", "tech"),
    ("Amplitude Analytics", "amplitudeanalytics", "tech"), ("Whatnot", "whatnot", "tech"),
    ("Faire", "faire", "tech"), ("Ironclad", "ironclad", "tech"),
    ("Verkada", "verkada", "tech"), ("Attentive", "attentive", "tech"),
    ("Ashby", "ashby", "tech"), ("Census", "census", "data"),
    ("Monte Carlo", "montecarlo", "data"), ("Sigma", "sigmacomputing", "data"),

    # ==== EXPANSION BATCH ====
    # ---- Observability / security / infra ----
    ("New Relic", "newrelic", "tech"), ("Dynatrace", "dynatrace", "tech"),
    ("Sentry", "sentry", "tech"), ("PagerDuty", "pagerduty", "tech"),
    ("Honeycomb", "honeycomb", "tech"), ("Chronosphere", "chronosphere", "tech"),
    ("CrowdStrike", "crowdstrike", "tech"), ("SentinelOne", "sentinelone", "tech"),
    ("Snyk", "snyk", "tech"), ("HackerOne", "hackerone", "tech"),
    ("Tenable", "tenable", "tech"), ("Rapid7", "rapid7", "tech"),
    ("Wiz", "wiz", "tech"), ("Sysdig", "sysdig", "tech"),
    ("Aqua Security", "aquasecurity", "tech"), ("Netskope", "netskope", "tech"),
    ("Abnormal Security", "abnormalsecurity", "tech"), ("Sonatype", "sonatype", "tech"),
    ("Fastly", "fastly", "tech"), ("DigitalOcean", "digitalocean", "tech"),
    ("HashiCorp", "hashicorpjobs", "tech"), ("Ping Identity", "pingidentity", "tech"),
    ("LaunchDarkly", "launchdarkly", "tech"), ("Split", "split", "tech"),
    ("Yugabyte", "yugabyte", "tech"), ("Materialize", "materializeinc", "data"),
    ("Dagster", "dagsterlabs", "data"), ("Astronomer", "astronomer", "data"),
    ("Prefect", "prefect", "data"), ("RudderStack", "rudderstack", "data"),
    ("Mixpanel", "mixpanel", "tech"), ("Algolia", "algolia", "tech"),
    ("Contentful", "contentful", "tech"), ("Sanity", "sanity", "tech"),
    ("Mux", "mux", "tech"), ("Cloudinary", "cloudinary", "tech"),
    ("Deepgram", "deepgram", "tech"), ("AssemblyAI", "assemblyai", "tech"),
    ("ElevenLabs", "elevenlabs", "tech"), ("Synthesia", "synthesia", "tech"),
    ("Railway", "railway", "tech"), ("Fly.io", "flyio", "tech"),
    ("Cursor", "anysphere", "tech"), ("Glean", "glean", "tech"),
    ("Sierra", "sierra", "tech"), ("Decagon", "decagon", "tech"),
    ("Ramp Fintech", "rampfinancial", "fintech"),

    # ---- Global consumer / SaaS ----
    ("Monday.com", "mondaycom", "tech"), ("ClickUp", "clickup", "tech"),
    ("Framer", "framer", "tech"), ("Vimeo", "vimeo", "tech"),
    ("DoorDash Eng", "doordashusa", "tech"), ("Coupang", "coupang", "tech"),
    ("Grab", "grab", "tech"), ("Sea / Shopee", "sea", "tech"),
    ("GoTo / Gojek", "gojek", "tech"), ("Traveloka", "traveloka", "tech"),
    ("Careem", "careem", "tech"), ("Delivery Hero", "deliveryhero", "tech"),
    ("Zalando", "zalando", "tech"), ("Klarna", "klarna", "fintech"),
    ("N26", "n26", "fintech"), ("Adyen", "adyen", "fintech"),
    ("Checkout.com", "checkout", "fintech"), ("Airwallex", "airwallex", "fintech"),
    ("GoCardless", "gocardless", "fintech"), ("SumUp", "sumup", "fintech"),

    # ---- Fintech (more) ----
    ("Chime Financial", "chimefinancial", "fintech"), ("Betterment", "betterment", "fintech"),
    ("SoFi", "sofi", "fintech"), ("Toast Fintech", "toasttab", "fintech"),
    ("Bill.com", "billcom", "fintech"), ("Addepar", "addepar", "fintech"),
    ("Modern Treasury", "moderntreasury", "fintech"), ("Alloy", "alloy", "fintech"),
    ("Unit", "unit", "fintech"), ("Column", "column", "fintech"),

    # ---- Indian startups / unicorns (more) ----
    ("Zoho", "zoho", "tech"), ("Whatfix", "whatfix", "tech"),
    ("MindTickle", "mindtickle", "tech"), ("Innovaccer", "innovaccer", "tech"),
    ("HighRadius", "highradius", "fintech"), ("Icertis", "icertis", "tech"),
    ("Gupshup", "gupshup", "tech"), ("Yellow.ai", "yellowai", "tech"),
    ("Uniphore", "uniphore", "tech"), ("Observe.ai", "observeai", "tech"),
    ("Locus", "locus", "tech"), ("Zetwerk", "zetwerk", "tech"),
    ("OfBusiness", "ofbusiness", "tech"), ("Udaan", "udaan", "tech"),
    ("Moglix", "moglix", "tech"), ("Infra.Market", "inframarket", "tech"),
    ("Rebel Foods", "rebelfoods", "tech"), ("Blinkit", "blinkit", "tech"),
    ("Licious", "licious", "tech"), ("BigBasket", "bigbasket", "tech"),
    ("Nazara", "nazara", "tech"), ("WinZO", "winzo", "tech"),
    ("Epifi (Fi)", "epifi", "fintech"), ("KreditBee", "kreditbee", "fintech"),
    ("MoneyView", "moneyview", "fintech"), ("INDmoney", "indmoney", "fintech"),
    ("Smallcase", "smallcase", "fintech"), ("Juspay", "juspay", "fintech"),
    ("Cashfree", "cashfree", "fintech"), ("Pine Labs", "pinelabs", "fintech"),
    ("Perfios", "perfios", "fintech"), ("M2P", "m2pfintech", "fintech"),
    ("Signzy", "signzy", "fintech"), ("Pixxel", "pixxel", "tech"),
    ("Skyroot", "skyroot", "tech"), ("Groww Tech", "growwtech", "fintech"),
    ("Sprinto", "sprinto", "tech"), ("Atlan", "atlan", "data"),
    ("Hasura India", "hasurahq", "tech"), ("Refyne", "refyne", "fintech"),
]


def probe_candidate(cand):
    """Try each provider for one candidate; return a result dict or None."""
    name, token, ctype = cand
    for source in SOURCES_TO_TRY:
        is_real, jobs = probe(source, token)
        if is_real and jobs:  # real AND has at least one posting
            india_eng = sum(1 for j in jobs if matches(j))
            return {
                "name": name, "source": source, "token": token, "type": ctype,
                "total": len(jobs), "india_eng": india_eng,
            }
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--append", action="store_true",
                        help="Merge with existing companies.json instead of overwriting.")
    args = parser.parse_args()

    print(f"Probing {len(CANDIDATES)} candidates across {', '.join(SOURCES_TO_TRY)} ...\n")
    found = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(probe_candidate, c): c for c in CANDIDATES}
        for fut in as_completed(futures):
            res = fut.result()
            cand = futures[fut]
            if res:
                flag = f"{res['india_eng']:>3} India-eng" if res["india_eng"] else "  · none in India now"
                print(f"  [OK]   {res['name']:<20} {res['source']:<10} {res['total']:>4} jobs | {flag}")
                found.append(res)
            else:
                print(f"  [skip] {cand[0]:<20} (no board found)")

    found.sort(key=lambda r: (-r["india_eng"], -r["total"]))

    # Build the companies.json entries (the monitor only needs these 4 fields).
    new_entries = [{"name": r["name"], "source": r["source"], "token": r["token"], "type": r["type"]}
                   for r in found]

    if args.append and os.path.exists(COMPANIES_FILE):
        with open(COMPANIES_FILE, "r", encoding="utf-8-sig") as f:
            existing = json.load(f)
        seen = {(c["source"], c["token"]) for c in existing}
        merged = existing + [e for e in new_entries if (e["source"], e["token"]) not in seen]
    else:
        merged = new_entries

    with open(COMPANIES_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)

    with_india = sum(1 for r in found if r["india_eng"])
    print("\n" + "=" * 64)
    print(f"  Found {len(found)} real boards ({with_india} have India eng roles right now).")
    print(f"  Wrote {len(merged)} companies to companies.json.")
    print("=" * 64)


if __name__ == "__main__":
    main()
