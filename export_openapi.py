import json
from pathlib import Path

from src.main import app  # FastAPI app


def main() -> None:
    schema = app.openapi()  # dict
    out_path = Path("openapi") / "openapi.generated.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2))
    print(f"Wrote {out_path}")  # noqa: T201


if __name__ == "__main__":
    main()
