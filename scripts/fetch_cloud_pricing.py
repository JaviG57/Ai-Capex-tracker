"""
STUB -- not implemented in v1.

Plan: track on-demand/spot H100 or B200 pricing across providers as a
compute-scarcity proxy:
  - CoreWeave, Lambda, RunPod publish public pricing pages (no API; would
    need light HTML scraping, so brittle to page redesigns).
  - AWS/Azure/GCP have official pricing APIs (AWS Price List API, Azure
    Retail Prices API, GCP Cloud Billing Catalog API) which are more
    stable than scraping but need each provider's specific instance-type
    naming for GPU SKUs (e.g. AWS p5.48xlarge for H100).

Left as a stub for a follow-up pass -- worth building once the rest of the
pipeline is running, since it's the most maintenance-prone source here.

Returning an empty dict keeps the rest of the pipeline running.
"""


def fetch_all() -> dict:
    return {}
