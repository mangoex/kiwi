import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@restaurantos/api-client';
import { CalendarDays, Clock3, Search } from 'lucide-react';

import { usePosSession } from '../../session';

interface AttendanceRow {
  id: string;
  employee_code_snapshot: string;
  employee_name_snapshot: string;
  subject_type: 'user' | 'driver';
  branch_id: string;
  branch_name: string;
  branch_timezone: string;
  local_date: string;
  checked_at: string;
  display_state: 'single' | 'entry' | 'exit';
}

interface Branch {
  id: string;
  name: string;
  status: string;
}

const statePresentation = {
  single: { label: 'Una checada', color: '#2563eb', background: '#dbeafe' },
  entry: { label: 'Entrada', color: '#15803d', background: '#dcfce7' },
  exit: { label: 'Salida', color: '#b91c1c', background: '#fee2e2' },
};

const isoUtc = (value: string) => /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`;

const AttendanceReport: React.FC = () => {
  const { session } = usePosSession();
  const activeBranch = session?.active_branch;
  const organizationScope = session?.scope.level === 'organization';
  const initialDay = useMemo(() => new Intl.DateTimeFormat('en-CA', {
    timeZone: activeBranch?.timezone,
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date()), [activeBranch?.timezone]);
  const [employeeCode, setEmployeeCode] = useState('');
  const [day, setDay] = useState(initialDay);
  const [month, setMonth] = useState('');
  const [branchId, setBranchId] = useState(organizationScope ? '' : activeBranch?.id || '');

  const branchesQuery = useQuery<Branch[]>({
    queryKey: ['attendance-branches'],
    queryFn: () => fetchApi('/branches'),
    enabled: organizationScope,
  });

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    if (/^[A-Z0-9]{6}$/.test(employeeCode.trim())) params.set('employee_code', employeeCode.trim());
    if (day) params.set('day', day);
    if (month) params.set('month', month);
    if (branchId) params.set('branch_id', branchId);
    return params.toString();
  }, [branchId, day, employeeCode, month]);

  const attendanceQuery = useQuery<AttendanceRow[]>({
    queryKey: ['attendance-report', queryString],
    queryFn: () => fetchApi(`/attendance/checks${queryString ? `?${queryString}` : ''}`),
    enabled: Boolean(activeBranch?.id),
  });

  const branches = organizationScope
    ? (branchesQuery.data || []).filter((branch) => branch.status === 'active')
    : activeBranch ? [{ id: activeBranch.id, name: activeBranch.name, status: activeBranch.status }] : [];

  return (
    <div style={{ padding: 32, maxWidth: 1280, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 24 }}>
        <span style={{ display: 'grid', placeItems: 'center', width: 52, height: 52, borderRadius: 15, color: '#047857', background: '#d1fae5' }}>
          <Clock3 size={28} />
        </span>
        <div>
          <h1 style={{ margin: 0, color: '#0f172a' }}>Reporte de checador</h1>
          <p style={{ margin: '5px 0 0', color: '#64748b' }}>Entradas y salidas registradas por el personal.</p>
        </div>
      </div>

      <section aria-label="Filtros del reporte" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 14, padding: 18, border: '1px solid #e2e8f0', borderRadius: 16, background: '#fff', marginBottom: 20 }}>
        <label style={{ display: 'grid', gap: 6, color: '#334155', fontSize: 13, fontWeight: 700 }}>
          Código del empleado
          <span style={{ position: 'relative' }}>
            <Search size={17} style={{ position: 'absolute', top: 11, left: 11, color: '#94a3b8' }} />
            <input value={employeeCode} maxLength={6} pattern="[A-Za-z0-9]{6}" onChange={(event) => setEmployeeCode(event.target.value.replace(/[^a-z0-9]/gi, '').toUpperCase())} placeholder="Ej. A7K204" style={{ width: '100%', boxSizing: 'border-box', minHeight: 40, padding: '0 10px 0 36px', border: '1px solid #cbd5e1', borderRadius: 9 }} />
          </span>
        </label>
        <label style={{ display: 'grid', gap: 6, color: '#334155', fontSize: 13, fontWeight: 700 }}>
          Día
          <input type="date" value={day} onChange={(event) => { setDay(event.target.value); if (event.target.value) setMonth(''); }} style={{ minHeight: 40, padding: '0 10px', border: '1px solid #cbd5e1', borderRadius: 9 }} />
        </label>
        <label style={{ display: 'grid', gap: 6, color: '#334155', fontSize: 13, fontWeight: 700 }}>
          Mes
          <input type="month" value={month} onChange={(event) => { setMonth(event.target.value); if (event.target.value) setDay(''); }} style={{ minHeight: 40, padding: '0 10px', border: '1px solid #cbd5e1', borderRadius: 9 }} />
        </label>
        <label style={{ display: 'grid', gap: 6, color: '#334155', fontSize: 13, fontWeight: 700 }}>
          Sucursal
          <select value={branchId} onChange={(event) => setBranchId(event.target.value)} disabled={!organizationScope} style={{ minHeight: 40, padding: '0 10px', border: '1px solid #cbd5e1', borderRadius: 9, background: '#fff' }}>
            {organizationScope && <option value="">Todas las sucursales</option>}
            {branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
          </select>
        </label>
      </section>

      <section style={{ border: '1px solid #e2e8f0', borderRadius: 16, background: '#fff', overflow: 'hidden' }}>
        {attendanceQuery.isLoading ? (
          <p style={{ padding: 32, margin: 0, color: '#64748b' }}>Cargando checadas…</p>
        ) : attendanceQuery.isError ? (
          <p role="alert" style={{ padding: 32, margin: 0, color: '#b91c1c' }}>No fue posible cargar el reporte.</p>
        ) : !attendanceQuery.data?.length ? (
          <div style={{ padding: 48, textAlign: 'center', color: '#64748b' }}>
            <CalendarDays size={38} style={{ marginBottom: 10, color: '#94a3b8' }} />
            <p style={{ margin: 0 }}>No hay checadas para los filtros seleccionados.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 820 }}>
              <thead style={{ background: '#f8fafc', color: '#475569', textAlign: 'left', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.04em' }}>
                <tr>
                  {['Estado', 'Empleado', 'Código', 'Tipo', 'Fecha', 'Hora', 'Sucursal'].map((label) => <th key={label} style={{ padding: '13px 16px', borderBottom: '1px solid #e2e8f0' }}>{label}</th>)}
                </tr>
              </thead>
              <tbody>
                {attendanceQuery.data.map((row) => {
                  const presentation = statePresentation[row.display_state];
                  const checkedAt = new Date(isoUtc(row.checked_at));
                  return (
                    <tr key={row.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '14px 16px' }}><span style={{ display: 'inline-flex', padding: '5px 9px', borderRadius: 999, color: presentation.color, background: presentation.background, fontSize: 12, fontWeight: 800 }}>{presentation.label}</span></td>
                      <td style={{ padding: '14px 16px', color: '#0f172a', fontWeight: 700 }}>{row.employee_name_snapshot}</td>
                      <td style={{ padding: '14px 16px', color: '#334155', fontFamily: 'ui-monospace, SFMono-Regular, monospace' }}>{row.employee_code_snapshot}</td>
                      <td style={{ padding: '14px 16px', color: '#64748b' }}>{row.subject_type === 'driver' ? 'Repartidor' : 'Usuario'}</td>
                      <td style={{ padding: '14px 16px', color: '#334155' }}>{new Intl.DateTimeFormat('es-MX', { timeZone: row.branch_timezone, dateStyle: 'medium' }).format(checkedAt)}</td>
                      <td style={{ padding: '14px 16px', color: presentation.color, fontWeight: 800, fontVariantNumeric: 'tabular-nums' }}>{new Intl.DateTimeFormat('es-MX', { timeZone: row.branch_timezone, timeStyle: 'medium' }).format(checkedAt)}</td>
                      <td style={{ padding: '14px 16px', color: '#334155' }}>{row.branch_name}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};

export default AttendanceReport;
