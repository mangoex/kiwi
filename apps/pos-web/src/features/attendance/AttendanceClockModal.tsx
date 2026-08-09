import React, { FormEvent, useEffect, useRef, useState } from 'react';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { CheckCircle2, Clock3, KeyRound, X } from 'lucide-react';

import { usePosSession } from '../../session';

interface AttendanceResult {
  id: string;
  employee_name_snapshot: string;
  daily_sequence: 1 | 2;
  checked_at: string;
}

interface AttendanceClockModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const errorMessage = (reason: unknown) => {
  if (!(reason instanceof ApiError)) return 'No fue posible registrar la checada.';
  if (reason.code === 'employee_code_invalid') {
    return 'La clave no existe o el empleado no está activo.';
  }
  if (reason.code === 'attendance_daily_limit_reached') {
    return 'La entrada y la salida de hoy ya fueron registradas.';
  }
  if (reason.code === 'employee_code_required') return 'Captura la clave del empleado.';
  if (reason.code === 'employee_code_invalid_format') {
    return 'La clave debe tener exactamente 6 caracteres alfanuméricos.';
  }
  return reason.message;
};

const AttendanceClockModal: React.FC<AttendanceClockModalProps> = ({ isOpen, onClose }) => {
  const { session } = usePosSession();
  const [now, setNow] = useState(new Date());
  const [employeeCode, setEmployeeCode] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<AttendanceResult | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isOpen) return undefined;
    setNow(new Date());
    setEmployeeCode('');
    setError('');
    setResult(null);
    const interval = window.setInterval(() => setNow(new Date()), 1000);
    window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearInterval(interval);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isSubmitting) onClose();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [isOpen, isSubmitting, onClose]);

  if (!isOpen) return null;

  const timezone = session?.active_branch?.timezone;
  const formattedTime = new Intl.DateTimeFormat('es-MX', {
    timeZone: timezone,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(now);
  const formattedDate = new Intl.DateTimeFormat('es-MX', {
    timeZone: timezone,
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(now);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const code = employeeCode.trim().toUpperCase();
    if (!/^[A-Z0-9]{6}$/.test(code)) {
      setError('La clave debe tener exactamente 6 caracteres alfanuméricos.');
      return;
    }
    if (!session?.active_branch?.id) {
      setError('La sesión no tiene una sucursal activa.');
      return;
    }
    setIsSubmitting(true);
    setError('');
    setResult(null);
    try {
      const response = await fetchApi<AttendanceResult>('/attendance/checks', {
        method: 'POST',
        body: JSON.stringify({
          employee_code: code,
          branch_id: session.active_branch.id,
        }),
      });
      setResult(response);
      setEmployeeCode('');
      window.setTimeout(() => inputRef.current?.focus(), 0);
    } catch (reason) {
      setError(errorMessage(reason));
      inputRef.current?.select();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isSubmitting) onClose();
      }}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000, display: 'grid', placeItems: 'center',
        padding: 20, background: 'rgba(15, 23, 42, .55)', backdropFilter: 'blur(4px)',
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="attendance-clock-title"
        style={{
          width: 'min(440px, 100%)', borderRadius: 22, background: '#fff',
          boxShadow: '0 24px 64px rgba(15, 23, 42, .24)', overflow: 'hidden',
        }}
      >
        <div style={{ padding: '18px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ display: 'grid', placeItems: 'center', width: 38, height: 38, borderRadius: 12, color: '#047857', background: '#d1fae5' }}>
              <Clock3 size={22} />
            </span>
            <div>
              <h2 id="attendance-clock-title" style={{ margin: 0, fontSize: 20, color: '#0f172a' }}>Checador</h2>
              <p style={{ margin: '2px 0 0', color: '#64748b', fontSize: 13 }}>{session?.active_branch?.name}</p>
            </div>
          </div>
          <button type="button" aria-label="Cerrar checador" onClick={onClose} disabled={isSubmitting} style={{ border: 0, background: 'transparent', color: '#64748b', cursor: 'pointer', padding: 6 }}>
            <X size={22} />
          </button>
        </div>

        <div style={{ padding: '28px 28px 30px' }}>
          <div style={{ textAlign: 'center', marginBottom: 26 }}>
            <strong aria-live="off" style={{ display: 'block', fontSize: 48, letterSpacing: '-.04em', color: '#0f172a', fontVariantNumeric: 'tabular-nums' }}>
              {formattedTime}
            </strong>
            <span style={{ color: '#64748b', textTransform: 'capitalize' }}>{formattedDate}</span>
          </div>

          <form onSubmit={submit} style={{ display: 'grid', gap: 14 }}>
            <label htmlFor="attendance-employee-code" style={{ color: '#334155', fontSize: 14, fontWeight: 700 }}>
              Clave del empleado
            </label>
            <div style={{ position: 'relative' }}>
              <KeyRound size={20} aria-hidden="true" style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
              <input
                ref={inputRef}
                id="attendance-employee-code"
                type="password"
                inputMode="text"
                autoComplete="off"
                maxLength={6}
                pattern="[A-Za-z0-9]{6}"
                value={employeeCode}
                onChange={(event) => setEmployeeCode(event.target.value.replace(/[^a-z0-9]/gi, '').toUpperCase())}
                disabled={isSubmitting}
                style={{ width: '100%', boxSizing: 'border-box', minHeight: 50, border: '1px solid #cbd5e1', borderRadius: 12, padding: '0 14px 0 44px', fontSize: 20, letterSpacing: '.08em', outlineColor: '#10b981' }}
              />
            </div>
            {error && <p role="alert" style={{ margin: 0, padding: '10px 12px', borderRadius: 10, color: '#b91c1c', background: '#fef2f2', fontSize: 14 }}>{error}</p>}
            {result && (
              <div role="status" style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '12px 14px', borderRadius: 12, color: '#047857', background: '#ecfdf5' }}>
                <CheckCircle2 size={22} />
                <div>
                  <strong>{result.daily_sequence === 1 ? 'Primera checada registrada' : 'Salida registrada'}</strong>
                  <div style={{ fontSize: 13, marginTop: 2 }}>{result.employee_name_snapshot}</div>
                </div>
              </div>
            )}
            <button type="submit" disabled={isSubmitting} style={{ minHeight: 50, border: 0, borderRadius: 12, background: isSubmitting ? '#a7f3d0' : '#10b981', color: '#fff', fontWeight: 800, fontSize: 16, cursor: isSubmitting ? 'wait' : 'pointer' }}>
              {isSubmitting ? 'Registrando…' : 'Registrar checada'}
            </button>
          </form>
        </div>
      </section>
    </div>
  );
};

export default AttendanceClockModal;
