"""Free-tier model providers behind small interfaces (PRD §8.4). Primary → fallback, set in config.

Modes (PROVIDER_MODE):
  auto     a provider is live if its key is set, otherwise it is unavailable (the default)
  fixture  never touch the network: STT reads recorded transcripts, the LLM reads the extraction cache
  live     like auto, for integration checks
Development and tests use fixture mode. With no keys at all, everything still works: STT failures become
"audio only" cases and the keyword path creates every case.
"""
