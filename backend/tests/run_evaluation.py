"""Evaluation runner (Spec 9).

    python -m tests.run_evaluation                 # mock provider (pipeline check only)
    python -m tests.run_evaluation --live          # real Gemini (uses quota!)
    python -m tests.run_evaluation --live --cases case_02_high_utilization_bottleneck,case_15_synthetic_bottleneck_yield
    python -m tests.run_evaluation --live --delay 10

Writes reports/eval_<timestamp>.json and .md. The markdown has an empty
"Human score (1-5)" column for the Spec 9.3 review rubric. Mock results only
prove the pipeline/guardrails; they say nothing about Gemini quality.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.ai.errors import AIError  # noqa: E402
from app.ai.gemini_client import GeminiClient, MockAIClient  # noqa: E402
from app.core.config import BACKEND_DIR, settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.integration.run_provider import LocalRunProvider  # noqa: E402
from app.models.optimization_run import OptimizationRun  # noqa: E402
from app.services.ai_service import AIService  # noqa: E402
from tests.evaluation_testset import EVALUATION_CASES  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--cases", default="")
    ap.add_argument("--delay", type=float, default=3.0, help="seconds between live calls")
    args = ap.parse_args()

    settings.AI_ANALYSIS_COOLDOWN_SECONDS = 0
    engine = create_engine(f"sqlite:///{(BACKEND_DIR / 'eval.db').as_posix()}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    factory = GeminiClient if args.live else MockAIClient
    mode = f"LIVE {settings.GEMINI_MODEL}" if args.live else "MOCK"
    wanted = {c for c in args.cases.split(",") if c}
    cases = [c for c in EVALUATION_CASES if not wanted or c["id"] in wanted]

    print(f"WasteFlow AI evaluation | mode={mode} | prompt={settings.PROMPT_VERSION} | cases={len(cases)}")
    rows = []
    for i, case in enumerate(cases):
        snap = dict(case["payload"])
        run = OptimizationRun(status=snap["solver"]["status"], data_source=snap["data_source"],
                              snapshot_data=snap)
        db.add(run)
        db.commit()
        svc = AIService(db, LocalRunProvider(db), factory)
        row = {"id": case["id"], "name": case["name"], "data_source": snap["data_source"],
               "expected_eligible": case["expected_eligibility"]}
        try:
            res = svc.run_analysis(run.id)
            r = res["result"]
            row.update(outcome="valid", latency_ms=res["latency_ms"], attempts=res["attempts"],
                       analysis_id=res["analysis_id"],
                       n_insights=len(r["operational_insights"]), n_recs=len(r["recommendations"]),
                       limitations_added=(res["validation_report"] or {}).get("limitations_added_by_backend", []),
                       summary=r["summary"])
        except AIError as e:
            row.update(outcome=e.code, layer=e.layer, message=e.message, details=e.details,
                       analysis_id=e.analysis_id)
        blocked = row["outcome"] in ("RUN_NOT_ELIGIBLE", "PAYLOAD_NOT_READY")
        row["pass"] = (row["outcome"] == "valid") if case["expected_eligibility"] else blocked
        rows.append(row)
        print(f"  [{'PASS' if row['pass'] else 'FAIL'}] {case['id']:<40} {row['outcome']}")
        if args.live and i < len(cases) - 1 and not blocked:
            time.sleep(args.delay)
    db.close()

    out_dir = BACKEND_DIR / "reports"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    meta = {"mode": mode, "model": settings.GEMINI_MODEL if args.live else "mock",
            "prompt_version": settings.PROMPT_VERSION, "temperature": settings.GEMINI_TEMPERATURE,
            "n_cases": len(rows), "n_pass": sum(r["pass"] for r in rows),
            "n_valid_outputs": sum(r["outcome"] == "valid" for r in rows),
            "n_rejected_outputs": sum(r["outcome"] == "AI_OUTPUT_INVALID" for r in rows),
            "n_provider_failures": sum(r["outcome"].startswith("AI_") and r["outcome"] != "AI_OUTPUT_INVALID" for r in rows)}
    (out_dir / f"eval_{stamp}.json").write_text(json.dumps({"meta": meta, "cases": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [f"# WasteFlow AI Evaluation {stamp}", "", *(f"- **{k}**: {v}" for k, v in meta.items()), "",
          "| Case | Data | Outcome | Pass | Latency ms | Human score (1-5) | Notes |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['id']} | {r['data_source']} | {r['outcome']} | {'yes' if r['pass'] else 'no'} | "
                  f"{r.get('latency_ms', '')} |  |  |")
    md += ["", "> Sample kecil; jangan mengklaim performa umum (Spec 9.3)."]
    (out_dir / f"eval_{stamp}.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\nPass {meta['n_pass']}/{meta['n_cases']} | valid={meta['n_valid_outputs']} "
          f"rejected={meta['n_rejected_outputs']} provider_failures={meta['n_provider_failures']}")
    print(f"Report: reports/eval_{stamp}.md")


if __name__ == "__main__":
    main()
