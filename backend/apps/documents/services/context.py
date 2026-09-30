"""Builds document rendering context from stored data and validates prerequisites.

Raises ValueError(message) when required stored information is missing — the caller
turns that into a 400. Nothing here invents or defaults a business date.
"""
from django.core.exceptions import ObjectDoesNotExist


def _one2one(obj, attr):
    try:
        return getattr(obj, attr)
    except ObjectDoesNotExist:
        return None


def _employee_ctx(emp):
    return {
        'name': f"{emp.first_name} {emp.last_name}",
        'employee_id': emp.employee_id,
        'designation': emp.designation.name if emp.designation else '—',
        'department': emp.department.name if emp.department else '—',
        'joining_date': emp.joining_date,
        'employment_type': emp.get_employment_type_display(),
        'manager': f"{emp.manager.first_name} {emp.manager.last_name}" if emp.manager else None,
    }


def _last_working_day(resignation):
    """Prefer the actual LWD recorded on the notice period; fall back to the
    manually-entered last_working_date on the resignation. Never derived."""
    np = _one2one(resignation, 'notice_period')
    if np and np.actual_last_working_day:
        return np.actual_last_working_day
    return resignation.last_working_date


def build_context(resignation, document_type):
    emp = resignation.employee
    ctx = _employee_ctx(emp)

    if document_type in ('RELIEVING_LETTER', 'EXPERIENCE_LETTER'):
        lwd = _last_working_day(resignation)
        if not lwd:
            raise ValueError('Last working day has not been entered yet; cannot generate this document.')
        ctx['last_working_day'] = lwd
        return ctx

    if document_type == 'FULL_FINAL_SETTLEMENT':
        fs = _one2one(resignation, 'final_settlement')
        if not fs:
            raise ValueError('No final settlement exists for this offboarding.')
        if fs.settlement_status != 'APPROVED':
            raise ValueError('The final settlement must be APPROVED before generating the statement.')
        ctx['settlement'] = {
            'pending_salary': fs.pending_salary, 'leave_encashment': fs.leave_encashment,
            'bonus': fs.bonus, 'incentives': fs.incentives, 'other_additions': fs.other_additions,
            'notice_recovery': fs.notice_recovery, 'loan_deduction': fs.loan_deduction,
            'advance_deduction': fs.advance_deduction, 'other_deductions': fs.other_deductions,
            'gross_amount': fs.gross_amount, 'total_deductions': fs.total_deductions,
            'net_settlement': fs.net_settlement, 'settlement_date': fs.settlement_date,
        }
        return ctx

    if document_type == 'EXIT_CLEARANCE':
        depts = list(resignation.department_clearances.all())
        clearances = [(dc.get_department_display(), dc.get_status_display()) for dc in depts]
        if not clearances:
            clearances = [('No department clearances recorded', '—')]
        assets = resignation.asset_clearances.all()
        total_assets = assets.count()
        cleared_assets = assets.filter(status__in=['CLEARED', 'LOST', 'DAMAGED']).count()
        ctx['clearances'] = clearances
        ctx['asset_summary'] = f"{cleared_assets}/{total_assets} resolved" if total_assets else 'No assets'
        kt_total = resignation.kt_items.count()
        kt_done = resignation.kt_items.filter(status='COMPLETED').count()
        ctx['kt_summary'] = f"{kt_done}/{kt_total} completed" if kt_total else 'No KT tasks'
        ctx['final_clearance_status'] = (
            'CLEARED' if resignation.clearance_completed_at is not None else 'PENDING')
        return ctx

    # OTHER — minimal context
    ctx['last_working_day'] = _last_working_day(resignation)
    return ctx
