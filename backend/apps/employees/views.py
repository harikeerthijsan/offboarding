import csv

from django.db.models import Q
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin, IsHR, IsManager
from apps.audit.utils import log_action
from .models import Department, Designation, Employee
from .serializers import (
    DepartmentSerializer,
    DesignationSerializer,
    EmployeeCreateSerializer,
    EmployeeListSerializer,
    EmployeeSelfUpdateSerializer,
    EmployeeSerializer,
)


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.prefetch_related('employees').select_related('head').all()
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        return qs

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsHR()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        dept = serializer.save()
        log_action(self.request.user, 'DEPARTMENT_CREATED', dept, request=self.request)

    def perform_update(self, serializer):
        dept = serializer.save()
        log_action(self.request.user, 'DEPARTMENT_UPDATED', dept, request=self.request)

    @action(detail=True, methods=['get'], url_path='employees')
    def employees(self, request, pk=None):
        dept = self.get_object()
        employees = dept.employees.select_related('user', 'department', 'designation', 'manager').all()
        search = request.query_params.get('search', '').strip()
        if search:
            employees = employees.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search)
            )
        page = self.paginate_queryset(employees)
        if page is not None:
            serializer = EmployeeListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = EmployeeListSerializer(employees, many=True)
        return Response(serializer.data)


class DesignationViewSet(viewsets.ModelViewSet):
    queryset = Designation.objects.select_related('department').all()
    serializer_class = DesignationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        dept_id = self.request.query_params.get('department')
        is_active = self.request.query_params.get('is_active')
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        return qs

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsHR()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        des = serializer.save()
        log_action(self.request.user, 'DESIGNATION_CREATED', des, request=self.request)

    def perform_update(self, serializer):
        des = serializer.save()
        log_action(self.request.user, 'DESIGNATION_UPDATED', des, request=self.request)


VALID_ORDERINGS = {
    'employee_id': 'employee_id',
    '-employee_id': '-employee_id',
    'first_name': 'first_name',
    '-first_name': '-first_name',
    'last_name': 'last_name',
    '-last_name': '-last_name',
    'joining_date': 'joining_date',
    '-joining_date': '-joining_date',
    'employment_status': 'employment_status',
    '-employment_status': '-employment_status',
}


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related('user', 'department', 'designation', 'manager').all()

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(phone__icontains=search)
            )

        dept = params.get('department')
        if dept:
            qs = qs.filter(department_id=dept)

        desig = params.get('designation')
        if desig:
            qs = qs.filter(designation_id=desig)

        mgr = params.get('manager')
        if mgr:
            qs = qs.filter(manager_id=mgr)

        emp_type = params.get('employment_type')
        if emp_type:
            qs = qs.filter(employment_type=emp_type)

        emp_status = params.get('status')
        if emp_status:
            qs = qs.filter(employment_status=emp_status)

        location = params.get('location', '').strip()
        if location:
            qs = qs.filter(location__icontains=location)

        ordering = params.get('ordering', 'employee_id')
        qs = qs.order_by(VALID_ORDERINGS.get(ordering, 'employee_id'))
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return EmployeeListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return EmployeeCreateSerializer
        return EmployeeSerializer

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAdmin()]
        if self.action in ('create', 'update', 'partial_update'):
            return [IsHR()]
        if self.action in ('list', 'retrieve', 'export'):
            return [IsManager()]
        if self.action in ('me', 'reports', 'manager_info'):
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        log_action(request.user, 'EMPLOYEE_CREATED', employee, request=request)
        data = EmployeeSerializer(employee, context={'request': request}).data
        generated_password = getattr(employee, '_generated_password', None)
        if generated_password:
            data['temporary_password'] = generated_password
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        log_action(request.user, 'EMPLOYEE_UPDATED', employee, request=request)
        return Response(EmployeeSerializer(employee, context={'request': request}).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action(request.user, 'EMPLOYEE_DEACTIVATED', instance, request=request)
        instance.employment_status = 'EXITED'
        instance.save(update_fields=['employment_status', 'updated_at'])
        return Response({'detail': 'Employee deactivated.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """Stream a CSV of employees matching the current filters (status, search,
        department, etc.) — same filtering as the list view. e.g.
        /api/employees/export/?status=ACTIVE

        Columns:
          * Personal details for every employee (blank fields render as '-').
          * Sensitive statutory/bank columns only for HR/ADMIN exporters.
          * Each employee's latest submitted skills.
          * Offboarding columns (exit date, exit interview, clearances) only when
            NOT exporting Active-only, and dashed out for any Active employee.
        """
        from apps.offboarding.models import ExitInterview, ResignationRequest, DepartmentClearance
        from apps.skills.models import SkillSubmission

        qs = list(self.get_queryset())
        status_filter = (request.query_params.get('status') or '').upper()
        status_label = status_filter.lower() or 'all'
        active_only = status_filter == 'ACTIVE'
        include_sensitive = request.user.role in ('HR', 'ADMIN')

        def d(v):
            """Render a cell: non-empty value, else a '-' dash."""
            s = '' if v is None else str(v).strip()
            return s if s else '-'

        # user_id -> latest submitted/saved skills (most recent submission wins)
        latest_sub = {}
        user_ids = [e.user_id for e in qs if e.user_id]
        for s in SkillSubmission.objects.filter(user_id__in=user_ids).order_by('updated_at'):
            latest_sub[s.user_id] = s

        def skills_cell(employee):
            sub = latest_sub.get(employee.user_id)
            if not sub or not sub.skills:
                return '-'
            parts = []
            for sk in sub.skills:
                name = str(sk.get('name') or '').strip()
                if not name:
                    continue
                extra = []
                if sk.get('proficiency'):
                    extra.append(str(sk['proficiency']))
                yrs = sk.get('years')
                if yrs not in (None, '', 0):
                    extra.append(f"{yrs}y")
                parts.append(f"{name} ({', '.join(extra)})" if extra else name)
            return '; '.join(parts) or '-'

        # ─ offboarding data (only needed when offboarding columns are shown) ─
        ei_map, latest_offboarding, dc_map = {}, {}, {}
        if not active_only:
            ei_map = {ei.employee_id: ei.get_status_display() for ei in ExitInterview.objects.all()}
            for r in (ResignationRequest.objects.filter(employee__in=qs)
                      .select_related('notice_period').order_by('employee_id', '-created_at')):
                latest_offboarding.setdefault(r.employee_id, r)
            res_ids = [r.id for r in latest_offboarding.values()]
            for dc in DepartmentClearance.objects.filter(offboarding_request_id__in=res_ids):
                dc_map.setdefault(dc.offboarding_request_id, {})[dc.department] = dc.get_status_display()

        def exit_date(employee):
            off = latest_offboarding.get(employee.id)
            if not off:
                return ''
            np = getattr(off, 'notice_period', None)
            dd = (getattr(np, 'actual_last_working_day', None)
                  or getattr(np, 'expected_last_working_day', None)
                  or off.last_working_date)
            return dd.isoformat() if dd else ''

        def offboarding_cells(employee):
            # Active employees have no offboarding context -> all dashes.
            if employee.employment_status == 'ACTIVE':
                return ['-'] * 9
            off = latest_offboarding.get(employee.id)
            if not off:
                return ['-'] * 9
            depts = dc_map.get(off.id, {})
            return [
                d(exit_date(employee)),
                d(ei_map.get(employee.id)),
                'Completed' if off.kt_completed_at else 'Pending',
                d(depts.get('IT')), d(depts.get('FINANCE')), d(depts.get('HR')),
                d(depts.get('ADMIN')), d(depts.get('MANAGER')),
                'Completed' if off.clearance_completed_at else 'Pending',
            ]

        headers = ['Employee ID', 'Name', 'Email', 'Phone', 'Date of Birth', 'Gender',
                   'Department', 'Designation', 'Manager', 'Employment Type', 'Status',
                   'Location', 'Address', 'Emergency Contact Name', 'Emergency Contact Phone']
        if include_sensitive:
            headers += ['Aadhaar Number', 'PAN Number', 'UAN Number', 'ESI Number',
                        'Bank Name', 'Bank Account Holder', 'Bank Account Number', 'Bank IFSC']
        headers += ['Joining Date', 'Skills']
        if not active_only:
            headers += ['Exit Date', 'Exit Interview', 'Knowledge Transfer',
                        'IT Clearance', 'Finance Clearance', 'HR Clearance',
                        'Admin Clearance', 'Manager Clearance', 'Overall Clearance']

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="employees_{status_label}.csv"'
        writer = csv.writer(response)
        writer.writerow(headers)
        for e in qs:
            row = [
                d(e.employee_id),
                d(f"{e.first_name} {e.last_name}".strip()),
                d(e.email),
                d(e.phone),
                d(e.date_of_birth.isoformat() if e.date_of_birth else ''),
                d(e.get_gender_display() if e.gender else ''),
                d(e.department.name if e.department else ''),
                d(e.designation.name if e.designation else ''),
                d(f"{e.manager.first_name} {e.manager.last_name}".strip() if e.manager else ''),
                d(e.get_employment_type_display() if e.employment_type else ''),
                d(e.get_employment_status_display()),
                d(e.location),
                d(e.address),
                d(e.emergency_contact_name),
                d(e.emergency_contact_phone),
            ]
            if include_sensitive:
                row += [
                    d(e.aadhaar_number), d(e.pan_number), d(e.uan_number), d(e.esi_number),
                    d(e.bank_name), d(e.bank_account_holder_name),
                    d(e.bank_account_number), d(e.bank_ifsc_code),
                ]
            row += [d(e.joining_date.isoformat() if e.joining_date else ''), skills_cell(e)]
            if not active_only:
                row += offboarding_cells(e)
            writer.writerow(row)
        return response

    @action(detail=False, methods=['get', 'patch'], url_path='me')
    def me(self, request):
        try:
            employee = Employee.objects.select_related('user', 'department', 'designation', 'manager').get(user=request.user)
        except Employee.DoesNotExist:
            return Response({'detail': 'No employee profile found.'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'PATCH':
            serializer = EmployeeSelfUpdateSerializer(
                employee, data=request.data, partial=True, context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            employee = serializer.save()
            log_action(request.user, 'EMPLOYEE_UPDATED', employee, request=request)
            return Response(serializer.data)

        return Response(EmployeeSerializer(employee).data)

    @action(detail=True, methods=['get'], url_path='reports')
    def reports(self, request, pk=None):
        employee = self.get_object()
        reports = employee.direct_reports.select_related('user', 'department', 'designation').all()
        serializer = EmployeeListSerializer(reports, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='manager')
    def manager_info(self, request, pk=None):
        employee = self.get_object()
        if not employee.manager:
            return Response({'detail': 'No manager assigned.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(EmployeeSerializer(employee.manager).data)
