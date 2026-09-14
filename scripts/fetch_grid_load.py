"""
STUB -- not implemented in v1.

Plan: pull daily peak load (MW) for data-center-dense grid regions as a
power-draw proxy for data center buildout:
  - PJM (Dominion / "Data Center Alley", Virginia): https://www.pjm.com/markets-and-operations
    PJM publishes hourly/daily load data; look at their Data Miner 2 API
    (requires free registration): https://dataminer2.pjm.com/
  - ERCOT (Texas): http://www.ercot.com/gridinfo/load - has a public daily
    load CSV feed, no registration required for basic historical/actual load.

This is left as a stub because both feeds are region-wide (not company-
specific) and each has its own quirks (PJM needs an API key + subscription
key; ERCOT's file layout changes occasionally) that are worth verifying
against their current docs before wiring in, rather than guessing.

Returning an empty dict keeps the rest of the pipeline running.
"""


def fetch_all() -> dict:
    return {}
