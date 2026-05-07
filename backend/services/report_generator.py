"""
Stage 4 — Report Generator
Creates a styled PDF report from EvaluationReport using fpdf2.
Includes mandatory vs optional sections, audit log, and disclaimer.
"""
from datetime import datetime, timezone
from pathlib import Path
from fpdf import FPDF
from backend.models.evaluation import EvaluationReport, Verdict, AuditEntry
from backend.config import DATA_DIR


# ── Colour palette ────────────────────────────────────────────────────────────
_NAVY    = (0,   30,  64)
_GREEN   = (22,  101, 52)
_RED     = (153, 0,   10)
_AMBER   = (146, 64,  14)
_GREY    = (80,  80,  80)
_LGREY   = (130, 130, 130)
_BLUE_BG = (235, 240, 255)
_GREEN_BG= (236, 253, 245)
_RED_BG  = (255, 235, 235)
_AMBER_BG= (255, 251, 235)


class _TenderPDF(FPDF):
    def _safe_str(self, txt):
        if not txt: return txt
        t = str(txt)
        t = t.replace("—", "-").replace("→", "->").replace("⚠", "[!]")
        t = t.replace("–", "-").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        return t.encode("latin-1", "replace").decode("latin-1")

    def cell(self, *args, **kwargs):
        args = list(args)
        if len(args) >= 3 and isinstance(args[2], str):
            args[2] = self._safe_str(args[2])
        elif 'txt' in kwargs and isinstance(kwargs['txt'], str):
            kwargs['txt'] = self._safe_str(kwargs['txt'])
        return super().cell(*args, **kwargs)

    def multi_cell(self, *args, **kwargs):
        args = list(args)
        if len(args) >= 3 and isinstance(args[2], str):
            args[2] = self._safe_str(args[2])
        elif 'txt' in kwargs and isinstance(kwargs['txt'], str):
            kwargs['txt'] = self._safe_str(kwargs['txt'])
        return super().multi_cell(*args, **kwargs)

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*_NAVY)
        self.cell(0, 8, "TenderIQ — AI Bid Evaluation Report  |  CRPF Procurement", align="L")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*_LGREY)
        self.cell(0, 8,
                  f"Generated: {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}",
                  align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(180, 190, 210)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*_LGREY)
        self.cell(0, 8,
                  f"Page {self.page_no()} | CONFIDENTIAL — INTERNAL USE ONLY | TenderIQ v2.0",
                  align="C")


def _verdict_color(verdict: Verdict):
    if verdict == Verdict.ELIGIBLE:      return _GREEN
    if verdict == Verdict.NOT_ELIGIBLE:  return _RED
    return _AMBER


def _verdict_bg(verdict: Verdict):
    if verdict == Verdict.ELIGIBLE:      return _GREEN_BG
    if verdict == Verdict.NOT_ELIGIBLE:  return _RED_BG
    return _AMBER_BG


def _section_title(pdf: _TenderPDF, title: str):
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*_NAVY)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(180, 190, 210)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)


def _kv_row(pdf: _TenderPDF, label: str, value: str, bold_val: bool = False):
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_GREY)
    pdf.cell(70, 6, label + ":", new_x="RIGHT")
    pdf.set_font("Helvetica", "B" if bold_val else "", 10)
    pdf.set_text_color(*_NAVY)
    pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")


def generate_pdf_report(report: EvaluationReport) -> str:
    """Generate full evaluation PDF and return file path."""
    pdf = _TenderPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(10, 15, 10)
    pdf.add_page()

    # ── Cover / Title ─────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*_NAVY)
    pdf.cell(0, 14, "Final Evaluation Report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(*_GREY)
    pdf.cell(0, 7, f"Tender: {report.tender_name}  |  Ref: {report.tender_ref}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # ── Executive Summary ─────────────────────────────────────────────────────
    _section_title(pdf, "Executive Summary")
    _kv_row(pdf, "Report ID", report.report_id)
    _kv_row(pdf, "Total Bidders Evaluated", str(report.total_bidders))
    _kv_row(pdf, "Eligible", str(report.eligible_count), bold_val=True)
    _kv_row(pdf, "Not Eligible", str(report.not_eligible_count), bold_val=True)
    _kv_row(pdf, "Flagged for Manual Review", str(report.manual_review_count), bold_val=True)
    _kv_row(pdf, "AI Confidence (avg)", f"{report.ai_confidence_avg:.1%}")
    _kv_row(pdf, "Report Status",
            "FINALIZED" if report.finalized else "DRAFT — Pending Officer Sign-off")
    if report.finalized_at:
        _kv_row(pdf, "Finalized At", report.finalized_at[:19].replace("T", " ") + " UTC")
    pdf.ln(4)

    # ── Bidder Summary Table ──────────────────────────────────────────────────
    _section_title(pdf, "Bidder Summary")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*_GREY)
    pdf.set_fill_color(*_BLUE_BG)
    pdf.cell(60, 6, "Bidder Name", fill=True, border=1)
    pdf.cell(35, 6, "Overall", fill=True, border=1, align="C")
    pdf.cell(35, 6, "Mandatory Only", fill=True, border=1, align="C")
    pdf.cell(15, 6, "Pass", fill=True, border=1, align="C")
    pdf.cell(15, 6, "Fail", fill=True, border=1, align="C")
    pdf.cell(15, 6, "Review", fill=True, border=1, align="C")
    pdf.cell(0,  6, "Mand. Fail", fill=True, border=1, align="C", new_x="LMARGIN", new_y="NEXT")

    for br in report.bidder_results:
        vc = _verdict_color(br.overall_verdict)
        mvc = _verdict_color(br.mandatory_verdict)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(60, 5, br.bidder_name[:36], border=1)
        pdf.set_text_color(*vc)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(35, 5, br.overall_verdict.value, border=1, align="C")
        pdf.set_text_color(*mvc)
        pdf.cell(35, 5, br.mandatory_verdict.value, border=1, align="C")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(15, 5, str(br.eligible_count), border=1, align="C")
        pdf.cell(15, 5, str(br.not_eligible_count), border=1, align="C")
        pdf.cell(15, 5, str(br.manual_review_count), border=1, align="C")
        pdf.cell(0,  5, str(br.mandatory_fail_count), border=1, align="C",
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # ── Per-Bidder Detailed Pages ─────────────────────────────────────────────
    for br in report.bidder_results:
        pdf.add_page()

        # Bidder header
        vc = _verdict_color(br.overall_verdict)
        pdf.set_fill_color(*_verdict_bg(br.overall_verdict))
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*_NAVY)
        pdf.cell(0, 11, f"  {br.bidder_name}", fill=True, new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*vc)
        pdf.cell(0, 7, f"  Overall Verdict: {br.overall_verdict.value}    |    "
                       f"Mandatory-only Verdict: {br.mandatory_verdict.value}",
                 new_x="LMARGIN", new_y="NEXT")

        if br.officer_override:
            pdf.set_text_color(*_AMBER)
            pdf.cell(0, 6, f"  OFFICER OVERRIDE → {br.officer_override}   Note: {br.officer_override_note or ''}",
                     new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # ── Mandatory rules ──────────────────────────────────────────────────
        mandatory_rules = [r for r in br.rule_results if r.rule_mandatory]
        optional_rules  = [r for r in br.rule_results if not r.rule_mandatory]

        for section_label, rules_subset in [
            ("Mandatory Criteria", mandatory_rules),
            ("Optional / Desirable Criteria", optional_rules),
        ]:
            if not rules_subset:
                continue
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*_NAVY)
            pdf.cell(0, 7, section_label, new_x="LMARGIN", new_y="NEXT")

            # Table header
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*_GREY)
            pdf.set_fill_color(*_BLUE_BG)
            pdf.cell(65, 5, "Criterion", fill=True, border=1)
            pdf.cell(28, 5, "Verdict", fill=True, border=1, align="C")
            pdf.cell(28, 5, "Found", fill=True, border=1, align="C")
            pdf.cell(28, 5, "Required", fill=True, border=1, align="C")
            pdf.cell(20, 5, "Conf.", fill=True, border=1, align="C")
            pdf.cell(0,  5, "Source Doc", fill=True, border=1, align="C",
                     new_x="LMARGIN", new_y="NEXT")

            for rr in rules_subset:
                vc2 = _verdict_color(rr.verdict)
                pdf.set_font("Helvetica", "", 7)
                pdf.set_text_color(30, 30, 30)
                pdf.cell(65, 5, rr.rule_label[:42], border=1)
                pdf.set_text_color(*vc2)
                pdf.set_font("Helvetica", "B", 7)
                pdf.cell(28, 5, rr.verdict.value, border=1, align="C")
                pdf.set_font("Helvetica", "", 7)
                pdf.set_text_color(30, 30, 30)
                found_str = str(rr.found_value or rr.found_raw or "N/A")[:18]
                req_str   = str(rr.required_value or "Present")[:14]
                src_str   = (rr.source_document or "—")[:18]
                pdf.cell(28, 5, found_str, border=1, align="C")
                pdf.cell(28, 5, req_str,   border=1, align="C")
                pdf.cell(20, 5, f"{rr.confidence:.0%}", border=1, align="C")
                pdf.cell(0,  5, src_str,   border=1, align="C",
                         new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

        # ── AI Explanations ──────────────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*_NAVY)
        pdf.cell(0, 7, "AI Reasoning (Criterion-Level Explanations):", new_x="LMARGIN", new_y="NEXT")

        for rr in br.rule_results:
            m_tag = "[M]" if rr.rule_mandatory else "[O]"
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*_verdict_color(rr.verdict))
            pdf.cell(0, 5,
                     f"  {m_tag} [{rr.rule_id}] {rr.rule_label}  →  {rr.verdict.value}",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(*_GREY)
            pdf.multi_cell(0, 4, f"     {rr.explanation}", new_x="LMARGIN", new_y="NEXT")
            if rr.needs_officer_action:
                pdf.set_text_color(*_AMBER)
                pdf.cell(0, 4, "     ⚠ OFFICER ACTION REQUIRED",
                         new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(*_GREY)
        pdf.ln(3)

    # ── Audit Log ─────────────────────────────────────────────────────────────
    if report.audit_log:
        pdf.add_page()
        _section_title(pdf, "Audit Log — Complete Decision Trail")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_GREY)
        pdf.multi_cell(0, 5,
            "Every automated decision made by TenderIQ is recorded below. "
            "This log provides an immutable audit trail suitable for formal government "
            "procurement proceedings. [M] = Mandatory criterion, [O] = Optional.",
            new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # Audit table header
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(*_BLUE_BG)
        pdf.set_text_color(*_GREY)
        pdf.cell(40, 5, "Bidder",       fill=True, border=1)
        pdf.cell(6,  5, "T",            fill=True, border=1, align="C")  # M/O
        pdf.cell(38, 5, "Rule",         fill=True, border=1)
        pdf.cell(25, 5, "Verdict",      fill=True, border=1, align="C")
        pdf.cell(14, 5, "Conf.",        fill=True, border=1, align="C")
        pdf.cell(25, 5, "Found",        fill=True, border=1, align="C")
        pdf.cell(25, 5, "Required",     fill=True, border=1, align="C")
        pdf.cell(0,  5, "Source",       fill=True, border=1, align="C",
                 new_x="LMARGIN", new_y="NEXT")

        for entry in report.audit_log:
            vc = _verdict_color(entry.verdict)
            pdf.set_font("Helvetica", "", 6)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(40, 4, entry.bidder_name[:26], border=1)
            pdf.cell(6,  4, "M" if entry.rule_mandatory else "O", border=1, align="C")
            pdf.cell(38, 4, entry.rule_label[:26], border=1)
            pdf.set_text_color(*vc)
            pdf.set_font("Helvetica", "B", 6)
            pdf.cell(25, 4, entry.verdict.value, border=1, align="C")
            pdf.set_font("Helvetica", "", 6)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(14, 4, f"{entry.confidence:.0%}", border=1, align="C")
            pdf.cell(25, 4, (str(entry.found_value) or "—")[:16], border=1, align="C")
            pdf.cell(25, 4, (str(entry.required_value) or "—")[:16], border=1, align="C")
            pdf.cell(0,  4, (entry.source_document or "—")[:18], border=1, align="C",
                     new_x="LMARGIN", new_y="NEXT")

    # ── Disclaimer ────────────────────────────────────────────────────────────
    pdf.add_page()
    _section_title(pdf, "Disclaimer & Certification")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_GREY)
    pdf.multi_cell(0, 5,
        "DISCLAIMER: This report was generated by TenderIQ AI (v2.0). All AI decisions "
        "are advisory in nature. Final eligibility determination is the sole responsibility "
        "of the designated Procurement Officer. Cases flagged as MANUAL_REVIEW must be "
        "verified by a qualified human evaluator before any procurement decision is finalised.\n\n"
        "The audit log included in this report provides a complete, criterion-level record "
        "of every automated decision, including the source document, page number, extracted "
        "value, required threshold, and confidence score. This log is suitable for use in "
        "formal government procurement proceedings and Right-to-Information (RTI) responses.\n\n"
        "This document is CONFIDENTIAL. Unauthorised disclosure is prohibited.",
        new_x="LMARGIN", new_y="NEXT")

    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*_NAVY)
    pdf.cell(0, 7, "Procurement Officer Sign-off:", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(15)
    pdf.set_draw_color(*_NAVY)
    pdf.line(10, pdf.get_y(), 90, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_GREY)
    pdf.cell(0, 5, "Signature & Date", new_x="LMARGIN", new_y="NEXT")

    # Save
    out_path = DATA_DIR / "reports" / f"{report.report_id}.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return str(out_path)
