import React from 'react';
import { Sidebar, SidebarItem, Card, Button, Badge } from '@restaurantos/ui';
import { LayoutDashboard, Users, FileText, Settings, BarChart2, Bell, Search, Activity, DollarSign, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import './App.css';

const Overview = () => {
  return (
    <div className="admin-layout">
      {/* Admin Sidebar */}
      <Sidebar>
        <div style={{ padding: '12px 16px', fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-blue)', marginBottom: 24 }}>
          RestaurantOS
          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: 500 }}>ADMIN PANEL</div>
        </div>
        
        <SidebarItem icon={<LayoutDashboard size={20} />} label="Overview" active />
        <SidebarItem icon={<BarChart2 size={20} />} label="Analytics" />
        <SidebarItem icon={<Users size={20} />} label="Users" />
        <SidebarItem icon={<FileText size={20} />} label="Reports" />
        
        <div style={{ flex: 1 }} />
        
        <SidebarItem icon={<Settings size={20} />} label="Settings" />
      </Sidebar>

      <div className="admin-main">
        {/* Topbar */}
        <header className="admin-topbar">
          <div style={{ position: 'relative', width: '300px' }}>
            <Search size={18} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)' }} />
            <input 
              type="text" 
              placeholder="Search anything..." 
              style={{ width: '100%', padding: '10px 12px 10px 40px', borderRadius: 'var(--radius-full)', border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)', outline: 'none' }}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}><Bell size={20} /></button>
            <div style={{ width: 36, height: 36, borderRadius: '50%', backgroundColor: 'var(--color-blue-light)', color: 'var(--color-blue)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600 }}>MG</div>
          </div>
        </header>

        {/* Main Content */}
        <div className="admin-content">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
            <h1 className="admin-title" style={{ marginBottom: 0 }}>Dashboard Overview</h1>
            <Button variant="primary">Download Report</Button>
          </div>

          <div className="admin-metrics-grid">
            <Card className="admin-metric-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div className="admin-metric-title">Total Revenue</div>
                <div style={{ padding: 8, backgroundColor: 'var(--color-blue-light)', borderRadius: 'var(--radius-sm)', color: 'var(--color-blue)' }}><DollarSign size={20} /></div>
              </div>
              <div className="admin-metric-value">
                Rp 24.5M
                <span className="admin-metric-trend up"><ArrowUpRight size={16} /> 12.5%</span>
              </div>
            </Card>
            
            <Card className="admin-metric-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div className="admin-metric-title">Total Orders</div>
                <div style={{ padding: 8, backgroundColor: 'var(--color-orange-light)', borderRadius: 'var(--radius-sm)', color: 'var(--color-orange)' }}><Activity size={20} /></div>
              </div>
              <div className="admin-metric-value">
                1,245
                <span className="admin-metric-trend up"><ArrowUpRight size={16} /> 8.2%</span>
              </div>
            </Card>

            <Card className="admin-metric-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div className="admin-metric-title">Active Customers</div>
                <div style={{ padding: 8, backgroundColor: 'var(--color-green-light)', borderRadius: 'var(--radius-sm)', color: 'var(--color-green)' }}><Users size={20} /></div>
              </div>
              <div className="admin-metric-value">
                892
                <span className="admin-metric-trend down"><ArrowDownRight size={16} /> 2.4%</span>
              </div>
            </Card>
          </div>

          <div className="admin-charts-area">
            <Card style={{ padding: 24 }}>
              <h3 style={{ marginBottom: 16 }}>Revenue Overview</h3>
              <div className="admin-chart-placeholder">Chart Area Placeholder</div>
            </Card>
            <Card style={{ padding: 24 }}>
              <h3 style={{ marginBottom: 16 }}>Recent Activity</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {[1,2,3,4].map(i => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: 'var(--color-blue)' }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.875rem', fontWeight: 500 }}>New order #100{i}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>2 mins ago</div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Overview;
