import React from 'react';
import { useAdminSession } from '../../lib/adminSession';
import { ExecutiveCopilot } from './ExecutiveCopilot';

const Overview: React.FC = () => {
  const { session, dashboardBranchId } = useAdminSession();
  const branches = session.allowed_branches || [];
  const selectedBranch = dashboardBranchId || '';

  return (
    <main className="admin-dashboard-modern">
      <ExecutiveCopilot selectedBranchId={selectedBranch} branches={branches} />
    </main>
  );
};

export default Overview;
