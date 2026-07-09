import React from 'react';
import './Sidebar.css';

interface SidebarProps {
  children: React.ReactNode;
}

export const Sidebar = ({ children }: SidebarProps) => {
  return <aside className="ui-sidebar">{children}</aside>;
};

interface SidebarItemProps {
  icon?: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}

export const SidebarItem = ({ icon, label, active, onClick }: SidebarItemProps) => {
  return (
    <button className={`ui-sidebar-item ${active ? 'active' : ''}`} onClick={onClick}>
      {icon && <span className="ui-sidebar-item-icon">{icon}</span>}
      <span className="ui-sidebar-item-label">{label}</span>
    </button>
  );
};
