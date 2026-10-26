"""Export the FastAPI schema to the repository root for frontend type generation."""

import json
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_path))
from app.main import app  # noqa: E402

output_path = backend_path.parent / "openapi.json"
output_path.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
print(f"Wrote {output_path}")
