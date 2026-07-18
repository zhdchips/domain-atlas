"""Run the deterministic golden public-Demo evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from domain_atlas.demo.catalog import public_demo_catalog
from domain_atlas.evaluation.golden_demo import (
    DEFAULT_MANIFEST_PATH,
    evaluate_catalog,
    load_manifest,
    render_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the versioned golden public Demo catalog.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/golden-demo"))
    parser.add_argument("--prefix", default="latest")
    parser.add_argument("--generated-at", default=None, help="UTC date override for reproducible baseline artifacts.")
    args = parser.parse_args()

    result = evaluate_catalog(
        public_demo_catalog(),
        manifest=load_manifest(args.manifest),
        generated_at=args.generated_at,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{args.prefix}.json"
    markdown_path = args.output_dir / f"{args.prefix}.md"
    json_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    print(f"Golden Demo evaluation: {result.passed} / {result.total}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    return 0 if result.passed_gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
