"""PDF generation for exit documents. Kept separate from API views.

All business dates rendered here come from stored, manually-entered values. This
module NEVER derives or defaults a date — callers pass what the database holds and
missing values render as "Not entered".
"""
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT


def _fmt_date(d):
    if not d:
        return 'Not entered'
    try:
        return d.strftime('%d %b %Y')
    except AttributeError:
        return str(d)


def _money(v):
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle('CompanyName', parent=ss['Title'], fontSize=18, spaceAfter=2))
    ss.add(ParagraphStyle('CompanyMeta', parent=ss['Normal'], fontSize=8,
                           textColor=colors.grey, alignment=TA_CENTER))
    ss.add(ParagraphStyle('DocTitle', parent=ss['Heading1'], fontSize=14,
                           alignment=TA_CENTER, spaceBefore=12, spaceAfter=12))
    ss.add(ParagraphStyle('RightMeta', parent=ss['Normal'], fontSize=9, alignment=TA_RIGHT))
    ss.add(ParagraphStyle('Body', parent=ss['Normal'], fontSize=10, leading=16, spaceAfter=8))
    ss.add(ParagraphStyle('SectionH', parent=ss['Heading2'], fontSize=11, spaceBefore=10, spaceAfter=4))
    return ss


def _header(story, ss, company):
    story.append(Paragraph(company.name or 'Company', ss['CompanyName']))
    meta_bits = [b for b in [company.address, company.email, company.phone] if b]
    if meta_bits:
        story.append(Paragraph(' · '.join(meta_bits), ss['CompanyMeta']))
    story.append(Spacer(1, 6 * mm))


def _signatory(story, ss, company):
    story.append(Spacer(1, 16 * mm))
    story.append(Paragraph('_______________________________', ss['Body']))
    story.append(Paragraph(company.signatory_name or 'Authorized Signatory', ss['Body']))
    if company.signatory_designation:
        story.append(Paragraph(company.signatory_designation, ss['Body']))
    story.append(Paragraph(company.name or 'Company', ss['Body']))


def _doc_meta(story, ss, doc):
    story.append(Paragraph(
        f"Document No: {doc.document_number}<br/>Date: {_fmt_date(doc.document_date)}",
        ss['RightMeta']))
    story.append(Spacer(1, 4 * mm))


def _build(build_fn):
    buf = BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=20 * mm, rightMargin=20 * mm)
    story = []
    build_fn(story)
    pdf.build(story)
    buf.seek(0)
    return buf.read()


# ─── generators ──────────────────────────────────────────────────────────────

def relieving_letter(doc, ctx, company):
    ss = _styles()

    def build(story):
        _header(story, ss, company)
        _doc_meta(story, ss, doc)
        story.append(Paragraph('RELIEVING LETTER', ss['DocTitle']))
        story.append(Paragraph(f"This is to certify that <b>{ctx['name']}</b> "
                               f"(Employee ID: {ctx['employee_id']}), who was employed with "
                               f"{company.name or 'the company'} as <b>{ctx['designation']}</b> "
                               f"in the {ctx['department']} department, has been relieved from "
                               f"their duties.", ss['Body']))
        story.append(Paragraph(f"Date of Joining: {_fmt_date(ctx['joining_date'])}", ss['Body']))
        story.append(Paragraph(f"Last Working Day: {_fmt_date(ctx['last_working_day'])}", ss['Body']))
        story.append(Paragraph("We confirm that the employee has completed the required exit "
                               "formalities. We wish them success in their future endeavours.", ss['Body']))
        _signatory(story, ss, company)
    return _build(build)


def experience_letter(doc, ctx, company):
    ss = _styles()

    def build(story):
        _header(story, ss, company)
        _doc_meta(story, ss, doc)
        story.append(Paragraph('EXPERIENCE CERTIFICATE', ss['DocTitle']))
        story.append(Paragraph(f"This is to certify that <b>{ctx['name']}</b> "
                               f"(Employee ID: {ctx['employee_id']}) was employed with "
                               f"{company.name or 'the company'} as <b>{ctx['designation']}</b> "
                               f"in the {ctx['department']} department.", ss['Body']))
        story.append(Paragraph(f"Employment Type: {ctx['employment_type']}", ss['Body']))
        story.append(Paragraph(f"Date of Joining: {_fmt_date(ctx['joining_date'])}", ss['Body']))
        story.append(Paragraph(f"Last Working Day: {_fmt_date(ctx['last_working_day'])}", ss['Body']))
        story.append(Paragraph("During the tenure, the employee was found to be sincere, "
                               "hardworking and professional in their conduct.", ss['Body']))
        _signatory(story, ss, company)
    return _build(build)


def settlement_statement(doc, ctx, company):
    ss = _styles()
    s = ctx['settlement']

    def build(story):
        _header(story, ss, company)
        _doc_meta(story, ss, doc)
        story.append(Paragraph('FULL &amp; FINAL SETTLEMENT', ss['DocTitle']))
        story.append(Paragraph(f"Employee: <b>{ctx['name']}</b> ({ctx['employee_id']})", ss['Body']))
        story.append(Paragraph(f"Department: {ctx['department']} &nbsp;&nbsp; "
                               f"Designation: {ctx['designation']}", ss['Body']))

        rows = [['Earnings', 'Amount', 'Deductions', 'Amount'],
                ['Pending Salary', _money(s['pending_salary']), 'Notice Recovery', _money(s['notice_recovery'])],
                ['Leave Encashment', _money(s['leave_encashment']), 'Loan Deduction', _money(s['loan_deduction'])],
                ['Bonus', _money(s['bonus']), 'Advance Deduction', _money(s['advance_deduction'])],
                ['Incentives', _money(s['incentives']), 'Other Deductions', _money(s['other_deductions'])],
                ['Other Additions', _money(s['other_additions']), '', ''],
                ['Gross Amount', _money(s['gross_amount']), 'Total Deductions', _money(s['total_deductions'])]]
        t = Table(rows, colWidths=[45 * mm, 30 * mm, 45 * mm, 30 * mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        story.append(Spacer(1, 4 * mm))
        story.append(t)
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(f"<b>NET SETTLEMENT PAYABLE: {_money(s['net_settlement'])}</b>", ss['SectionH']))
        story.append(Paragraph(f"Settlement Date: {_fmt_date(s['settlement_date'])}", ss['Body']))
        _signatory(story, ss, company)
    return _build(build)


def clearance_certificate(doc, ctx, company):
    ss = _styles()

    def build(story):
        _header(story, ss, company)
        _doc_meta(story, ss, doc)
        story.append(Paragraph('EXIT CLEARANCE CERTIFICATE', ss['DocTitle']))
        story.append(Paragraph(f"Employee: <b>{ctx['name']}</b> ({ctx['employee_id']})", ss['Body']))
        story.append(Paragraph(f"Department: {ctx['department']} &nbsp;&nbsp; "
                               f"Manager: {ctx['manager'] or '—'}", ss['Body']))

        rows = [['Department', 'Status']]
        for label, st in ctx['clearances']:
            rows.append([label, st])
        t = Table(rows, colWidths=[80 * mm, 60 * mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        story.append(Spacer(1, 4 * mm))
        story.append(t)
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(f"Assets: {ctx['asset_summary']}", ss['Body']))
        story.append(Paragraph(f"Knowledge Transfer: {ctx['kt_summary']}", ss['Body']))
        story.append(Paragraph(f"<b>Final Clearance Status: {ctx['final_clearance_status']}</b>", ss['SectionH']))
        _signatory(story, ss, company)
    return _build(build)


GENERATORS = {
    'RELIEVING_LETTER': relieving_letter,
    'EXPERIENCE_LETTER': experience_letter,
    'FULL_FINAL_SETTLEMENT': settlement_statement,
    'EXIT_CLEARANCE': clearance_certificate,
}
