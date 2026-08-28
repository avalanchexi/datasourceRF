from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pring_cycle.health_types import ArtifactHealth
from pring_cycle.storage import (
    artifact_is_registered,
    artifact_registry_available,
    register_artifact,
)


@dataclass(frozen=True)
class StoredArtifact:
    content_hash: str
    media_type: str
    path: Path
    size: int
    source_reference: str


def store_artifact(
    database_path: Path,
    artifacts_root: Path,
    content: bytes,
    media_type: str,
    source_reference: str,
) -> StoredArtifact:
    content_hash = hashlib.sha256(content).hexdigest()
    artifact_directory = artifacts_root / content_hash[:2]
    artifact_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    artifact_directory.chmod(0o700)
    artifact_path = artifact_directory / content_hash
    temporary_path: Path | None = None
    try:
        if not artifact_path.exists():
            with tempfile.NamedTemporaryFile(
                dir=artifact_directory,
                prefix=f".{content_hash}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                os.fchmod(temporary_file.fileno(), 0o600)
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, artifact_path)
            temporary_path = None
        if hashlib.sha256(artifact_path.read_bytes()).hexdigest() != content_hash:
            raise ValueError("artifact_hash_mismatch")
        register_artifact(
            database_path,
            content_hash=content_hash,
            byte_count=len(content),
            media_type=media_type,
            source_reference=source_reference,
            created_at=datetime.now(UTC),
        )
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return StoredArtifact(
        content_hash=content_hash,
        media_type=media_type,
        path=artifact_path,
        size=len(content),
        source_reference=source_reference,
    )


def read_artifact(artifact: StoredArtifact) -> bytes:
    content = artifact.path.read_bytes()
    if hashlib.sha256(content).hexdigest() != artifact.content_hash:
        raise ValueError("artifact_hash_mismatch")
    return content


def artifact_health(database_path: Path, artifacts_root: Path) -> ArtifactHealth:
    available = artifacts_root.is_dir() and artifact_registry_available(database_path)
    return {
        "addressing": "sha256",
        "status": "ok" if available else "missing",
    }


def artifact_registration_exists(database_path: Path, artifact: StoredArtifact) -> bool:
    return artifact_is_registered(
        database_path,
        artifact.content_hash,
        artifact.source_reference,
    )
