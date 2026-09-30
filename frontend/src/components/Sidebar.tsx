import { NavLink } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import type { UserRole } from '../types';
import Icon, { type IconName } from './Icon';

interface NavItem {
  path: string;
  label: string;
  icon: IconName;
  roles: UserRole[];
}

const ALL_NAV_ITEMS: NavItem[] = [
  {
    path: '/dashboard',
    label: 'Dashboard',
    icon: 'grid',
    roles: ['EMPLOYEE', 'MANAGER', 'HR', 'IT', 'FINANCE', 'ADMIN'],
  },
  {
    path: '/employees',
    label: 'Employees',
    icon: 'users',
    roles: ['MANAGER', 'HR', 'IT', 'FINANCE', 'ADMIN'],
  },
  {
    path: '/organization',
    label: 'Organization',
    icon: 'building',
    roles: ['MANAGER', 'HR', 'IT', 'FINANCE', 'ADMIN'],
  },
  {
    path: '/offboarding',
    label: 'Resignation',
    icon: 'clipboard',
    roles: ['EMPLOYEE', 'MANAGER', 'HR', 'ADMIN'],
  },
  {
    path: '/hr/offboarding',
    label: 'HR Dashboard',
    icon: 'bar-chart',
    roles: ['HR', 'ADMIN'],
  },
  {
    path: '/my-knowledge-transfer',
    label: 'My Knowledge Transfer',
    icon: 'refresh',
    roles: ['EMPLOYEE', 'MANAGER', 'HR', 'ADMIN'],
  },
  {
    path: '/clearances',
    label: 'Clearances',
    icon: 'shield',
    roles: ['IT', 'FINANCE', 'HR', 'ADMIN', 'MANAGER'],
  },
  {
    path: '/assets',
    label: 'Assets',
    icon: 'laptop',
    roles: ['EMPLOYEE', 'MANAGER', 'HR', 'IT', 'FINANCE', 'ADMIN'],
  },
  {
    path: '/notifications',
    label: 'Notifications',
    icon: 'bell',
    roles: ['EMPLOYEE', 'MANAGER', 'HR', 'IT', 'FINANCE', 'ADMIN'],
  },
  {
    path: '/profile',
    label: 'My Profile',
    icon: 'user',
    roles: ['EMPLOYEE', 'MANAGER', 'HR', 'IT', 'FINANCE', 'ADMIN'],
  },
];

function getRoleBadgeClass(role: UserRole): string {
  const map: Record<UserRole, string> = {
    EMPLOYEE: 'badge badge-employee',
    MANAGER: 'badge badge-manager',
    HR: 'badge badge-hr',
    IT: 'badge badge-it',
    FINANCE: 'badge badge-finance',
    ADMIN: 'badge badge-admin',
  };
  return map[role] ?? 'badge';
}

function getInitials(firstName: string, lastName: string): string {
  return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
}

export default function Sidebar() {
  const { user } = useAuthContext();

  const visibleItems = ALL_NAV_ITEMS.filter(
    item => user && item.roles.includes(user.role)
  );

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <img src="/jsanlogo.png" alt="JSAN" className="sidebar-logo-img" />
        <span>Offboarding Management</span>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Navigation</div>
        {visibleItems.map(item => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <span className="nav-icon"><Icon name={item.icon} size={18} /></span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {user && (
        <div className="sidebar-footer">
          <div className="user-info">
            <div className="avatar">
              {getInitials(user.first_name || user.username, user.last_name || '')}
            </div>
            <div className="user-details">
              <div className="name">
                {user.first_name
                  ? `${user.first_name} ${user.last_name}`.trim()
                  : user.username}
              </div>
              <span className={getRoleBadgeClass(user.role)} style={{ marginTop: 2 }}>
                {user.role}
              </span>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
