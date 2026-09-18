"""
The tracked company universe. Edit this list to add/remove companies --
every fetcher script imports from here, so this is the single source of
truth for who gets tracked.

domain: used by TheirStack (job postings) and PredictLeads-style lookups.
Must be the company's primary corporate domain (no "www.", no subdomain).
group: used to organize the dashboard's Hiring/Market tabs into sections.
"""

COMPANIES = [
    # Hyperscalers
    {"ticker": "MSFT", "name": "Microsoft", "domain": "microsoft.com", "group": "Hyperscalers"},
    {"ticker": "GOOGL", "name": "Alphabet", "domain": "google.com", "group": "Hyperscalers"},
    {"ticker": "AMZN", "name": "Amazon", "domain": "amazon.com", "group": "Hyperscalers"},
    {"ticker": "META", "name": "Meta Platforms", "domain": "meta.com", "group": "Hyperscalers"},
    # Chipmakers
    {"ticker": "NVDA", "name": "NVIDIA", "domain": "nvidia.com", "group": "Chipmakers"},
    {"ticker": "AVGO", "name": "Broadcom", "domain": "broadcom.com", "group": "Chipmakers"},
    {"ticker": "AMD", "name": "AMD", "domain": "amd.com", "group": "Chipmakers"},
    {"ticker": "TSM", "name": "TSMC", "domain": "tsmc.com", "group": "Chipmakers"},
    {"ticker": "ASML", "name": "ASML", "domain": "asml.com", "group": "Chipmakers"},
    {"ticker": "ARM", "name": "Arm Holdings", "domain": "arm.com", "group": "Chipmakers"},
    # Infra / OEM
    {"ticker": "ORCL", "name": "Oracle", "domain": "oracle.com", "group": "Infra / OEM"},
    {"ticker": "DELL", "name": "Dell Technologies", "domain": "dell.com", "group": "Infra / OEM"},
    {"ticker": "SMCI", "name": "Super Micro Computer", "domain": "supermicro.com", "group": "Infra / OEM"},
    {"ticker": "CRWV", "name": "CoreWeave", "domain": "coreweave.com", "group": "Infra / OEM"},
    # Power / data center
    {"ticker": "DLR", "name": "Digital Realty", "domain": "digitalrealty.com", "group": "Power / Data Center"},
    {"ticker": "EQIX", "name": "Equinix", "domain": "equinix.com", "group": "Power / Data Center"},
    {"ticker": "VRT", "name": "Vertiv", "domain": "vertiv.com", "group": "Power / Data Center"},
    {"ticker": "ETN", "name": "Eaton", "domain": "eaton.com", "group": "Power / Data Center"},
]

# Curated open-source repos used as an "AI ecosystem dev activity" proxy.
# Not tied to a single ticker -- this is a macro/ecosystem signal.
GITHUB_AI_REPOS = [
    "pytorch/pytorch",
    "huggingface/transformers",
    "vllm-project/vllm",
    "ggerganov/llama.cpp",
    "NVIDIA/TensorRT-LLM",
    "microsoft/DeepSpeed",
]
