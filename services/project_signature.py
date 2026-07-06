from __future__ import annotations

import hashlib
import json
import os
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from services.dazzling_lock import (
    LOCK_ALGORITHM,
    LOCK_BRAND,
    LOCK_OWNER,
    LOCK_VERSION,
    PRIVATE_KEY_PATH_HINT,
    PUBLIC_KEY_PEM,
    load_public_key,
)


SIGNATURE_OWNER = LOCK_OWNER
SIGNATURE_BRAND = LOCK_BRAND
SIGNATURE_VERSION = LOCK_VERSION
SIGNATURE_FILE = "PROJECT_SIGNATURE.json"
SIGNATURE_LOG = Path("logs") / "project_signature.log"
SIGNATURE_LOCK_FILE = "services/dazzling_lock.py"

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "backups",
    "cache",
    "downloads",
    "logs",
    "outputs",
    "private",
    "runtimes",
    "secrets",
    "tools",
}

EXCLUDED_FILE_NAMES = {
    SIGNATURE_FILE,
    "model_paths.json",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".mp3",
    ".wav",
    ".onnx",
    ".pth",
    ".pt",
    ".npy",
}


@dataclass(frozen=True)
class SignatureResult:
    ok: bool
    status: str
    details: str
    checked_files: int = 0


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _signature_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "owner": manifest.get("owner"),
        "brand": manifest.get("brand"),
        "version": manifest.get("version"),
        "algorithm": manifest.get("algorithm"),
        "lock_file": manifest.get("lock_file"),
        "lock_file_sha256": manifest.get("lock_file_sha256"),
        "public_key_sha256": manifest.get("public_key_sha256"),
        "files": manifest.get("files") or [],
    }


def _payload_digest(manifest: dict[str, Any]) -> str:
    payload = json.dumps(_signature_payload(manifest), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(payload)


def _payload_bytes(manifest: dict[str, Any]) -> bytes:
    return json.dumps(_signature_payload(manifest), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _private_key_path(root: Path) -> Path:
    return root / PRIVATE_KEY_PATH_HINT


def _load_private_key(root: Path) -> Ed25519PrivateKey:
    private_key_path = _private_key_path(root)
    if not private_key_path.exists():
        raise FileNotFoundError(
            f"Missing Dazzling private key: {private_key_path}. "
            "Only the project owner can sign modified source files."
        )
    key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Dazzling private key is not an Ed25519 key.")
    return key


def make_signature(root: Path, manifest: dict[str, Any]) -> str:
    private_key = _load_private_key(root)
    signature = private_key.sign(_payload_bytes(manifest))
    return base64.b64encode(signature).decode("ascii")


def _verify_signature(manifest: dict[str, Any]) -> bool:
    try:
        signature = base64.b64decode(str(manifest.get("signature") or ""), validate=True)
        load_public_key().verify(signature, _payload_bytes(manifest))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def should_sign_file(root: Path, path: Path) -> bool:
    if not path.is_file():
        return False
    relative = path.relative_to(root)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.name in EXCLUDED_FILE_NAMES:
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return True


def iter_signed_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if should_sign_file(root, path))


def build_manifest(root: Path) -> dict[str, Any]:
    files = []
    for path in iter_signed_files(root):
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _hash_file(path),
            }
        )
    manifest = {
        "owner": SIGNATURE_OWNER,
        "brand": SIGNATURE_BRAND,
        "version": SIGNATURE_VERSION,
        "algorithm": LOCK_ALGORITHM,
        "lock_file": SIGNATURE_LOCK_FILE,
        "lock_file_sha256": _hash_file(root / SIGNATURE_LOCK_FILE),
        "public_key_sha256": _sha256_bytes(PUBLIC_KEY_PEM),
        "files": files,
    }
    manifest["payload_digest"] = _payload_digest(manifest)
    manifest["signature"] = make_signature(root, manifest)
    return manifest


def write_manifest(root: Path) -> Path:
    manifest_path = root / SIGNATURE_FILE
    manifest = build_manifest(root)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _log_signature(root: Path, message: str) -> None:
    try:
        log_path = root / SIGNATURE_LOG
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(message.rstrip() + "\n")
    except Exception:
        pass


def verify_project_signature(root: Path) -> SignatureResult:
    manifest_path = root / SIGNATURE_FILE
    if not manifest_path.exists():
        return SignatureResult(False, "Project signature is missing.", f"Missing file: {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return SignatureResult(False, "Project signature cannot be read.", str(exc))

    if manifest.get("owner") != SIGNATURE_OWNER:
        return SignatureResult(False, "Project signature owner is invalid.", f"Expected owner: {SIGNATURE_OWNER}")

    expected_payload_digest = _payload_digest(manifest)
    if manifest.get("payload_digest") != expected_payload_digest:
        return SignatureResult(False, "Project signature payload was changed.", "Manifest payload digest mismatch.")

    if manifest.get("algorithm") != LOCK_ALGORITHM:
        return SignatureResult(False, "Project signature algorithm is invalid.", f"Expected: {LOCK_ALGORITHM}")

    if manifest.get("lock_file") != SIGNATURE_LOCK_FILE:
        return SignatureResult(False, "Project signature lock file is invalid.", f"Expected: {SIGNATURE_LOCK_FILE}")

    lock_file = root / SIGNATURE_LOCK_FILE
    if not lock_file.exists():
        return SignatureResult(False, "Dazzling lock file is missing.", f"Missing file: {lock_file}")

    if manifest.get("lock_file_sha256") != _hash_file(lock_file):
        return SignatureResult(False, "Dazzling lock file was changed.", "Lock file hash mismatch.")

    if manifest.get("public_key_sha256") != _sha256_bytes(PUBLIC_KEY_PEM):
        return SignatureResult(False, "Dazzling public key does not match manifest.", "Public key hash mismatch.")

    if not _verify_signature(manifest):
        return SignatureResult(False, "Project signature value is invalid.", "Signature mismatch.")

    files = manifest.get("files") or []
    changed: list[str] = []
    missing: list[str] = []
    signed_paths = {str(item.get("path") or "") for item in files}
    for item in files:
        relative = str(item.get("path") or "")
        expected_hash = str(item.get("sha256") or "")
        path = root / relative
        if not path.exists():
            missing.append(relative)
            continue
        actual_hash = _hash_file(path)
        if actual_hash != expected_hash:
            changed.append(relative)

    current_paths = {path.relative_to(root).as_posix() for path in iter_signed_files(root)}
    unsigned = sorted(current_paths - signed_paths)

    details = []
    if changed:
        details.append("Changed files: " + ", ".join(changed[:20]))
    if missing:
        details.append("Missing files: " + ", ".join(missing[:20]))
    if unsigned:
        details.append("Unsigned files: " + ", ".join(unsigned[:20]))
    if changed or missing or unsigned:
        return SignatureResult(False, "Project signature check failed.", "\n".join(details), len(files))

    status = f"Project signature verified: {SIGNATURE_OWNER} ({len(files)} files)."
    _log_signature(root, status)
    return SignatureResult(True, status, "All signed files match the Dazzling manifest.", len(files))


def enforce_project_signature(root: Path) -> SignatureResult:
    result = verify_project_signature(root)
    if result.ok:
        return result

    _log_signature(root, f"{result.status}\n{result.details}")
    if os.environ.get("TTS_STUDIO_ALLOW_UNSIGNED") == "1":
        return SignatureResult(True, "Unsigned project allowed by environment.", result.details, result.checked_files)
    raise RuntimeError(f"{result.status}\n{result.details}\nSet TTS_STUDIO_ALLOW_UNSIGNED=1 only for trusted local development.")
