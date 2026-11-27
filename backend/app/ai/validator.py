"""Validation & guardrails (Spec 6).

Layer 1  request eligibility            -> before Gemini
Layer 2  payload validation             -> before Gemini
Layer 3  schema validation              -> Pydantic
Layer 4  evidence validation            -> evidence_validator
Layer 5  numeric consistency            -> every number in AI text must map to payload
Layer 6  policy validation              -> prohibited claims (Spec 6.4) + flag rules (3.3)
Post     limitation enforcement         -> backend appends mandatory limitations
"""
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from pydantic import ValidationError

from app.ai.evidence_validator import EvidenceValidator
from app.ai.input_schema import AIInputPayload
from app.ai.output_schema import AIAnalysisOutput
from app.core.config import settings

# ---------------------------------------------------------------- Layer 1
# Status names produced by the solver adapter (PuLP: pulp.LpStatus values),
# normalised to lower case. Spec 2.3 + "use the enum the adapter really emits".
ELIGIBLE_STATUSES = {"optimal", "feasible"}
BLOCK_REASONS = {
    "infeasible": "Solver infeasible: constraint tidak dapat dipenuhi bersamaan. "
                  "Rekomendasi alokasi tidak dibuat; periksa kapasitas/intake/kompatibilitas.",
    "unbounded": "Solver unbounded: formulasi model perlu diperiksa. Analisis operasional diblok.",
    "not solved": "Solver belum menyelesaikan model. Analisis hasil diblok.",
    "undefined": "Status solver undefined. Analisis hasil diblok.",
    "error": "Solver error. Lihat log backend; analisis hasil diblok.",
}


def check_eligibility(solver_status: Optional[str]) -> Tuple[bool, str]:
    s = (solver_status or "").strip().lower()
    if s in ELIGIBLE_STATUSES:
        return True, s
    return False, BLOCK_REASONS.get(s, f"Status solver '{solver_status}' tidak dikenal; analisis diblok.")


# ---------------------------------------------------------------- Layer 2
def validate_payload(payload: AIInputPayload) -> List[str]:
    errors: List[str] = []

    def walk(obj: Any, path: str):
        if isinstance(obj, float) and not math.isfinite(obj):
            errors.append(f"Nilai non-finite pada {path}")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(payload.model_dump(), "")

    w = payload.weights
    if abs((w.cost + w.recovery + w.residual) - 1.0) > 0.01:
        errors.append(f"Jumlah bobot objective harus 1.0 (saat ini {w.cost + w.recovery + w.residual:.3f})")
    if payload.metrics.total_input_kg <= 0:
        errors.append("total_input_kg harus > 0")
    if "period_mismatch" in payload.data_quality_flags:
        # Spec 3.3: block analysis until data is fixed.
        errors.append("period_mismatch: periode intake dan kapasitas tidak konsisten; perbaiki data dulu.")
    route_ids = {r.route_id for r in payload.routes}
    orphan = sorted({a.route_id for a in payload.allocations} - route_ids)
    if payload.routes and orphan:
        errors.append(f"Alokasi merujuk route yang tidak ada di routes: {orphan}")
    if not payload.evidence_catalog:
        errors.append("evidence_catalog kosong")
    size = len(payload.model_dump_json().encode())
    if size > settings.AI_MAX_PAYLOAD_BYTES:
        errors.append(f"Payload terlalu besar ({size} byte > {settings.AI_MAX_PAYLOAD_BYTES})")
    return errors


# ---------------------------------------------------------------- Layer 3
def validate_schema(raw: Optional[Dict[str, Any]]) -> Tuple[Optional[AIAnalysisOutput], List[str]]:
    if raw is None:
        return None, ["Output bukan JSON yang dapat diparse"]
    try:
        return AIAnalysisOutput.model_validate(raw), []
    except ValidationError as e:
        return None, [f"{'.'.join(map(str, er['loc']))}: {er['msg']}" for er in e.errors()][:20]


# ---------------------------------------------------------------- Layer 5
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_NUM_RE = re.compile(r"(?<![\w\-:])(\d+(?:[.,]\d+)*)(\s?%)?(?![\w\-])")


def _iter_text(output: AIAnalysisOutput) -> Iterable[Tuple[str, str]]:
    yield "summary", output.summary
    for i, it in enumerate(output.operational_insights):
        yield f"operational_insights[{i}].title", it.title
        yield f"operational_insights[{i}].finding", it.finding
    for i, t in enumerate(output.optimization_interpretation.tradeoffs):
        yield f"tradeoffs[{i}].statement", t.statement
    for i, r in enumerate(output.recommendations):
        yield f"recommendations[{i}].action", r.action
        yield f"recommendations[{i}].rationale", r.rationale
    for i, l in enumerate(output.limitations):
        yield f"limitations[{i}]", l


def _candidates(token: str) -> Set[float]:
    """All plausible values of a number written in id-ID or en-US style."""
    out: Set[float] = set()
    t = token
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):            # 1.200,5 (id)
            out.add(float(t.replace(".", "").replace(",", ".")))
        else:                                        # 1,200.5 (en)
            out.add(float(t.replace(",", "")))
    elif "," in t:
        out.add(float(t.replace(",", ".")) if t.count(",") == 1 else float(t.replace(",", "")))
        if re.fullmatch(r"\d{1,3}(,\d{3})+", t):
            out.add(float(t.replace(",", "")))
    elif "." in t:
        if t.count(".") == 1:
            out.add(float(t))
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
            out.add(float(t.replace(".", "")))
    else:
        out.add(float(t))
    return out


def _known_numbers(payload: AIInputPayload) -> Set[float]:
    known: Set[float] = set()

    def walk(obj: Any):
        if isinstance(obj, bool):
            return
        if isinstance(obj, (int, float)):
            known.add(float(obj))
            if 0 <= obj <= 1:
                known.add(float(obj) * 100)  # fraction quoted as percent
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(payload.model_dump(exclude={"evidence_catalog", "units"}))
    for r in payload.routes:  # utilization can exceed 1 in principle
        known.add(r.utilization_rate * 100)
    known.update({float(len(payload.routes)), float(len(payload.allocations))})
    known.update(float(i) for i in range(0, 11))  # small counts/ordinals
    return known


def _matches(value: float, known: Set[float], is_integer_token: bool) -> bool:
    for k in known:
        tol = max(settings.AI_NUMERIC_REL_TOLERANCE * abs(k), 0.051)
        if is_integer_token:
            tol = max(tol, 0.5)  # "83%" for 83.33
        if abs(value - k) <= tol:
            return True
    return False


def validate_numbers(output: AIAnalysisOutput, payload: AIInputPayload) -> List[str]:
    known = _known_numbers(payload)
    issues: List[str] = []
    for where, text in _iter_text(output):
        clean = _DATE_RE.sub(" ", text)
        clean = re.sub(r"\bRp\.?\s?", "Rp ", clean)
        for m in _NUM_RE.finditer(clean):
            token = m.group(1)
            try:
                cands = _candidates(token)
            except ValueError:
                continue
            is_int = not re.search(r"[.,]\d{1,2}$", token)
            if not any(_matches(c, known, is_int) for c in cands):
                issues.append(f"{where}: angka '{token}{(m.group(2) or '').strip()}' tidak dapat dipetakan ke payload backend")
    return issues


# ---------------------------------------------------------------- Layer 6
def _sentences(text: str) -> List[str]:
    return [s for s in re.split(r"(?<=[.!?;])\s+", text) if s.strip()]


def validate_policy(output: AIAnalysisOutput, payload: AIInputPayload) -> List[str]:
    v: List[str] = []
    status = payload.solver.status.strip().lower()
    flags = set(payload.data_quality_flags)

    main_parts = [output.summary]
    main_parts += [i.title + ". " + i.finding for i in output.operational_insights]
    main_parts += [t.statement for t in output.optimization_interpretation.tradeoffs]
    main_parts += [r.action + ". " + r.rationale for r in output.recommendations]
    main = " ".join(main_parts)
    low = main.lower()

    # AI must echo, never change, the solver status.
    if output.optimization_interpretation.solver_status.strip().lower() != status:
        v.append(f"solver_status output ('{output.optimization_interpretation.solver_status}') "
                 f"berbeda dari status backend ('{payload.solver.status}')")

    # 6.4-1 city-wide impact claims
    if re.search(r"(mengurangi|menurunkan|reduc\w*|cut\w*)[^.]{0,60}(sampah (di |se)?kota|city[- ]?wide|municipal|seluruh kota)", low):
        v.append("Klaim dampak skala kota tanpa evaluasi eksternal")

    # 6.4-2 guaranteed outcomes without a valid comparison
    if re.search(r"\bdijamin\b|\bguarantee", low) or (
        payload.baseline_metrics is None
        and re.search(r"\bpasti (turun|menurun|naik|meningkat|hemat|berkurang)|\bwill (definitely|certainly)", low)
    ):
        v.append("Klaim hasil pasti/dijamin tanpa pembanding yang valid")

    # 6.4-3 'optimal' when solver is not optimal
    if status != "optimal":
        for s in _sentences(low):
            if re.search(r"(?<!non-)\boptimal\b", s) and not re.search(r"\b(tidak|bukan|belum|not|non)\b[^.]{0,25}optimal", s):
                v.append("Menyebut hasil 'optimal' padahal status solver bukan optimal")
                break

    # 6.4-4 capacity increase without bottleneck evidence + cost consideration
    cap_re = r"(tambah\w*|menambah\w*|penambahan|perluas\w*|ekspansi|increase|add\w*|expand\w*)\s[^.]{0,20}(kapasitas|capacity)"
    hot = {f"route_utilization:{r.route_id}" for r in payload.routes if r.utilization_rate >= 0.85}
    for i, r in enumerate(output.recommendations):
        txt = (r.action + " " + r.rationale).lower()
        if re.search(cap_re, txt):
            if not (set(r.evidence) & hot):
                v.append(f"recommendations[{i}]: saran tambah kapasitas tanpa evidence utilisasi tinggi (>=85%)")
            elif not re.search(r"biaya|cost", txt):
                v.append(f"recommendations[{i}]: saran tambah kapasitas tanpa pertimbangan biaya")

    # 6.4-5 residual treated as unallocated
    if re.search(r"residu\w*[^.]{0,40}(belum|tidak)\s+(di)?alokasi|residual[^.]{0,40}unallocated", low):
        v.append("Memperlakukan residu proses sebagai material belum dialokasikan")

    # 3.3 baseline_unavailable -> no baseline comparison
    if "baseline_unavailable" in flags:
        for s in _sentences(low):
            if "baseline" in s and re.search(r"dibanding|lebih (rendah|tinggi|baik|hemat)|turun|naik|meningkat|menurun|compared|than|lower|higher", s):
                v.append("Membandingkan dengan baseline padahal baseline tidak tersedia")
                break

    # 3.3 missing_route_profile -> keep allocation advice off incomplete routes
    # (cannot be detected generically; enforced via prompt + mandatory limitation)
    return v


# ---------------------------------------------------------------- Post-processing
_REQUIRED_LIMITATIONS = {
    "synthetic_data": (r"sintetis|simulasi|synthetic|simulat",
                       "Analisis berbasis data sintetis (simulasi), bukan bukti kondisi lapangan."),
    "yield_assumption": (r"yield|asumsi|estimasi|assum",
                         "Sebagian yield berasal dari estimasi/asumsi; rekomendasi yang bergantung pada yield bersifat sementara."),
    "missing_route_profile": (r"profil rute|route profile|parameter[^.]{0,30}(rute|route)|tidak lengkap|incomplete",
                              "Parameter material-rute belum lengkap; jangan mengalokasikan ke rute yang profilnya belum lengkap."),
    "baseline_unavailable": (r"baseline|pembanding",
                             "Baseline tidak tersedia, sehingga tidak ada perbandingan terhadap baseline."),
}


def enforce_limitations(output: AIAnalysisOutput, payload: AIInputPayload) -> List[str]:
    """Append backend-authored limitations the model omitted. Returns the added texts."""
    added: List[str] = []
    joined = " ".join(output.limitations).lower()
    for flag in payload.data_quality_flags:
        if flag in _REQUIRED_LIMITATIONS:
            pattern, text = _REQUIRED_LIMITATIONS[flag]
            if not re.search(pattern, joined):
                output.limitations.append(text)
                added.append(text)
    return added


# ---------------------------------------------------------------- Orchestration
@dataclass
class OutputValidationReport:
    output: Optional[AIAnalysisOutput] = None
    schema_errors: List[str] = field(default_factory=list)
    evidence_errors: List[str] = field(default_factory=list)
    numeric_errors: List[str] = field(default_factory=list)
    policy_errors: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.output is not None and not (
            self.schema_errors or self.evidence_errors or self.numeric_errors or self.policy_errors
        )

    @property
    def failed_layer(self) -> Optional[str]:
        for name, errs in (("SchemaValidation", self.schema_errors),
                           ("EvidenceValidation", self.evidence_errors),
                           ("NumericConsistency", self.numeric_errors),
                           ("PolicyValidation", self.policy_errors)):
            if errs:
                return name
        return None

    def summary(self) -> Dict[str, List[str]]:
        return {k: getattr(self, k) for k in
                ("schema_errors", "evidence_errors", "numeric_errors", "policy_errors")
                if getattr(self, k)}


def validate_output(raw: Optional[Dict[str, Any]], payload: AIInputPayload) -> OutputValidationReport:
    rep = OutputValidationReport()
    rep.output, rep.schema_errors = validate_schema(raw)
    if rep.output is None:
        return rep
    _, rep.evidence_errors = EvidenceValidator.validate_evidence_keys(rep.output, payload.evidence_catalog)
    rep.numeric_errors = validate_numbers(rep.output, payload)
    rep.policy_errors = validate_policy(rep.output, payload)
    return rep


def feedback_for_retry(rep: OutputValidationReport) -> str:
    return ("Your previous JSON was rejected by the backend validator for these reasons:\n"
            + json.dumps(rep.summary(), ensure_ascii=False, indent=1)
            + "\nReturn a corrected, complete JSON object. Remove any number you cannot "
              "copy exactly from the payload and use only keys from evidence_catalog.")
