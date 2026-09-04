"""Producer determinístico que verifica declarações de provenance contra artefatos autorizados."""

from __future__ import annotations

from copy import deepcopy

PRODUCER_ID = "evolutive.provenance.declared_manifest_verifier"
PRODUCER_VERSION = "0.1.0"

_ARTIFACT_KINDS = {
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
_REQUIRED_TRANSFORMATION_KEYS = {
    "id",
    "provenance_class",
    "inputs",
    "outputs",
    "candidate_relations",
    "observation_basis",
}
_ALLOWED_TRANSFORMATION_KEYS = _REQUIRED_TRANSFORMATION_KEYS | {"notes"}


def _validate_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{label}: sha256 inválido")
    return value


def _validate_artifact(artifact: object, label: str) -> tuple[str, str, str]:
    if not isinstance(artifact, dict):
        raise ValueError(f"{label}: artifact precisa ser objeto")
    if set(artifact) != {"identity", "kind", "sha256"}:
        raise ValueError(f"{label}: artifact precisa conter somente identity, kind e sha256")
    identity = artifact["identity"]
    kind = artifact["kind"]
    sha256 = artifact["sha256"]
    if not isinstance(identity, str) or not identity:
        raise ValueError(f"{label}: identity inválida")
    if kind not in _ARTIFACT_KINDS:
        raise ValueError(f"{label}: kind inválido")
    return identity, kind, _validate_sha256(sha256, label)


def verify(declaration: dict, authorized_artifacts: list[dict]) -> dict:
    """Valida bindings declarados sem executar código do consumidor.

    `authorized_artifacts` deve conter somente identidades já autorizadas por uma
    autoridade externa, com `identity`, `kind` e `sha256` exatos.
    """

    if not isinstance(declaration, dict):
        raise ValueError("declaration precisa ser objeto")
    if set(declaration) != {"constitution_version", "transformations"}:
        raise ValueError("declaration precisa conter somente constitution_version e transformations")
    if not isinstance(authorized_artifacts, list):
        raise ValueError("authorized_artifacts precisa ser lista")

    artifact_index: dict[str, tuple[str, str]] = {}
    for index, artifact in enumerate(authorized_artifacts):
        identity, kind, sha256 = _validate_artifact(artifact, f"authorized_artifacts[{index}]")
        binding = (kind, sha256)
        previous = artifact_index.get(identity)
        if previous is not None and previous != binding:
            raise ValueError(f"artifact autorizado com binding conflitante: {identity}")
        artifact_index[identity] = binding

    constitution_version = declaration["constitution_version"]
    transformations = declaration["transformations"]
    if not isinstance(constitution_version, str) or not constitution_version:
        raise ValueError("constitution_version ausente")
    if not isinstance(transformations, list) or not transformations:
        raise ValueError("transformations ausentes")

    verified_transformations: list[dict] = []
    seen_ids: set[str] = set()
    for transformation in transformations:
        if not isinstance(transformation, dict):
            raise ValueError("transformation precisa ser objeto")
        keys = set(transformation)
        if not _REQUIRED_TRANSFORMATION_KEYS.issubset(keys) or not keys.issubset(_ALLOWED_TRANSFORMATION_KEYS):
            raise ValueError("transformation possui shape inválido")

        transformation_id = transformation["id"]
        if not isinstance(transformation_id, str) or not transformation_id:
            raise ValueError("transformation id ausente")
        if transformation_id in seen_ids:
            raise ValueError(f"transformation id duplicado: {transformation_id}")
        seen_ids.add(transformation_id)

        provenance_class = transformation["provenance_class"]
        if not isinstance(provenance_class, str) or not provenance_class:
            raise ValueError(f"{transformation_id}: provenance_class inválida")
        candidate_relations = transformation["candidate_relations"]
        if (
            not isinstance(candidate_relations, list)
            or not candidate_relations
            or any(not isinstance(item, str) or not item for item in candidate_relations)
            or len(candidate_relations) != len(set(candidate_relations))
        ):
            raise ValueError(f"{transformation_id}: candidate_relations inválidas")
        if transformation["observation_basis"] != "declared":
            raise ValueError("declared verifier só aceita observation_basis=declared")
        if "notes" in transformation and (not isinstance(transformation["notes"], str) or not transformation["notes"]):
            raise ValueError(f"{transformation_id}: notes inválidas")

        for side in ("inputs", "outputs"):
            artifacts = transformation[side]
            if not isinstance(artifacts, list) or not artifacts:
                raise ValueError(f"{transformation_id}: {side} ausente")
            for index, artifact in enumerate(artifacts):
                identity, kind, sha256 = _validate_artifact(
                    artifact,
                    f"{transformation_id}.{side}[{index}]",
                )
                if identity not in artifact_index:
                    raise ValueError(f"{transformation_id}: artifact não autorizado: {identity}")
                if artifact_index[identity] != (kind, sha256):
                    raise ValueError(f"{transformation_id}: binding diverge do artefato autorizado: {identity}")

        verified_transformations.append(deepcopy(transformation))

    return {
        "evidence_version": 1,
        "constitution_version": constitution_version,
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
        "transformations": verified_transformations,
    }
