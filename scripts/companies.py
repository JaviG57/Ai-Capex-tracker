"""
The tracked company universe. Edit this list to add/remove companies --
every fetcher script imports from here, so this is the single source of
truth for who gets tracked.

domain: used by TheirStack (job postings) and PredictLeads-style lookups.
Must be the company's primary corporate domain (no "www.", no subdomain).
"""

COMPANIES = [
    # Hyperscalers
    {"ticker": "MSFT", "name": "Microsoft", "domain": "microsoft.com"},
    {"ticker": "GOOGL", "name": "Alphabet", "domain": "google.com"},
    {"ticker": "AMZN", "name": "Amazon", "domain": "amazon.com"},
    {"ticker": "META", "name": "Meta Platforms", "domain": "meta.com"},
    # Chipmakers
    {"ticker": "NVDA", "name": "NVIDIA", "domain": "nvidia.com"},
    {"ticker": "AVGO", "name": "Broadcom", "domain": "broadcom.com"},
    {"ticker": "AMD", "name": "AMD", "domain": "amd.com"},
    {"ticker": "TSM", "name": "TSMC", "domain": "tsmc.com"},
    {"ticker": "ASML", "name": "ASML", "domain": "asml.com"},
    {"ticker": "ARM", "name": "Arm Holdings", "domain": "arm.com"},
    # Infra / OEM
    {"ticker": "ORCL", "name": "Oracle", "domain": "oracle.com"},
    {"ticker": "DELL", "name": "Dell Technologies", "domain": "dell.com"},
    {"ticker": "SMCI", "name": "Super Micro Computer", "domain": "supermicro.com"},
    {"ticker": "CRWV", "name": "CoreWeave", "domain": "coreweave.com"},
    # Power / data center
    {"ticker": "DLR", "name": "Digital Realty", "domain": "digitalrealty.com"},
    {"ticker": "EQIX", "name": "Equinix", "domain": "equinix.com"},
    {"ticker": "VRT", "name": "Vertiv", "domain": "vertiv.com"},
    {"ticker": "ETN", "name": "Eaton", "domain": "eaton.com"},
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
