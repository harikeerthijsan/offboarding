import api from './api';
import type { Employee, EmployeeListItem, Department, Designation, PaginatedResponse, EmployeeFilters } from '../types';

export const employeeService = {
  getEmployees: async (filters?: EmployeeFilters): Promise<PaginatedResponse<EmployeeListItem>> => {
    const { data } = await api.get<PaginatedResponse<EmployeeListItem>>('/employees/', { params: filters });
    return data;
  },

  getEmployee: async (id: number): Promise<Employee> => {
    const { data } = await api.get<Employee>(`/employees/${id}/`);
    return data;
  },

  getMyProfile: async (): Promise<Employee> => {
    const { data } = await api.get<Employee>('/employees/me/');
    return data;
  },

  updateMyProfile: async (payload: Record<string, unknown>): Promise<Employee> => {
    const { data } = await api.patch<Employee>('/employees/me/', payload);
    return data;
  },

  createEmployee: async (payload: Record<string, unknown>): Promise<Employee> => {
    const { data } = await api.post<Employee>('/employees/', payload);
    return data;
  },

  updateEmployee: async (id: number, payload: Record<string, unknown>): Promise<Employee> => {
    const { data } = await api.patch<Employee>(`/employees/${id}/`, payload);
    return data;
  },

  deleteEmployee: async (id: number): Promise<void> => {
    await api.delete(`/employees/${id}/`);
  },

  getReports: async (id: number): Promise<EmployeeListItem[]> => {
    const { data } = await api.get<EmployeeListItem[]>(`/employees/${id}/reports/`);
    return data;
  },

  getManager: async (id: number): Promise<Employee> => {
    const { data } = await api.get<Employee>(`/employees/${id}/manager/`);
    return data;
  },

  getDepartments: async (params?: { is_active?: boolean; page?: number }): Promise<PaginatedResponse<Department>> => {
    const { data } = await api.get<PaginatedResponse<Department>>('/employees/departments/', { params });
    return data;
  },

  createDepartment: async (payload: Partial<Department>): Promise<Department> => {
    const { data } = await api.post<Department>('/employees/departments/', payload);
    return data;
  },

  updateDepartment: async (id: number, payload: Partial<Department>): Promise<Department> => {
    const { data } = await api.patch<Department>(`/employees/departments/${id}/`, payload);
    return data;
  },

  getDepartmentEmployees: async (deptId: number): Promise<EmployeeListItem[]> => {
    const { data } = await api.get(`/employees/departments/${deptId}/employees/`);
    return data.results || data;
  },

  getDesignations: async (params?: { department?: number; is_active?: boolean; page?: number }): Promise<PaginatedResponse<Designation>> => {
    const { data } = await api.get<PaginatedResponse<Designation>>('/employees/designations/', { params });
    return data;
  },

  createDesignation: async (payload: Partial<Designation>): Promise<Designation> => {
    const { data } = await api.post<Designation>('/employees/designations/', payload);
    return data;
  },

  updateDesignation: async (id: number, payload: Partial<Designation>): Promise<Designation> => {
    const { data } = await api.patch<Designation>(`/employees/designations/${id}/`, payload);
    return data;
  },
};
