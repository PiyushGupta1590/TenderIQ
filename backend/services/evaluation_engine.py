"""
Stage 3 — Evaluation Engine
Compares bidder extracted fields against tender rules → ELIGIBLE / NOT_ELIGIBLE / MANUAL_REVIEW
Generates a per-decision audit log for government procurement auditability.
Computes separate mandatory-only verdict alongside overall verdict.
"""
import uuid
from datetime import datetime, timezone
from typing import List

from backend.models.tender import TenderRule, TenderRuleSet, RuleOperator
from backend.models.bidder import BidderData
from backend.models.evaluation import (
    Verdict, RuleResult, BidderResult, EvaluationReport, AuditEntry
)
from backend.config import CONFIDENCE_THRESHOLD, BORDERLINE_MARGIN


def _evaluate_rule(rule: TenderRule, bidder: BidderData) -> RuleResult:
    """Evaluate a single rule against a bidder's extracted fields."""

    # Find the extracted field matching this rule
    field_data = next(
        (f for f in bidder.extracted_fields if f.field == rule.field),
        None
    )

    rule_desc = _rule_description(rule)
    # Source document: prefer the specific file that had the evidence
    source_doc = (
        field_data.source_file if field_data and field_data.source_file
        else (bidder.uploaded_files[0] if bidder.uploaded_files else None)
    )

    base = dict(
        rule_id=rule.id,
        rule_label=rule.label,
        rule_description=rule_desc,
        rule_mandatory=rule.mandatory,
        required_value=rule.value,
        required_unit=rule.unit,
        source_document=source_doc,
    )

    # Field not found in bidder docs
    if field_data is None:
        return RuleResult(
            **base,
            found_value=None,
            found_raw=None,
            verdict=Verdict.MANUAL_REVIEW,
            confidence=0.0,
            source_page=None,
            explanation=(
                f"Field '{rule.label}' was not found in any of the "
                f"{len(bidder.uploaded_files)} uploaded document(s). "
                "Manual verification required."
            ),
            needs_officer_action=True,
        )

    conf = field_data.confidence
    source_page = field_data.source_page

    # PRESENT rule — just check if value exists
    if rule.operator == RuleOperator.PRESENT:
        if field_data.value:
            return RuleResult(
                **base,
                found_value=None,
                found_raw=str(field_data.value)[:150],
                verdict=Verdict.ELIGIBLE if conf >= CONFIDENCE_THRESHOLD else Verdict.MANUAL_REVIEW,
                confidence=conf,
                source_page=source_page,
                explanation=(
                    f"Found: '{field_data.value}' in '{source_doc}' (page {source_page}). "
                    f"Confidence {conf:.0%}."
                    + ("" if conf >= CONFIDENCE_THRESHOLD
                       else " Low OCR confidence — please verify the original document.")
                ),
                needs_officer_action=conf < CONFIDENCE_THRESHOLD,
            )
        else:
            return RuleResult(
                **base,
                found_value=None,
                found_raw=field_data.raw_text,
                verdict=Verdict.NOT_ELIGIBLE,
                confidence=conf,
                source_page=source_page,
                explanation=(
                    f"Required: '{rule.label}' must be present. "
                    f"Document '{source_doc}' matched the keyword but value is empty — "
                    "flag for officer verification."
                ),
                needs_officer_action=True,
            )

    # Numeric comparison rules
    if rule.value is None:
        return RuleResult(
            **base,
            found_value=None,
            found_raw=None,
            verdict=Verdict.MANUAL_REVIEW,
            confidence=0.3,
            source_page=source_page,
            explanation=(
                "Rule threshold not defined in tender document. "
                "Refer to tender clause for manual verification."
            ),
            needs_officer_action=True,
        )

    try:
        found_val = float(field_data.value)
    except (TypeError, ValueError):
        return RuleResult(
            **base,
            found_value=None,
            found_raw=field_data.raw_text,
            verdict=Verdict.MANUAL_REVIEW,
            confidence=conf,
            source_page=source_page,
            explanation=(
                f"Could not parse a numeric value from '{field_data.raw_text}' "
                f"in document '{source_doc}' (page {source_page}). "
                "Manual check required."
            ),
            needs_officer_action=True,
        )

    required = rule.value
    margin = required * BORDERLINE_MARGIN  # 5% borderline zone

    # Determine pass/fail
    if rule.operator == RuleOperator.GTE:
        passes = found_val >= required
        borderline = abs(found_val - required) <= margin
    elif rule.operator == RuleOperator.LTE:
        passes = found_val <= required
        borderline = abs(found_val - required) <= margin
    elif rule.operator == RuleOperator.GT:
        passes = found_val > required
        borderline = (required - found_val) <= margin
    elif rule.operator == RuleOperator.LT:
        passes = found_val < required
        borderline = (found_val - required) <= margin
    elif rule.operator == RuleOperator.EQ:
        passes = abs(found_val - required) < 0.01
        borderline = abs(found_val - required) <= margin
    else:
        passes = False
        borderline = False

    # Decide verdict
    if conf < CONFIDENCE_THRESHOLD:
        verdict = Verdict.MANUAL_REVIEW
        explanation = (
            f"Found {_fmt(found_val, rule.unit)} in '{source_doc}' (page {source_page}). "
            f"Required {rule.operator} {_fmt(required, rule.unit)}. "
            f"OCR confidence {conf:.0%} is below threshold — human verification required."
        )
        needs_action = True
    elif passes and borderline:
        verdict = Verdict.MANUAL_REVIEW
        explanation = (
            f"Found {_fmt(found_val, rule.unit)} in '{source_doc}' (page {source_page}), "
            f"which is within {BORDERLINE_MARGIN:.0%} of the threshold "
            f"{_fmt(required, rule.unit)}. Borderline — officer review recommended."
        )
        needs_action = True
    elif passes:
        verdict = Verdict.ELIGIBLE
        explanation = (
            f"Found {_fmt(found_val, rule.unit)} in '{source_doc}' (page {source_page}), "
            f"which satisfies the requirement {rule.operator} {_fmt(required, rule.unit)}."
        )
        needs_action = False
    else:
        verdict = Verdict.NOT_ELIGIBLE
        explanation = (
            f"Found {_fmt(found_val, rule.unit)} in '{source_doc}' (page {source_page}), "
            f"which does NOT meet the requirement {rule.operator} {_fmt(required, rule.unit)}. "
            + ("This is a MANDATORY criterion — bidder is disqualified." if rule.mandatory
               else "This is an optional criterion.")
        )
        needs_action = False

    return RuleResult(
        **base,
        found_value=found_val,
        found_raw=field_data.raw_text,
        verdict=verdict,
        confidence=conf,
        source_page=source_page,
        explanation=explanation,
        needs_officer_action=needs_action,
    )


def _fmt(val: float, unit: str) -> str:
    if unit in ("INR", "USD", "EUR"):
        if val >= 1e7:
            return f"Rs.{val/1e7:.2f} Cr" if unit == "INR" else f"${val/1e6:.2f}M"
        elif val >= 1e5:
            return f"Rs.{val/1e5:.2f} L" if unit == "INR" else f"${val/1000:.1f}K"
        else:
            return f"Rs.{val:,.0f}" if unit == "INR" else f"${val:,.0f}"
    return f"{val:,.1f} {unit or ''}".strip()


def _rule_description(rule: TenderRule) -> str:
    mandatory_tag = "[MANDATORY]" if rule.mandatory else "[OPTIONAL]"
    if rule.value is not None:
        return f"{mandatory_tag} {rule.label}: {rule.operator} {_fmt(rule.value, rule.unit or '')}"
    return f"{mandatory_tag} {rule.label}: must be present"


def _aggregate_verdict(results: List[RuleResult]) -> Verdict:
    verdicts = [r.verdict for r in results]
    if Verdict.NOT_ELIGIBLE in verdicts:
        return Verdict.NOT_ELIGIBLE
    if Verdict.MANUAL_REVIEW in verdicts:
        return Verdict.MANUAL_REVIEW
    return Verdict.ELIGIBLE


def _mandatory_verdict(results: List[RuleResult]) -> Verdict:
    """Compute verdict considering only mandatory rules."""
    mandatory = [r for r in results if r.rule_mandatory]
    if not mandatory:
        return Verdict.ELIGIBLE
    return _aggregate_verdict(mandatory)


def _build_audit_entry(
    rule: TenderRule,
    result: RuleResult,
    bidder: BidderData,
    ts: str,
) -> AuditEntry:
    return AuditEntry(
        timestamp=ts,
        bidder_id=bidder.bidder_id,
        bidder_name=bidder.bidder_name,
        rule_id=rule.id,
        rule_label=rule.label,
        rule_mandatory=rule.mandatory,
        verdict=result.verdict,
        confidence=result.confidence,
        found_value=str(result.found_value) if result.found_value is not None else result.found_raw,
        required_value=str(rule.value) if rule.value is not None else "present",
        source_document=result.source_document,
        source_page=result.source_page,
        decision_basis=result.explanation,
        automated=True,
    )


def evaluate_all(ruleset: TenderRuleSet, bidders: List[BidderData]) -> EvaluationReport:
    """Run full evaluation and return EvaluationReport."""
    approved_rules = [r for r in ruleset.rules if r.approved]
    bidder_results: List[BidderResult] = []
    audit_log: List[AuditEntry] = []

    for bidder in bidders:
        ts = datetime.now(timezone.utc).isoformat()
        rule_results = [_evaluate_rule(r, bidder) for r in approved_rules]

        # Build audit entries for every decision
        for rule, rr in zip(approved_rules, rule_results):
            audit_log.append(_build_audit_entry(rule, rr, bidder, ts))

        overall = _aggregate_verdict(rule_results)
        mandatory_v = _mandatory_verdict(rule_results)

        e = sum(1 for r in rule_results if r.verdict == Verdict.ELIGIBLE)
        ne = sum(1 for r in rule_results if r.verdict == Verdict.NOT_ELIGIBLE)
        mr = sum(1 for r in rule_results if r.verdict == Verdict.MANUAL_REVIEW)
        mf = sum(1 for r in rule_results if r.rule_mandatory and r.verdict == Verdict.NOT_ELIGIBLE)

        bidder_results.append(BidderResult(
            bidder_id=bidder.bidder_id,
            bidder_name=bidder.bidder_name,
            overall_verdict=overall,
            mandatory_verdict=mandatory_v,
            rule_results=rule_results,
            eligible_count=e,
            not_eligible_count=ne,
            manual_review_count=mr,
            mandatory_fail_count=mf,
        ))

    total = len(bidder_results)
    elig = sum(1 for b in bidder_results if b.overall_verdict == Verdict.ELIGIBLE)
    not_elig = sum(1 for b in bidder_results if b.overall_verdict == Verdict.NOT_ELIGIBLE)
    manual = sum(1 for b in bidder_results if b.overall_verdict == Verdict.MANUAL_REVIEW)

    all_confs = [r.confidence for br in bidder_results for r in br.rule_results]
    avg_conf = round(sum(all_confs) / len(all_confs), 4) if all_confs else 0.0

    return EvaluationReport(
        report_id=str(uuid.uuid4()),
        tender_id=ruleset.tender_id,
        tender_name=ruleset.tender_name,
        tender_ref=ruleset.tender_ref,
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_bidders=total,
        eligible_count=elig,
        not_eligible_count=not_elig,
        manual_review_count=manual,
        bidder_results=bidder_results,
        ai_confidence_avg=avg_conf,
        audit_log=audit_log,
    )
