"""
AI integration extension points.

See docs/AI_INTEGRATION.md for how to plug in test generation or semantic checks.
"""

from framework.ai.context import build_project_context_bundle

__all__ = ["build_project_context_bundle"]
