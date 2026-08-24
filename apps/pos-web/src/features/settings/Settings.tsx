import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { CheckCircle2, Clock, Printer, RefreshCw, Settings as SettingsIcon, WifiOff, Building2, Store } from 'lucide-react';
import { Button } from '@restaurantos/ui';
import { usePosSession } from '../../session';
import {
  type CloseIntent,
  type CashShiftView,
  type ClosureView,
  createCloseIntent,
  isIdempotencyConflict,
  isPersistedCashConfiguration,
  normalizeRegisterId,
  parseCloseResponse,
  parseCurrentShiftResponse,
  parseOpenShiftResponse,
  parseExactCents,
} from './shiftOperations';
import { UserCashCutsPanel } from './UserCashCutsPanel';

type ShiftViewState = 'loading' | 'open' | 'closed' | 'submitting' | 'error';

interface BranchOption { id: string; name: string }
interface OpenIntent {
  readonly key: string;
  readonly payload: Readonly<{ branch_id: string; register_id: string; opening_cash_cents: number }>;
}

const formatApiError = (error: unknown, fallback: string) => {
  if (error instanceof ApiError) {
    if (error.code === 'permission_denied') return 'Esta cuenta no tiene permiso para operar la caja seleccionada.';
    if (error.code === 'cash_shift_already_open') return 'Esta caja ya tiene un turno abierto.';
    if (error.code === 'idempotency_conflict') return 'La solicitud guardada ya no coincide. Revisa el estado antes de volver a intentar.';
    return error.message || fallback;
  }
  return error instanceof Error ? error.message : fallback;
};

const money = (cents: number | undefined) => Number.isSafeInteger(cents)
  ? new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format((cents || 0) / 100)
  : 'No disponible';

const Settings = () => {
  const { session, hasPermission, selectBranch } = usePosSession();
  const activeBranchId = session?.active_branch?.id || '';
  const activeBranchName = session?.active_branch?.name || 'Sucursal';
  const [activeTab, setActiveTab] = useState<'shift' | 'printers' | 'sync' | 'user-cuts'>('shift');
  const [branches, setBranches] = useState<BranchOption[]>([]);
  const [branchId, setBranchId] = useState(activeBranchId);
  
  const [persistedRegisterId, setPersistedRegisterId] = useState(() => {
    const stored = localStorage.getItem('pos_register_id');
    return stored ? normalizeRegisterId(stored) : 'Caja 1';
  });
  const [persistedBranchId, setPersistedBranchId] = useState(activeBranchId);
  const [registerId, setRegisterId] = useState(persistedRegisterId || 'Caja 1');
  const [startingCash, setStartingCash] = useState('500.00');
  const [viewState, setViewState] = useState<ShiftViewState>('loading');
  const [currentShift, setCurrentShift] = useState<CashShiftView | null>(null);
  const [lastClosure, setLastClosure] = useState<ClosureView | null>(null);
  const [message, setMessage] = useState('');
  const [messageKind, setMessageKind] = useState<'status' | 'alert'>('status');
  const [selectingBranch, setSelectingBranch] = useState(false);
  const requestController = useRef<AbortController | null>(null);
  const submitLockRef = useRef(false);
  const closeIntentRef = useRef<CloseIntent | null>(null);
  const openIntentRef = useRef<OpenIntent | null>(null);
  const [hasRetryIntent, setHasRetryIntent] = useState(false);
  const feedbackRef = useRef<HTMLDivElement | null>(null);

  const isOrganizationScope = session?.scope.level === 'organization';
  const canRead = hasPermission('cash.shift.read');
  const canOpen = hasPermission('cash.shift.open');
  const canClose = hasPermission('cash.shift.close');
  const canReadUserCuts = hasPermission('cash.user_cut.read');
  const selectedBranchIsValidated = branchId === activeBranchId;
  const configurationSaved = isPersistedCashConfiguration(
    branchId, activeBranchId, registerId, persistedRegisterId, persistedBranchId,
  );

  const announce = (text: string, kind: 'status' | 'alert' = 'status') => {
    setMessage(text);
    setMessageKind(kind);
    window.setTimeout(() => feedbackRef.current?.focus(), 0);
  };

  useEffect(() => {
    if (activeBranchId) {
      setBranchId(activeBranchId);
      setPersistedBranchId(activeBranchId);
      if (!localStorage.getItem('pos_register_id')) {
        localStorage.setItem('pos_register_id', 'Caja 1');
      }
    }
  }, [activeBranchId]);

  useEffect(() => {
    if (!isOrganizationScope) {
      setBranches(session?.active_branch ? [{ id: session.active_branch.id, name: session.active_branch.name }] : []);
      return;
    }
    const controller = new AbortController();
    fetchApi<BranchOption[]>('/branches', { signal: controller.signal })
      .then((response) => setBranches(Array.isArray(response)
        ? response.filter((branch) => !session?.scope.allowed_branch_ids.length
          || session.scope.allowed_branch_ids.includes(branch.id))
        : []))
      .catch((reason) => {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
          announce('No fue posible cargar las sucursales autorizadas.', 'alert');
        }
      });
    return () => controller.abort();
  }, [isOrganizationScope, session?.active_branch, session?.scope.allowed_branch_ids]);

  const loadShift = useCallback(async () => {
    requestController.current?.abort();
    if (!canRead) {
      setViewState('closed');
      setCurrentShift(null);
      return;
    }
    if (!activeBranchId || !persistedRegisterId) {
      setCurrentShift(null);
      setLastClosure(null);
      setViewState('closed');
      return;
    }
    const controller = new AbortController();
    requestController.current = controller;
    setViewState('loading');
    try {
      const raw = await fetchApi<unknown>(
        `/cash/shifts/current?branch_id=${encodeURIComponent(activeBranchId)}&register_id=${encodeURIComponent(persistedRegisterId)}`,
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      const response = parseCurrentShiftResponse(raw);
      setCurrentShift(response.cash_shift);
      setLastClosure(response.closure || null);
      setViewState(response.cash_shift ? 'open' : 'closed');
    } catch (reason) {
      if (controller.signal.aborted) return;
      setCurrentShift(null);
      setViewState('error');
      announce(formatApiError(reason, 'No fue posible consultar el turno. La operación queda bloqueada.'), 'alert');
    }
  }, [activeBranchId, canRead, persistedRegisterId]);

  useEffect(() => {
    void loadShift();
    return () => requestController.current?.abort();
  }, [loadShift]);

  const saveConfiguration = async () => {
    const normalizedRegister = normalizeRegisterId(registerId);
    setMessage('');
    if (!branchId || !normalizedRegister) {
      announce('Selecciona una sucursal y escribe el identificador de caja.', 'alert');
      return;
    }
    setSelectingBranch(true);
    try {
      if (isOrganizationScope && branchId !== activeBranchId) await selectBranch(branchId);
      localStorage.setItem('pos_register_id', normalizedRegister);
      setPersistedBranchId(branchId);
      setPersistedRegisterId(normalizedRegister);
      setRegisterId(normalizedRegister);
      setViewState('loading');
      announce('Configuración de caja guardada.');
    } catch (reason) {
      announce(formatApiError(reason, 'No fue posible validar la sucursal seleccionada.'), 'alert');
    } finally {
      setSelectingBranch(false);
    }
  };

  const executeOpen = async (intent: OpenIntent) => {
    try {
      const raw = await fetchApi<unknown>('/cash/shifts/open', {
        method: 'POST', headers: { 'Idempotency-Key': intent.key },
        body: JSON.stringify(intent.payload),
      });
      const shift = parseOpenShiftResponse(raw);
      openIntentRef.current = null;
      setHasRetryIntent(Boolean(closeIntentRef.current));
      setCurrentShift(shift);
      setViewState('open');
      announce('Turno abierto correctamente.');
    } catch (reason) {
      const uncertain = !(reason instanceof ApiError) || reason.status >= 500;
      openIntentRef.current = uncertain && !isIdempotencyConflict(reason) ? intent : null;
      setHasRetryIntent(Boolean(openIntentRef.current || closeIntentRef.current));
      setViewState('error');
      announce(formatApiError(reason, 'No se confirmó la apertura. Puedes reintentar la misma solicitud.'), 'alert');
    }
  };

  const executeClose = async (intent: CloseIntent) => {
    try {
      const raw = await fetchApi<unknown>(
        `/cash/shifts/${encodeURIComponent(intent.shiftId)}/close-operationally`,
        { method: 'POST', headers: { 'Idempotency-Key': intent.key }, body: JSON.stringify(intent.payload) },
      );
      const response = parseCloseResponse(raw);
      closeIntentRef.current = null;
      setHasRetryIntent(Boolean(openIntentRef.current));
      setCurrentShift(null);
      setLastClosure(response.closure);
      setViewState('closed');
      announce('Turno cerrado operativamente. El corte final queda pendiente.');
    } catch (reason) {
      const uncertain = !(reason instanceof ApiError) || reason.status >= 500;
      closeIntentRef.current = uncertain && !isIdempotencyConflict(reason) ? intent : null;
      setHasRetryIntent(Boolean(openIntentRef.current || closeIntentRef.current));
      setViewState('error');
      announce(formatApiError(reason, 'No se confirmó el cierre. Puedes reintentar la misma solicitud.'), 'alert');
    }
  };

  const withSubmitLock = async (operation: () => Promise<void>) => {
    if (submitLockRef.current) return;
    submitLockRef.current = true;
    setViewState('submitting');
    try { await operation(); } finally { submitLockRef.current = false; }
  };

  const openShift = () => void withSubmitLock(async () => {
    if (!canRead || !canOpen || viewState !== 'closed' || !selectedBranchIsValidated) {
      setViewState('error');
      announce('Guarda una sucursal y caja autorizadas antes de abrir el turno.', 'alert');
      return;
    }
    const openingCashCents = parseExactCents(startingCash);
    if (openingCashCents === null) {
      setViewState('closed');
      announce('El fondo inicial debe ser un importe exacto, no negativo y con máximo dos decimales.', 'alert');
      return;
    }
    const intent: OpenIntent = Object.freeze({
      key: crypto.randomUUID(),
      payload: Object.freeze({ branch_id: activeBranchId, register_id: persistedRegisterId, opening_cash_cents: openingCashCents }),
    });
    openIntentRef.current = intent;
    await executeOpen(intent);
  });

  const closeShift = () => void withSubmitLock(async () => {
    if (!canClose || !currentShift) {
      setViewState(currentShift ? 'open' : 'closed');
      announce('No hay un turno abierto autorizado para cerrar.', 'alert');
      return;
    }
    const intent = createCloseIntent(currentShift.id, crypto.randomUUID());
    closeIntentRef.current = intent;
    await executeClose(intent);
  });

  const retryIntent = () => void withSubmitLock(async () => {
    if (closeIntentRef.current) await executeClose(closeIntentRef.current);
    else if (openIntentRef.current) await executeOpen(openIntentRef.current);
    else await loadShift();
  });

  const summary = lastClosure?.summary_snapshot;

  return (
    <div className="settings-page">
      <header className="settings-header">
        <SettingsIcon size={28} />
        <div>
          <h1>Apertura y Configuración de Caja</h1>
          <p>Administra la caja de {activeBranchName} y tu turno operativo diario.</p>
        </div>
      </header>

      <div className="settings-layout">
        <nav className="settings-tabs" aria-label="Secciones de configuración">
          <TabButton active={activeTab === 'shift'} onClick={() => setActiveTab('shift')} icon={<Clock size={20} />} label="Turno y Caja" />
          <TabButton active={activeTab === 'printers'} onClick={() => setActiveTab('printers')} icon={<Printer size={20} />} label="Impresoras" />
          <TabButton active={activeTab === 'sync'} onClick={() => setActiveTab('sync')} icon={<WifiOff size={20} />} label="Modo Offline" />
          {canReadUserCuts && <TabButton active={activeTab === 'user-cuts'} onClick={() => setActiveTab('user-cuts')} icon={<CheckCircle2 size={20} />} label="Cortes por usuario" />}
        </nav>

        <section className="settings-panel">
          {message && (
            <div ref={feedbackRef} tabIndex={-1} role={messageKind} className={`settings-feedback ${messageKind === 'alert' ? 'is-error' : ''}`}>
              {message}
            </div>
          )}

          {activeTab === 'shift' && (
            <>
              <h2>Gestión de Turno</h2>
              {!canRead && (
                <p role="alert" className="settings-feedback is-error">
                  No tienes permiso para consultar turnos de caja.
                </p>
              )}

              {canRead && viewState === 'loading' && (
                <p role="status" style={{ color: 'var(--color-text-muted)', padding: '12px 0' }}>Consultando el estado de la caja…</p>
              )}

              {canRead && viewState === 'error' && (
                <div style={{ marginBottom: 16 }}>
                  <Button variant="secondary" onClick={hasRetryIntent ? retryIntent : () => void loadShift()}>
                    {hasRetryIntent ? 'Reintentar la misma solicitud' : 'Reintentar consulta'}
                  </Button>
                </div>
              )}

              {canRead && (
                <div className={`shift-status-card ${currentShift ? 'is-open' : ''}`} style={{ marginBottom: 20 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ padding: 10, background: currentShift ? '#dcfce7' : '#f1f5f9', color: currentShift ? '#16a34a' : '#64748b', borderRadius: 8 }}>
                      <Store size={22} />
                    </div>
                    <div>
                      <h3 style={{ margin: 0, fontSize: '1.1rem' }}>
                        {currentShift ? `Turno Abierto en ${currentShift.register_code}` : `Caja Cerrada (${persistedRegisterId})`}
                      </h3>
                      <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                        {currentShift
                          ? `Iniciado el ${new Date(currentShift.opened_at).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })} con fondo de ${money(currentShift.opening_cash_cents)}`
                          : `No hay un turno abierto en ${activeBranchName}. Ingresa el fondo inicial para comenzar.`}
                      </p>
                    </div>
                  </div>

                  {currentShift && canClose && (
                    <Button variant="secondary" disabled={viewState !== 'open'} onClick={closeShift}>
                      {viewState === 'submitting' ? 'Cerrando…' : 'Cerrar Turno'}
                    </Button>
                  )}
                </div>
              )}

              {!currentShift && (
                <div className="shift-form-grid" style={{ background: '#f8fafc', padding: 20, borderRadius: 12, border: '1px solid #e2e8f0' }}>
                  {/* Sucursal */}
                  <label style={{ display: 'grid', gap: 4, fontWeight: 500, fontSize: '0.875rem' }}>
                    <span>Sucursal</span>
                    {isOrganizationScope ? (
                      <select
                        value={branchId}
                        disabled={selectingBranch || viewState === 'submitting'}
                        onChange={(event) => setBranchId(event.target.value)}
                        style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff' }}
                      >
                        <option value="">Selecciona sucursal…</option>
                        {branches.map((b) => (
                          <option key={b.id} value={b.id}>{b.name}</option>
                        ))}
                      </select>
                    ) : (
                      <div style={{ padding: '10px 14px', background: '#e2e8f0', borderRadius: 8, color: '#334155', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Building2 size={16} />
                        <span>{activeBranchName} (Sucursal asignada)</span>
                      </div>
                    )}
                  </label>

                  {/* Caja */}
                  <label style={{ display: 'grid', gap: 4, fontWeight: 500, fontSize: '0.875rem' }}>
                    <span>Identificador de Caja</span>
                    <input
                      value={registerId}
                      disabled={viewState === 'submitting'}
                      onChange={(event) => setRegisterId(event.target.value)}
                      placeholder="Ej. Caja 1"
                      style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff' }}
                    />
                  </label>

                  {isOrganizationScope && (
                    <Button
                      variant="secondary"
                      onClick={() => void saveConfiguration()}
                      disabled={selectingBranch || viewState === 'submitting' || configurationSaved}
                    >
                      {selectingBranch ? 'Validando…' : configurationSaved ? <><CheckCircle2 size={17} /> Guardado</> : 'Guardar configuración'}
                    </Button>
                  )}

                  {/* Fondo Inicial */}
                  {canRead && canOpen && (
                    <label style={{ display: 'grid', gap: 4, fontWeight: 500, fontSize: '0.875rem' }}>
                      <span>Fondo Inicial ($ MXN)</span>
                      <input
                        inputMode="decimal"
                        value={startingCash}
                        disabled={viewState !== 'closed'}
                        onChange={(event) => setStartingCash(event.target.value)}
                        placeholder="500.00"
                        style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff', fontSize: '1.05rem', fontWeight: 600 }}
                      />
                    </label>
                  )}

                  {/* Botón Abrir Turno */}
                  {canRead && canOpen && (
                    <div style={{ marginTop: 8 }}>
                      <Button
                        variant="primary"
                        onClick={openShift}
                        disabled={viewState !== 'closed' || (!configurationSaved && isOrganizationScope)}
                        style={{ width: '100%', padding: '12px 20px', fontSize: '1rem', fontWeight: 600 }}
                      >
                        {viewState === 'submitting' ? 'Abriendo Turno…' : '🟢 Abrir Turno'}
                      </Button>
                    </div>
                  )}
                </div>
              )}

              {lastClosure && summary && (
                <section className="shift-closure-summary" aria-label="Último cierre operativo" style={{ marginTop: 24 }}>
                  <h3>Último Cierre Operativo</h3>
                  <p>
                    Cerrado por <strong>{lastClosure.closed_by_user_id}</strong> el{' '}
                    <time dateTime={lastClosure.closed_at}>
                      {new Date(lastClosure.closed_at).toLocaleString('es-MX', { timeZone: session?.active_branch?.timezone || 'UTC' })}
                    </time>.
                  </p>
                  <dl>
                    <div><dt>Venta</dt><dd>{money(summary.sales_total_cents)}</dd></div>
                    <div><dt>Pagos</dt><dd>{money(summary.payment_total_cents)}</dd></div>
                    <div><dt>Efectivo esperado</dt><dd>{money(summary.expected_cash_cents)}</dd></div>
                    <div><dt>Fondo inicial</dt><dd>{money(summary.opening_cash_cents)}</dd></div>
                    <div><dt>Pagos confirmados</dt><dd>{summary.confirmed_payment_count ?? 'No disponible'}</dd></div>
                    <div><dt>Pedidos cerrados</dt><dd>{summary.closed_order_count ?? 'No disponible'}</dd></div>
                  </dl>
                </section>
              )}
            </>
          )}

          {activeTab === 'printers' && (
            <div>
              <h2>Configuración de Impresoras</h2>
              <p>La configuración de impresión local se asocia al navegador del dispositivo.</p>
            </div>
          )}

          {activeTab === 'sync' && (
            <div>
              <h2>Sincronización y Red</h2>
              <p><RefreshCw size={18} aria-hidden="true" /> El modo offline opera en segundo plano con base de datos local SQLite.</p>
            </div>
          )}

          {activeTab === 'user-cuts' && canReadUserCuts && (
            <UserCashCutsPanel
              branchId={activeBranchId}
              registerId={persistedRegisterId}
              canCreate={hasPermission('cash.user_cut.create')}
              canReopenRequest={hasPermission('cash.user_cut.reopen.request')}
              canReopenAuthorize={hasPermission('cash.user_cut.reopen.authorize')}
            />
          )}
        </section>
      </div>
    </div>
  );
};

const TabButton = ({ active, icon, label, onClick }: { active: boolean; icon: React.ReactNode; label: string; onClick: () => void }) => (
  <button type="button" aria-pressed={active} className={active ? 'is-active' : ''} onClick={onClick}>
    {icon}
    {label}
  </button>
);

export default Settings;
