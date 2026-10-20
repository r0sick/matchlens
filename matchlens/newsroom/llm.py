"""Model provider selection for the newsroom.

Configured through environment variables (a local `.env` file is loaded automatically):

  Microsoft Foundry, signed in with your Azure account (recommended)
      FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
      FOUNDRY_MODEL=<model deployment name>
      # authentication: `az login` (Azure CLI) or any credential DefaultAzureCredential can find

  API key instead of Azure sign-in (no Azure CLI needed; takes precedence when set)
      FOUNDRY_PROJECT_ENDPOINT / FOUNDRY_MODEL as above, plus
      AZURE_OPENAI_API_KEY=<key from the project Overview page>
      # optional: AZURE_OPENAI_ENDPOINT to use a different resource, MATCHLENS_API=chat_completions

  MATCHLENS_AI=off   forces the deterministic template narrator (no model calls)

With nothing configured MatchLens still runs: narratives come from templates.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

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


def _resource_root(endpoint: str) -> str:
    """https://x.services.ai.azure.com/api/projects/p -> https://x.services.ai.azure.com"""
    parts = urlsplit(endpoint.strip())
    return f"{parts.scheme}://{parts.netloc}" if parts.netloc else endpoint.strip()


def make_provider() -> Provider:
    _load_env()
    if os.getenv("MATCHLENS_AI", "").lower() in ("off", "0", "false", "templates"):
        return Provider(None, "templates")
    endpoint, model = os.getenv("FOUNDRY_PROJECT_ENDPOINT"), os.getenv("FOUNDRY_MODEL")
    key = os.getenv("AZURE_OPENAI_API_KEY")
    key_model = os.getenv("AZURE_OPENAI_MODEL") or os.getenv("AZURE_OPENAI_CHAT_COMPLETION_MODEL") or model
    key_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or (_resource_root(endpoint) if endpoint else None)

    # 1) API key (no Azure CLI needed). Uses the Responses API of your Foundry resource,
    #    or Chat Completions if MATCHLENS_API=chat_completions.
    if key and key_endpoint and key_model:
        try:
            if os.getenv("MATCHLENS_API", "").lower() == "chat_completions":
                from agent_framework.openai import OpenAIChatCompletionClient as Client
            else:
                from agent_framework.openai import OpenAIChatClient as Client
            client = Client(model=key_model, azure_endpoint=_resource_root(key_endpoint), api_key=key)
            return Provider(client, "Microsoft Foundry" if "services.ai.azure.com" in key_endpoint else "Azure OpenAI",
                            key_model)
        except Exception as e:
            log.warning("API-key client unavailable (%s); trying Azure sign-in", e)

    # 2) Microsoft Foundry with your Azure sign-in (az login, VS Code, or a managed identity in Azure)
    if endpoint and model:
        try:
            from azure.identity import DefaultAzureCredential
            from agent_framework.foundry import FoundryChatClient
            client = FoundryChatClient(project_endpoint=endpoint, model=model,
                                       credential=DefaultAzureCredential(exclude_interactive_browser_credential=True))
            return Provider(client, "Microsoft Foundry", model)
        except Exception as e:
            log.warning("Foundry client unavailable (%s); using templates", e)
    return Provider(None, "templates")
