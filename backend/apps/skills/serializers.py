from rest_framework import serializers

from .models import SkillDefinition, ReviewCycle, SkillSubmission


def clean_skills(input_val):
    """Trust-boundary validation for a skills array (port of lib/skills.ts cleanSkills).
    Dedupes by name (case-insensitive), clamps lengths, normalizes years to 0.5 steps."""
    if not isinstance(input_val, list):
        return []
    seen, out = set(), []
    for raw in input_val:
        s = raw if isinstance(raw, dict) else {}
        name = str(s.get('name') or '').strip()[:80]
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)

        tools_raw = s.get('tools')
        if isinstance(tools_raw, list):
            tools_iter = tools_raw
        else:
            tools_iter = str(tools_raw or '').split(',')
        tools, tseen = [], set()
        for t in tools_iter:
            t = str(t).strip()[:60]
            if t and t.lower() not in tseen:
                tseen.add(t.lower())
                tools.append(t)
        tools = tools[:20]

        years = None
        yv = s.get('years')
        try:
            if yv not in (None, '', 'null'):
                years = max(0.0, min(50.0, round(float(yv) * 2) / 2))
        except (TypeError, ValueError):
            years = None

        out.append({
            'name': name,
            'category': (str(s.get('category') or '').strip()[:80]) or 'Technical',
            'status': (str(s.get('status') or '').strip()[:80]) or 'current',
            'proficiency': (str(s.get('proficiency') or '').strip()[:80]) or 'Intermediate',
            'tools': tools,
            'years': years,
            'company': str(s.get('company') or '').strip()[:120],
            'role': str(s.get('role') or '').strip()[:80],
            'customer': str(s.get('customer') or '').strip()[:200],
            'note': str(s.get('note') or '').strip()[:300],
        })
    return out


def _list_field(v, item_max=60, cap=30):
    items = v if isinstance(v, list) else str(v or '').split(',')
    out, seen = [], set()
    for t in items:
        t = str(t).strip()[:item_max]
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:cap]


class SkillDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillDefinition
        fields = ['id', 'name', 'tools', 'customers', 'active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        return ' '.join(str(value or '').split())[:80]

    def validate_tools(self, value):
        return _list_field(value)

    def validate_customers(self, value):
        return _list_field(value)


class ReviewCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewCycle
        fields = [
            'id', 'cycle_id', 'period_start', 'period_end',
            'employee_due', 'manager_due', 'closure_target', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SkillSubmissionSerializer(serializers.ModelSerializer):
    cycle_id = serializers.CharField(source='cycle.cycle_id', read_only=True)
    employee_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SkillSubmission
        fields = [
            'id', 'cycle_id', 'employee_name', 'due_date', 'skills', 'status',
            'employee_note', 'submitted_at', 'reviewed_by_name', 'reviewed_at',
            'review_note', 'source', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        u = obj.user
        return f"{u.first_name} {u.last_name}".strip() or u.username

    def get_reviewed_by_name(self, obj):
        u = obj.reviewed_by
        if not u:
            return None
        return f"{u.first_name} {u.last_name}".strip() or u.username
