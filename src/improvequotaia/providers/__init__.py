"""Registre des modules « outil ». Ajouter un outil = l'importer et l'ajouter à ALL_PROVIDERS."""
from .antigravity import AntigravityProvider
from .base import Bucket, Provider, ProviderError, ProviderResult, ToolMissing
from .claude import ClaudeProvider
from .codex import CodexProvider
from .copilot import CopilotProvider
from .gemini_cli import GeminiCliProvider
from .grok import GrokProvider
from .zai import ZaiProvider

# Ordre d'affichage des sections
ALL_PROVIDERS = (ClaudeProvider, AntigravityProvider, CodexProvider, GrokProvider, CopilotProvider,
                 GeminiCliProvider, ZaiProvider)

__all__ = ["ALL_PROVIDERS", "Bucket", "Provider", "ProviderError", "ProviderResult", "ToolMissing"]
