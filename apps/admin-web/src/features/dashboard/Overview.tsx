import React from 'react';
import { Card, Button } from '@restaurantos/ui';
import { Activity, DollarSign, ArrowUpRight, ArrowDownRight, Users } from 'lucide-react';

const Overview = () => {
  return (
    <>
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
    </>
  );
};

export default Overview;
