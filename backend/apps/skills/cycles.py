"""Cycle-state maths — a faithful port of the source app's lib/cycles.ts.

Per-person view of the company review calendar. A cycle's state is the person's
submission status if one exists, otherwise derived from today vs. the cycle dates.
"""
from django.utils import timezone


def _sorted(cycles):
    return sorted(cycles, key=lambda c: c.period_start)


def active_index(cycles, today=None):
    """Index of the active cycle: running today, else the next to open, else the last."""
    today = today or timezone.localdate()
    s = _sorted(cycles)
    for i, c in enumerate(s):
        if c.period_start <= today <= c.closure_target:
            return i
    for i, c in enumerate(s):
        if today < c.period_start:
            return i
    return len(s) - 1 if s else -1


def active_cycle(cycles, today=None):
    s = _sorted(cycles)
    idx = active_index(s, today)
    return s[idx] if idx >= 0 else None


def cycles_for(cycles, subs_by_cycle_id, today=None):
    """Return a list of dicts describing each cycle's per-person state. Oldest first.

    subs_by_cycle_id: {cycle_id: submission_status}
    """
    today = today or timezone.localdate()
    s = _sorted(cycles)
    active = active_index(s, today)
    out = []
    for i, c in enumerate(s):
        sub = subs_by_cycle_id.get(c.cycle_id)
        if sub:
            state = sub
        elif today < c.period_start:
            state = 'upcoming'
        elif today > c.closure_target:
            state = 'missed'
        elif today > c.employee_due:
            state = 'overdue'
        else:
            state = 'open'
        out.append({
            'cycle_id': c.cycle_id,
            'period_start': c.period_start,
            'period_end': c.period_end,
            'employee_due': c.employee_due,
            'manager_due': c.manager_due,
            'closure_target': c.closure_target,
            'notes': c.notes,
            'state': state,
            'is_active': i == active,
        })
    return out


def compliance_of(cycles, subs_by_cycle_id, today=None):
    """One-word compliance summary: the active cycle's state for this person."""
    if not cycles:
        return 'no_cycle'
    rows = cycles_for(cycles, subs_by_cycle_id, today)
    for r in rows:
        if r['is_active']:
            return r['state']
    return 'no_cycle'
