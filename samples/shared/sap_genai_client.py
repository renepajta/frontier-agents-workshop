"""Utility helpers to wire Microsoft Agent Framework agents to SAP AI Core."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv

from agent_framework.azure import AzureOpenAIChatClient

from ai_core_sdk.ai_core_v2_client import AICoreV2Client
from gen_ai_hub.proxy import GenAIHubProxyClient

load_dotenv()


@dataclass(frozen=True)
class SapAiCoreSettings:
    """Configuration needed to talk to SAP AI Core via GenAI Hub."""

    resource_group: str = field(default_factory=lambda: os.getenv("AICORE_RESOURCE_GROUP", "default"))
    scenario_id: str = field(default_factory=lambda: os.getenv("AICORE_SCENARIO_ID", "foundation-models"))
    deployment_name: Optional[str] = field(default_factory=lambda: os.getenv("AICORE_DEPLOYMENT_NAME"))
    api_version: str = field(default_factory=lambda: os.getenv("AICORE_API_VERSION", "2023-05-15"))

    def default_headers(self) -> Dict[str, str]:
        return {"AI-Resource-Group": self.resource_group}


IDENTIFIER_FIELDS = (
    "id",
    "name",
    "configurationName",
    "configuration_name",
    "configurationId",
    "configuration_id",
)


def _read_attr(candidate: Any, attr: str) -> Optional[str]:
    value = getattr(candidate, attr, None)
    if value is None and isinstance(candidate, dict):
        value = candidate.get(attr)
    if value is None:
        return None
    return str(value)


def _candidate_identifiers(candidate: Any) -> List[str]:
    identifiers: List[str] = []
    for field_name in IDENTIFIER_FIELDS:
        value = _read_attr(candidate, field_name)
        if value and value not in identifiers:
            identifiers.append(value)
    return identifiers


def _deployment_endpoint(candidate: Any, identifiers: List[str]) -> Tuple[str, Optional[str]]:
    url = _read_attr(candidate, "deployment_url")
    if not url:
        raise RuntimeError("Selected deployment is missing 'deployment_url'.")
    canonical_id = _infer_deployment_name(url) or (identifiers[0] if identifiers else None)
    return url, canonical_id


def _get_deployment_url(settings: SapAiCoreSettings) -> Tuple[str, Optional[str]]:
    client = AICoreV2Client.from_env()
    response = client.deployment.query(
        resource_group=settings.resource_group,
        scenario_id=settings.scenario_id,
    )
    resources: Iterable[Any] = getattr(response, "resources", []) or []

    deployments: List[Tuple[Any, List[str]]] = []
    for candidate in resources:
        identifiers = _candidate_identifiers(candidate)
        if identifiers:
            deployments.append((candidate, identifiers))

    if not deployments:
        raise RuntimeError(
            "No SAP AI Core deployments were returned. Verify the resource group and scenario id."
        )

    target = settings.deployment_name.strip().lower() if settings.deployment_name else None
    if target:
        for candidate, identifiers in deployments:
            if any(identifier.lower() == target for identifier in identifiers):
                return _deployment_endpoint(candidate, identifiers)

        available = ", ".join(sorted({identifier for _, ids in deployments for identifier in ids})) or "<none>"
        raise RuntimeError(
            "Deployment '%s' not found in resource group '%s' and scenario '%s'. Available: %s"
            % (settings.deployment_name, settings.resource_group, settings.scenario_id, available)
        )

    candidate, identifiers = deployments[0]
    return _deployment_endpoint(candidate, identifiers)


def _infer_deployment_name(url: str) -> Optional[str]:
    parts = [part for part in url.rstrip("/").split("/") if part]
    if "deployments" in parts:
        idx = parts.index("deployments")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def _get_bearer_token(settings: SapAiCoreSettings) -> str:
    proxy = GenAIHubProxyClient(resource_group=settings.resource_group)
    token = proxy.get_ai_core_token()
    if not token:
        raise RuntimeError("GenAI Hub did not return an AI Core token.")

    prefix = "Bearer "
    if token.startswith(prefix):
        token = token[len(prefix) :]
    token = token.strip()
    if not token:
        raise RuntimeError("AI Core token is empty after removing the 'Bearer' prefix.")
    return token


def build_sap_chat_client(settings: Optional[SapAiCoreSettings] = None) -> AzureOpenAIChatClient:
    """Return an AzureOpenAIChatClient configured to route calls through SAP AI Core."""

    settings = settings or SapAiCoreSettings()
    deployment_url, deployment_name = _get_deployment_url(settings)
    if not deployment_name:
        raise RuntimeError(
            "Set AICORE_DEPLOYMENT_NAME or ensure the deployment URL contains '/deployments/<name>'."
        )

    token = _get_bearer_token(settings)

    return AzureOpenAIChatClient(
        deployment_name=deployment_name,
        base_url=deployment_url,
        api_key=token,
        api_version=settings.api_version,
        default_headers=settings.default_headers(),
    )


__all__ = ["SapAiCoreSettings", "build_sap_chat_client"]