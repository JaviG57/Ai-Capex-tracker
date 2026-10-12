"""Inspect how each company reports capex in SEC XBRL before building the
extractor: which tag is used, and whether values are 3-month or cumulative
year-to-date (cash-flow items are frequently YTD, which must be differenced)."""
import json, os, pathlib, time
from collections import defaultdict
from datetime import date
import requests
import companies as cm, fetch_sec_edgar

HDRS = {"User-Agent": f"AI Capex Tracker ({os.environ.get('SEC_CONTACT_EMAIL','x@example.com')})"}
TAGS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
    "PaymentsToAcquirePropertyPlantAndEquipmentExcludingFinanceLease",
    "PaymentsForCapitalImprovements",
    "PaymentsToAcquireOtherPropertyPlantAndEquipment",
    "PurchaseOfPropertyPlantAndEquipment",
]

def bucket(days):
    if 80 <= days <= 100: return "3mo"
    if 170 <= days <= 190: return "6mo"
    if 260 <= days <= 285: return "9mo"
    if 350 <= days <= 380: return "12mo"
    return f"{days}d"

out = {}
cik = fetch_sec_edgar.get_cik_map()
for c in cm.COMPANIES:
    t = c["ticker"]
    k = cik.get(t)
    if not k:
        print(f"{t:6} no CIK"); continue
    try:
        r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{k}.json", headers=HDRS, timeout=60)
        r.raise_for_status()
        facts = r.json().get("facts", {})
        rec = {"taxonomies": list(facts.keys()), "tags": {}}
        for tax in facts:
            for tag in TAGS:
                node = facts[tax].get(tag)
                if not node: continue
                usd = node.get("units", {}).get("USD", [])
                durs, recent = defaultdict(int), []
                for e in usd:
                    if not e.get("start"): continue
                    b = bucket((date.fromisoformat(e["end"]) - date.fromisoformat(e["start"])).days)
                    durs[b] += 1
                    recent.append((e["end"], b, e.get("fp"), e.get("form"), e["val"]))
                recent.sort()
                rec["tags"][f"{tax}:{tag}"] = {"durations": dict(durs), "last4": recent[-4:]}
        out[t] = rec
        print(f"{t:6} tax={rec['taxonomies']}")
        if not rec["tags"]:
            print("        NO CAPEX TAG FOUND")
        for tg, info in rec["tags"].items():
            print(f"        {tg}: {info['durations']}")
            for e in info["last4"]:
                print(f"           {e[0]} {e[1]:5} {e[2]} {e[3]} ${e[4]/1e9:.2f}B")
    except Exception as e:
        print(f"{t:6} FAILED {e}")
    time.sleep(0.2)
pathlib.Path(__file__).resolve().parent.parent.joinpath("data/capex_probe.json").write_text(
    json.dumps(out, indent=2, default=str))
print("\nwrote data/capex_probe.json")
