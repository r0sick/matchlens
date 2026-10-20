"""Model provider selection for the newsroom.

Configured through environment variables (a local `.env` file is loaded automatically):

  Microsoft Foundry, signed in with your Azure account (recommended)
      FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
      FOUNDRY_MODEL=<model deployment name>
      # authentication: `az login` (Azure CLI) or any credential DefaultAzureCredential can find

  Azure OpenAI-compatible endpoint with an API key (fallback)
      AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
      AZURE_OPENAI_API_KEY=<key>
      AZURE_OPENAI_MODEL=<model deployment name>

  MATCHLENS_AI=off   forces the deterministic template narrator (no model calls)

With nothing configured MatchLens still runs: narratives come from templates.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("matchlens.newsroom")


@dataclass
class Provider:
    client: object | None
    name: str                      # shown to viewers as provenance
    model: str | None = None

    @property
    def enabled(self) -> bool:
        return self.client is not None


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    except Exception:          # python-dotenv is optional
        pass


def make_provider() -> Provider:
    _load_env()
    if os.getenv("MATCHLENS_AI", "").lower() in ("off", "0", "false", "templates"):
        return Provider(None, "templates")
    endpoint, model = os.getenv("FOUNDRY_PROJECT_ENDPOINT"), os.getenv("FOUNDRY_MODEL")
    if endpoint and model:
        try:
            from azure.identity import DefaultAzureCredential
            from agent_framework.foundry import FoundryChatClient
            client = FoundryChatClient(project_endpoint=endpoint, model=model,
                                       credential=DefaultAzureCredential(exclude_interactive_browser_credential=True))
            return Provider(client, "Microsoft Foundry", model)
        except Exception as e:  # missing package or bad configuration: fall through to the next option
            log.warning("Foundry client unavailable (%s); trying API-key configuration", e)
    az_endpoint, az_key = os.getenv("AZURE_OPENAI_ENDPOINT"), os.getenv("AZURE_OPENAI_API_KEY")
    az_model = os.getenv("AZURE_OPENAI_MODEL") or os.getenv("AZURE_OPENAI_CHAT_COMPLETION_MODEL") or model
    if az_endpoint and az_key and az_model:
        try:
            from agent_framework.openai import OpenAIChatCompletionClient
            client = OpenAIChatCompletionClient(model=az_model, azure_endpoint=az_endpoint, api_key=az_key)
            return Provider(client, "Azure OpenAI", az_model)
        except Exception as e:
            log.warning("Azure OpenAI client unavailable (%s); using templates", e)
    return Provider(None, "templates")
