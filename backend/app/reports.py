"""PDF shortlist report (ReportLab) written to the file store."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.storage.files import reports_dir

NAVY, STEEL, GOLD = colors.HexColor("#0B1F3A"), colors.HexColor("#2F6690"), colors.HexColor("#C9A227")


def build_pdf(run_id: str, summary: dict, cards: list[dict], decisions: list[dict]) -> Path:
    path = reports_dir() / f"shortlist_{run_id}.pdf"
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=NAVY, fontSize=18, alignment=0)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=STEEL)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=8, leading=10)
    job = summary["job"]
    dec = {d["employee_id"]: d for d in decisions}
    story = [Paragraph("TalentFlow AI — Internal Shortlist Report", h1),
             Paragraph(f"<b>{job['title']}</b> · {job['job_id']} · {job['location']['city']} ({job['work_mode']}) · start {job['start_date']}", body),
             Paragraph(f"Generated {datetime.now():%d %b %Y %H:%M} · run {run_id}", small), Spacer(1, 6 * mm),
             Paragraph("Sourcing brief", h2), Paragraph(summary.get("sourcing_brief") or "-", body),
             Paragraph("Matching summary", h2), Paragraph(summary.get("swarm_summary") or "-", body)]
    f = summary.get("funnel") or {}
    story += [Paragraph("Funnel", h2), Paragraph(" → ".join(f"{k}: <b>{v}</b>" for k, v in f.items()), body)]
    fair = summary.get("fairness") or {}
    fair_txt = "; ".join(f"{a}: impact ratio {v['impact_ratio']} ({'pass' if v['pass'] else 'flag'})" for a, v in fair.get("attributes", {}).items())
    story += [Paragraph("Responsible AI", h2),
              Paragraph(f"Fairness (four-fifths rule): {fair_txt or 'insufficient group sizes'}"
                        f"{' · shortlist re-balanced' if fair.get('rebalanced') else ''}. Protected attributes were never used for scoring "
                        "or sent to the LLM; final decisions were made by a human reviewer.", body), Spacer(1, 4 * mm),
              Paragraph("Shortlist", h2)]
    rows = [["#", "Candidate", "Score", "Skill", "Avail.", "Loc.", "P(succ)", "Decision"]]
    for c in cards:
        comp = c["components"]
        d = dec.get(c["employee_id"], {})
        rows.append([c["rank"], Paragraph(f"<b>{c['name']}</b><br/>{c['title']} · {c['city']}"
                                          f"{'<br/><font color=#C9A227>Hidden fit</font>' if c['hidden_fit'] else ''}", small),
                     f"{c['score']:.1f}", f"{comp['skill']:.2f}", f"{comp['availability']:.2f}", f"{comp['location']:.2f}",
                     f"{comp['success']:.2f}", Paragraph(f"{d.get('decision', 'pending')}<br/>{d.get('reason') or ''}", small)])
    t = Table(rows, colWidths=[8 * mm, 58 * mm, 14 * mm, 13 * mm, 13 * mm, 12 * mm, 15 * mm, 42 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F9")]),
                           ("LINEBELOW", (0, 0), (-1, 0), 1.2, GOLD), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1"))]))
    story.append(t)
    story += [Spacer(1, 4 * mm), Paragraph("Match explanations", h2)]
    for c in cards:
        story.append(Paragraph(f"<b>{c['rank']}. {c['name']}</b> — {c['headline'].rstrip('.')}: {c['narrative']}", small))
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                      title=f"Shortlist {job['job_id']}").build(story)
    return path
