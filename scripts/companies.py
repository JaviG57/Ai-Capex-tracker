"""
The tracked company universe. Edit this list to add/remove companies --
every fetcher script imports from here, so this is the single source of
truth for who gets tracked.

domain: used by TheirStack (job postings) and PredictLeads-style lookups.
Must be the company's primary corporate domain (no "www.", no subdomain).
group: used to organize the dashboard's Hiring/Market tabs into sections.
warn_aliases: legal/brand names to match in state WARN layoff notices, which
  are filed under legal entity names (e.g. 'Amazon.com Services LLC').
warn_exclude: names that would false-match an alias (e.g. 'Eaton Vance' is an
  unrelated asset manager, not Eaton Corp).
"""

COMPANIES = [
    # Hyperscalers
    {"ticker": "MSFT", "name": "Microsoft", "domain": "microsoft.com", "group": "Hyperscalers", "warn_aliases": ['Microsoft'], "warn_exclude": []},
    {"ticker": "GOOGL", "name": "Alphabet", "domain": "google.com", "group": "Hyperscalers", "warn_aliases": ['Google', 'Alphabet'], "warn_exclude": []},
    {"ticker": "AMZN", "name": "Amazon", "domain": "amazon.com", "group": "Hyperscalers", "warn_aliases": ['Amazon'], "warn_exclude": []},
    {"ticker": "META", "name": "Meta Platforms", "domain": "meta.com", "group": "Hyperscalers", "warn_aliases": ['Meta Platforms', 'Facebook'], "warn_exclude": []},
    # Chipmakers
    {"ticker": "NVDA", "name": "NVIDIA", "domain": "nvidia.com", "group": "Chipmakers", "warn_aliases": ['NVIDIA'], "warn_exclude": []},
    {"ticker": "AVGO", "name": "Broadcom", "domain": "broadcom.com", "group": "Chipmakers", "warn_aliases": ['Broadcom', 'VMware'], "warn_exclude": []},
    {"ticker": "AMD", "name": "AMD", "domain": "amd.com", "group": "Chipmakers", "warn_aliases": ['Advanced Micro Devices', 'Xilinx'], "warn_exclude": []},
    {"ticker": "TSM", "name": "TSMC", "domain": "tsmc.com", "group": "Chipmakers", "warn_aliases": ['TSMC', 'Taiwan Semiconductor'], "warn_exclude": []},
    {"ticker": "ASML", "name": "ASML", "domain": "asml.com", "group": "Chipmakers", "warn_aliases": ['ASML', 'Cymer'], "warn_exclude": []},
    {"ticker": "ARM", "name": "Arm Holdings", "domain": "arm.com", "group": "Chipmakers", "warn_aliases": ['Arm Inc', 'Arm Limited', 'Arm Ltd', 'ARM, Inc'], "warn_exclude": []},
    # Infra / OEM
    {"ticker": "ORCL", "name": "Oracle", "domain": "oracle.com", "group": "Infra / OEM", "warn_aliases": ['Oracle'], "warn_exclude": []},
    {"ticker": "DELL", "name": "Dell Technologies", "domain": "dell.com", "group": "Infra / OEM", "warn_aliases": ['Dell Technologies', 'Dell Inc', 'Dell Marketing', 'Dell USA'], "warn_exclude": []},
    {"ticker": "SMCI", "name": "Super Micro Computer", "domain": "supermicro.com", "group": "Infra / OEM", "warn_aliases": ['Super Micro', 'Supermicro'], "warn_exclude": []},
    {"ticker": "CRWV", "name": "CoreWeave", "domain": "coreweave.com", "group": "Infra / OEM", "warn_aliases": ['CoreWeave'], "warn_exclude": []},
    # Power / data center
    {"ticker": "DLR", "name": "Digital Realty", "domain": "digitalrealty.com", "group": "Power / Data Center", "warn_aliases": ['Digital Realty'], "warn_exclude": []},
    {"ticker": "EQIX", "name": "Equinix", "domain": "equinix.com", "group": "Power / Data Center", "warn_aliases": ['Equinix'], "warn_exclude": []},
    {"ticker": "VRT", "name": "Vertiv", "domain": "vertiv.com", "group": "Power / Data Center", "warn_aliases": ['Vertiv'], "warn_exclude": []},
    {"ticker": "ETN", "name": "Eaton", "domain": "eaton.com", "group": "Power / Data Center", "warn_aliases": ['Eaton'], "warn_exclude": ['Eaton Vance', 'Eaton Rapids']},
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
