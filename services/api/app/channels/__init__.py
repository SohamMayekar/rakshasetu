"""Channel adapters (PRD F-L1, §15): each maps its payload to Canonical Report v1, then calls intake.accept().

The registry is the adaptation seam: an SMS or WhatsApp adapter is one more module here, not a new path.
"""

from app.channels import desk, partner  # noqa: F401  (register on import)
from app.channels.registry import ADAPTERS, adapter

__all__ = ["ADAPTERS", "adapter"]
