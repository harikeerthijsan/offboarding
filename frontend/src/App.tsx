import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import MainLayout from './layouts/MainLayout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import EmployeesPage from './pages/EmployeesPage';
import EmployeeDetailPage from './pages/EmployeeDetailPage';
import EmployeeFormPage from './pages/EmployeeFormPage';
import OrganizationPage from './pages/OrganizationPage';
import OffboardingPage from './pages/OffboardingPage';
import ResignationCreatePage from './pages/ResignationCreatePage';
import ResignationDetailPage from './pages/ResignationDetailPage';
import NoticePeriodPage from './pages/NoticePeriodPage';
import KnowledgeTransferPage from './pages/KnowledgeTransferPage';
import MyKnowledgeTransferPage from './pages/MyKnowledgeTransferPage';
import ClearancePage from './pages/ClearancePage';
import ClearanceQueuePage from './pages/ClearanceQueuePage';
import AssetsPage from './pages/AssetsPage';
import SettlementPage from './pages/SettlementPage';
import ExitInterviewPage from './pages/ExitInterviewPage';
import HRDashboardPage from './pages/HRDashboardPage';
import FinalReviewPage from './pages/FinalReviewPage';
import DocumentsPage from './pages/DocumentsPage';
import NotificationCenterPage from './pages/NotificationCenterPage';
import OffboardingRequestsPage from './pages/OffboardingRequestsPage';
import ProfilePage from './pages/ProfilePage';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<MainLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/employees" element={<EmployeesPage />} />
              <Route path="/employees/create" element={<EmployeeFormPage />} />
              <Route path="/employees/:id" element={<EmployeeDetailPage />} />
              <Route path="/employees/:id/edit" element={<EmployeeFormPage />} />
              <Route path="/organization" element={<OrganizationPage />} />
              <Route path="/offboarding" element={<OffboardingPage />} />
              <Route path="/offboarding/create" element={<ResignationCreatePage />} />
              <Route path="/offboarding/requests" element={<OffboardingRequestsPage />} />
              <Route path="/offboarding/:id" element={<ResignationDetailPage />} />
              <Route path="/offboarding/:id/notice-period" element={<NoticePeriodPage />} />
              <Route path="/offboarding/:id/knowledge-transfer" element={<KnowledgeTransferPage />} />
              <Route path="/offboarding/:id/clearance" element={<ClearancePage />} />
              <Route path="/offboarding/:id/settlement" element={<SettlementPage />} />
              <Route path="/offboarding/:id/exit-interview" element={<ExitInterviewPage />} />
              <Route path="/offboarding/:id/final-review" element={<FinalReviewPage />} />
              <Route path="/offboarding/:id/documents" element={<DocumentsPage />} />
              <Route path="/notifications" element={<NotificationCenterPage />} />
              <Route path="/hr/offboarding" element={<HRDashboardPage />} />
              <Route path="/hr/offboarding/:id" element={<ResignationDetailPage />} />
              <Route path="/my-knowledge-transfer" element={<MyKnowledgeTransferPage />} />
              <Route path="/assets" element={<AssetsPage />} />
              <Route path="/clearances" element={<ClearanceQueuePage />} />
              <Route path="/profile" element={<ProfilePage />} />
            </Route>
          </Route>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
