"""Producer determinístico que verifica declarações de provenance contra artefatos autorizados."""

from __future__ import annotations

from copy import deepcopy

PRODUCER_ID = "evolutive.provenance.declared_manifest_verifier"
PRODUCER_VERSION = "0.1.0"


def verify(declaration: dict, authorized_artifacts: list[dict]) -> dict:
    """Valida bindings declarados sem executar código do consumidor.

    `authorized_artifacts` deve conter somente identidades já autorizadas por uma
    autoridade externa, com `identity`, `kind` e `sha256` exatos.
    """

    if not isinstance(declaration, dict):
        raise ValueError("declaration precisa ser objeto")
    if not isinstance(authorized_artifacts, list):
        raise ValueError("authorized_artifacts precisa ser lista")

    artifact_index: dict[str, tuple[str, str]] = {}
    for artifact in authorized_artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("artifact autorizado precisa ser objeto")
        identity = artifact.get("identity")
        kind = artifact.get("kind")
        sha256 = artifact.get("sha256")
        if not all(isinstance(value, str) and value for value in (identity, kind, sha256)):
            raise ValueError("artifact autorizado incompleto")
        binding = (kind, sha256)
        previous = artifact_index.get(identity)
        if previous is not None and previous != binding:
            raise ValueError(f"artifact autorizado com binding conflitante: {identity}")
        artifact_index[identity] = binding

    constitution_version = declaration.get("constitution_version")
    transformations = declaration.get("transformations")
    if not isinstance(constitution_version, str) or not constitution_version:
        raise ValueError("constitution_version ausente")
    if not isinstance(transformations, list) or not transformations:
        raise ValueError("transformations ausentes")

    verified_transformations: list[dict] = []
    seen_ids: set[str] = set()
    for transformation in transformations:
        if not isinstance(transformation, dict):
            raise ValueError("transformation precisa ser objeto")
        transformation_id = transformation.get("id")
        if not isinstance(transformation_id, str) or not transformation_id:
            raise ValueError("transformation id ausente")
        if transformation_id in seen_ids:
            raise ValueError(f"transformation id duplicado: {transformation_id}")
        seen_ids.add(transformation_id)

        if transformation.get("observation_basis") != "declared":
            raise ValueError("declared verifier só aceita observation_basis=declared")

        for side in ("inputs", "outputs"):
            artifacts = transformation.get(side)
            if not isinstance(artifacts, list) or not artifacts:
                raise ValueError(f"{transformation_id}: {side} ausente")
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    raise ValueError(f"{transformation_id}: artifact inválido")
                identity = artifact.get("identity")
                binding = (artifact.get("kind"), artifact.get("sha256"))
                if identity not in artifact_index:
                    raise ValueError(f"{transformation_id}: artifact não autorizado: {identity}")
                if artifact_index[identity] != binding:
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
