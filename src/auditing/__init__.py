"""
PaperForge — Auditing Module
Semantic audits, JATS compliance, and visual regression.
"""

from .semantic import full_audit, audit_report
from .jats_compliance import validate_jats

try:
    from .visual_diff import visual_diff, visual_audit_report
except ImportError:
    pass
