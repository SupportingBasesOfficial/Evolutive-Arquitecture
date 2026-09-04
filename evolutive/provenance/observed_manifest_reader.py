"""Producer determinístico que observa provenance em um manifest brokerado e hash-bound."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from jsonschema import Draft202012Validator

PRODUCER_ID = "evolutive.provenance.observed_manifest_reader"
PRODUCER_VERSION = "0.1.0"

_ALLOWED_ARTIFACT_KINDS = {
    "source",
    "generated_source",
    "ast",
    "ir",
    "object",
    "library",
    "binary",
    "metadata",
    "build_manifest",
    "package",
}


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _reject_duplicate_members(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON contém membro duplicado: {key}")
        result[key] = value
    return result


def _artifact_index(authorized_artifacts: list[dict]) -> dict[str, tuple[str, str]]:
    if not isinstance(authorized_artifacts, list):
        raise ValueError("authorized_artifacts precisa ser lista")
    index: dict[str, tuple[str, str]] = {}
    for artifact in authorized_artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {"identity", "kind", "sha256"}:
            raise ValueError("artifact autorizado precisa conter somente identity, kind e sha256")
        identity, kind, sha256 = artifact["identity"], artifact["kind"], artifact["sha256"]
        if not isinstance(identity, str) or not identity:
            raise ValueError("artifact autorizado com identity inválida")
        if kind not in _ALLOWED_ARTIFACT_KINDS:
            raise ValueError(f"artifact autorizado com kind inválido: {kind}")
        if not isinstance(sha256, str) or len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
            raise ValueError("artifact autorizado com sha256 inválido")
        if identity in index:
            raise ValueError(f"artifact autorizado com identity duplicada: {identity}")
        index[identity] = (kind, sha256)
    return index


def observe(brokered_manifest: dict, authorized_artifacts: list[dict], manifest_schema: dict) -> dict:
    """Observa apenas fatos materializados em um manifest brokerado.

    O producer não recebe root, não abre arquivos e não executa build/código do consumidor.
    `brokered_manifest` contém identity/kind/sha256/content já entregues por uma autoridade externa.
    """

    if not isinstance(brokered_manifest, dict) or set(brokered_manifest) != {"identity", "kind", "sha256", "content"}:
        raise ValueError("brokered_manifest precisa conter somente identity, kind, sha256 e content")
    identity = brokered_manifest["identity"]
    kind = brokered_manifest["kind"]
    sha256 = brokered_manifest["sha256"]
    content = brokered_manifest["content"]
    if kind != "build_manifest":
        raise ValueError("brokered_manifest precisa ter kind=build_manifest")
    if not isinstance(identity, str) or not identity or not isinstance(content, str):
        raise ValueError("brokered_manifest inválido")
    actual_sha = _sha256_text(content)
    if sha256 != actual_sha:
        raise ValueError("sha256 do brokered_manifest diverge do conteúdo")

    artifact_index = _artifact_index(authorized_artifacts)
    if artifact_index.get(identity) != (kind, sha256):
        raise ValueError("brokered_manifest não corresponde a artifact binding autorizado")

    try:
        payload = json.loads(content, object_pairs_hook=_reject_duplicate_members)
    except json.JSONDecodeError as exc:
        raise ValueError("brokered_manifest não contém JSON válido") from exc

    Draft202012Validator.check_schema(manifest_schema)
    failures = sorted(error.message for error in Draft202012Validator(manifest_schema).iter_errors(payload))
    if failures:
        raise ValueError("observed provenance manifest inválido: " + "; ".join(failures))

    seen_ids: set[str] = set()
    transformations: list[dict] = []
    for transformation in payload["transformations"]:
        transformation_id = transformation["id"]
        if transformation_id in seen_ids:
            raise ValueError(f"transformation id duplicado: {transformation_id}")
        seen_ids.add(transformation_id)
        for side in ("inputs", "outputs"):
            for artifact in transformation[side]:
                binding = artifact_index.get(artifact["identity"])
                expected = (artifact["kind"], artifact["sha256"])
                if binding is None:
                    raise ValueError(f"{transformation_id}: artifact não autorizado: {artifact['identity']}")
                if binding != expected:
                    raise ValueError(f"{transformation_id}: binding diverge: {artifact['identity']}")
        observed = deepcopy(transformation)
        observed["observation_basis"] = "observed"
        transformations.append(observed)

    return {
        "evidence_version": 1,
        "constitution_version": payload["constitution_version"],
        "authority": {
            "producer_trust": "unverified",
            "may_assert_semantic_relation": False,
            "may_assert_rule_outcome": False,
        },
        "producer": {
            "id": PRODUCER_ID,
            "version": PRODUCER_VERSION,
            "kind": "provenance_adapter",
        },
        "transformations": transformations,
    }
