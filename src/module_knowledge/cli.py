"""Local-only CLI. Gold-note access exists only in the evaluate command."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re

from .baseline import extractive_baseline
from .draft import draft_slice
from .evaluate import evaluate_candidate, extract_gold_sections
from .extract import extract_frozen
from .generation import generate_y2
from .latex import combine_latex_notes
from .render import render_latex
from .sources import freeze_slice


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="module-knowledge")
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze", help="Copy an exact official source slice into a private run")
    freeze.add_argument("--config", type=Path, required=True)
    freeze.add_argument("--root", type=Path, required=True, help="Read-only root of the module's source folder")
    build_latex = commands.add_parser("build-latex", help="Build a standalone LaTeX note from lecture fragments")
    build_latex.add_argument("--manifest", type=Path, required=True, help="JSON manifest beside private .tex fragments and figures")
    build_latex.add_argument("--output", type=Path, required=True, help="Standalone .tex output path outside the project")
    build_latex.add_argument("--template", type=Path, help="Optional LaTeX template override")
    build_latex.add_argument("--evidence-root", type=Path, help="Module root for source_files paths in the manifest")
    build_master = commands.add_parser("build-master", help="Combine standalone lecture/tutorial LaTeX notes")
    build_master.add_argument("--component", type=Path, action="append", required=True, help="Component .tex; repeat for each lecture/tutorial")
    build_master.add_argument("--module", required=True)
    build_master.add_argument("--academic-year", required=True)
    build_master.add_argument("--output", type=Path, required=True)
    build_master.add_argument("--template", type=Path)
    generate = commands.add_parser("generate-y2", help="Discover, snapshot, draft, and build all Year 2 lecture/tutorial notes")
    generate.add_argument("--year-root", type=Path, required=True, help="Year 2 directory containing module folders")
    generate.add_argument("--output-root", type=Path, required=True, help="Destination root; for module-local output, set this equal to --year-root")
    generate.add_argument("--in-module-generated", action="store_true", help="Write each module's outputs to its generated/ directory")
    generate.add_argument("--academic-year", required=True)
    generate.add_argument("--endpoint", default="http://127.0.0.1:11434")
    generate.add_argument("--model", default="qwen3:8b")
    generate.add_argument("--visual-model", default="qwen3-vl:8b-instruct")
    generate.add_argument("--no-pdf", action="store_true", help="Generate .tex only; do not invoke the pinned PDF builder")
    generate.add_argument("--module", dest="modules", action="append", help="Exact module directory name; repeat to select several")
    generate.add_argument("--weeks", help="Explicit teaching weeks, for example 1-5 or 1,3-5")
    generate.add_argument("--run-name", help="Fresh output directory under generated/runs/; required for scoped runs")
    generate.add_argument("--dry-run", action="store_true", help="Print input inventory and gaps without writes or model calls")
    for name in ("freeze", "extract", "baseline", "draft", "render", "evaluate"):
        command = freeze if name == "freeze" else commands.add_parser(name)
        command.add_argument("--run", type=Path, required=True, help="Private path outside the project")
        command.add_argument("--slice", choices=("development", "locked_test"), default="development")
        if name in {"freeze", "draft"}:
            command.add_argument("--unlock-test", action="store_true")
        if name == "draft":
            command.add_argument("--endpoint", default="http://127.0.0.1:11434")
            command.add_argument("--model", default="qwen3:8b")
        if name in {"render", "evaluate"}:
            command.add_argument("--label", default="Lecture 1")
            command.add_argument("--variant", choices=("model", "baseline"), default="model")
        if name == "evaluate":
            command.add_argument("--gold-docx", type=Path, required=True)
    args = parser.parse_args(argv)
    os.umask(0o077)
    project_root = Path(__file__).resolve().parents[2]
    if args.command == "build-latex":
        output = args.output.resolve()
        if output == project_root or output.is_relative_to(project_root):
            parser.error("Generated notes must live outside the project tree")
        manifest_path = args.manifest.resolve(strict=True)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        result = render_latex(
            manifest,
            output,
            source_root=manifest_path.parent,
            evidence_root=args.evidence_root,
            template_path=args.template,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "build-master":
        output = args.output.resolve()
        if output == project_root or output.is_relative_to(project_root):
            parser.error("Generated notes must live outside the project tree")
        result = combine_latex_notes(
            args.component,
            output,
            module=args.module,
            academic_year=args.academic_year,
            template_path=args.template,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "generate-y2":
        output = args.output_root.resolve()
        if output == project_root or output.is_relative_to(project_root):
            parser.error("Generated notes must live outside the project tree")
        year_root = args.year_root.resolve(strict=True)
        if args.in_module_generated and output != year_root:
            parser.error("--output-root must equal --year-root with --in-module-generated")
        from .inventory import parse_weeks
        try:
            selected_weeks = parse_weeks(args.weeks) if args.weeks else None
        except ValueError as error:
            parser.error(str(error))
        result = generate_y2(
            year_root,
            output,
            academic_year=args.academic_year,
            endpoint=args.endpoint,
            model=args.model,
            visual_model=args.visual_model,
            compile_pdfs=not args.no_pdf,
            project_root=project_root,
            in_module_generated=args.in_module_generated,
            modules=args.modules,
            weeks=selected_weeks,
            run_name=args.run_name,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    run = args.run.resolve()
    if run == project_root or run.is_relative_to(project_root):
        parser.error("Private run must live outside the project tree")
    name = args.slice
    if args.command == "freeze":
        snapshot = freeze_slice(args.config, args.root, run, name, unlock_test=args.unlock_test)
        result = {"slice": name, "source_count": len(snapshot["sources"]), "manifest": str(run / f"frozen-{name}.json")}
    else:
        frozen = json.loads((run / f"frozen-{name}.json").read_text(encoding="utf-8"))
        if args.command == "extract":
            result = extract_frozen(frozen, run / f"evidence-{name}.jsonl")
        elif args.command == "baseline":
            blocks = [json.loads(line) for line in (run / f"evidence-{name}.jsonl").read_text(encoding="utf-8").splitlines()]
            baseline = extractive_baseline(frozen, blocks)
            destination = run / f"baseline-{name}.json"
            destination.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
            result = {"baseline": str(destination), "items": len(baseline["items"]), "skipped": len(baseline["skipped"])}
        elif args.command == "draft":
            blocks = [json.loads(line) for line in (run / f"evidence-{name}.jsonl").read_text(encoding="utf-8").splitlines()]
            draft = draft_slice(frozen, blocks, endpoint=args.endpoint, model=args.model, checkpoint_dir=run / "model-checkpoints", allow_locked_test=args.unlock_test)
            destination = run / f"draft-{name}.json"
            destination.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
            result = {"draft": str(destination), "items": len(draft["items"]), "skipped": len(draft["skipped"])}
        elif args.command == "render":
            input_name = f"baseline-{name}.json" if args.variant == "baseline" else f"draft-{name}.json"
            suffix = "-baseline" if args.variant == "baseline" else ""
            draft = json.loads((run / input_name).read_text(encoding="utf-8"))
            module = str(draft.get("module") or frozen.get("module") or "Accounting")
            draft["module"] = module
            module_slug = re.sub(r"[^A-Za-z0-9-]+", "-", module).strip("-") or "Module"
            result = render_latex(draft, run / f"{module_slug}-{name}{suffix}.tex", label=args.label)
        elif args.command == "evaluate":
            suffix = "-baseline" if args.variant == "baseline" else ""
            module = str(frozen.get("module") or "Accounting")
            module_slug = re.sub(r"[^A-Za-z0-9-]+", "-", module).strip("-") or "Module"
            draft_tex = run / f"{module_slug}-{name}{suffix}.tex"
            sidecar = json.loads(draft_tex.with_suffix(".evidence.json").read_text(encoding="utf-8"))
            blocks = [json.loads(line) for line in (run / f"evidence-{name}.jsonl").read_text(encoding="utf-8").splitlines()]
            gold = extract_gold_sections(args.gold_docx, label=args.label)
            result = evaluate_candidate(gold, draft_tex, sidecar, blocks)
            (run / f"evaluation-{name}{suffix}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        else:
            raise AssertionError("Unknown command")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
