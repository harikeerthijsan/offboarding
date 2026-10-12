import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import { authService } from '../services/authService';
import type { UserRole } from '../types';
import Icon, { type IconName } from './Icon';

interface NavItem {
  path: string;
  label: string;
  icon: IconName;
  roles: UserRole[];
  children?: NavItem[];
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
    children: [
      {
        path: '/my-knowledge-transfer',
        label: 'Knowledge Transfer',
        icon: 'refresh',
        roles: ['EMPLOYEE', 'MANAGER', 'HR', 'ADMIN'],
      },
    ],
  },
  {
    path: '/hr/offboarding',
    label: 'HR Dashboard',
    icon: 'bar-chart',
    roles: ['HR', 'ADMIN'],
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
    path: '/policies',
    label: 'Policies',
    icon: 'book',
    roles: ['EMPLOYEE', 'MANAGER', 'HR', 'IT', 'FINANCE', 'ADMIN'],
  },
  {
    path: '/notifications',
    label: 'Notifications',
    icon: 'bell',
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
  const [ssoBusy, setSsoBusy] = useState(false);

  const openSkillHub = async () => {
    if (ssoBusy) return;
    setSsoBusy(true);
    try {
      const { redirect_url } = await authService.skillHubSSO();
      // Full navigation so the Skills Hub can set its own session cookie.
      window.location.assign(redirect_url);
    } catch {
      setSsoBusy(false);
      alert('Skills Hub is not available right now. Please try again later.');
    }
  };

  const visibleItems = ALL_NAV_ITEMS.filter(
    item => user && item.roles.includes(user.role)
  );

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <img src="/jsanlogo.png" alt="JSAN" className="sidebar-logo-img" />
        <span>JSAN PEOPLE360</span>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Navigation</div>
        {visibleItems.map(item => {
          const children = (item.children || []).filter(c => user && c.roles.includes(user.role));
          return (
            <div key={item.path}>
              <NavLink
                to={item.path}
                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              >
                <span className="nav-icon"><Icon name={item.icon} size={18} /></span>
                <span>{item.label}</span>
              </NavLink>
              {children.map(child => (
                <NavLink
                  key={child.path}
                  to={child.path}
                  className={({ isActive }) => `nav-link nav-sublink${isActive ? ' active' : ''}`}
                >
                  <span className="nav-icon"><Icon name={child.icon} size={16} /></span>
                  <span>{child.label}</span>
                </NavLink>
              ))}
            </div>
          );
        })}

        {/* External app — single sign-on handoff to the JSAN Skills Hub */}
        <button
          type="button"
          className="nav-link nav-link-external"
          onClick={openSkillHub}
          disabled={ssoBusy}
          title="Open the JSAN Skills Hub (single sign-on)"
        >
          <span className="nav-icon"><Icon name="bar-chart" size={18} /></span>
          <span>Skills Hub</span>
          {ssoBusy
            ? <span className="btn-spinner" style={{ marginLeft: 'auto' }} />
            : <span className="nav-external-mark" aria-hidden="true">↗</span>}
        </button>
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
