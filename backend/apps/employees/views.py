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
        return Response(
            EmployeeSerializer(employee, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

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
        /api/employees/export/?status=ACTIVE"""
        from apps.offboarding.models import ExitInterview
        qs = self.get_queryset()
        status_label = (request.query_params.get('status') or 'all').lower()

        # employee_id -> exit interview status (single query)
        ei_map = {ei.employee_id: ei.get_status_display()
                  for ei in ExitInterview.objects.all()}

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="employees_{status_label}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Employee ID', 'Name', 'Email', 'Department', 'Designation',
                         'Manager', 'Status', 'Joining Date', 'Exit Interview'])
        for e in qs:
            writer.writerow([
                e.employee_id,
                f"{e.first_name} {e.last_name}".strip(),
                e.email,
                e.department.name if e.department else '',
                e.designation.name if e.designation else '',
                f"{e.manager.first_name} {e.manager.last_name}".strip() if e.manager else '',
                e.get_employment_status_display(),
                e.joining_date.isoformat() if e.joining_date else '',
                ei_map.get(e.id, 'Not Started'),
            ])
        return response

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        try:
            employee = Employee.objects.select_related('user', 'department', 'designation', 'manager').get(user=request.user)
            return Response(EmployeeSerializer(employee).data)
        except Employee.DoesNotExist:
            return Response({'detail': 'No employee profile found.'}, status=status.HTTP_404_NOT_FOUND)

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
