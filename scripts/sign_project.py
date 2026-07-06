from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.project_signature import SIGNATURE_OWNER, write_manifest  # noqa: E402


def main() -> int:
    manifest_path = write_manifest(ROOT)
    print(f"Signed project as {SIGNATURE_OWNER}: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
