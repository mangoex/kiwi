import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { CheckCircle2, Clock, Printer, RefreshCw, Settings as SettingsIcon, WifiOff } from 'lucide-react';
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
  const [activeTab, setActiveTab] = useState<'shift' | 'printers' | 'sync'>('shift');
  const [branches, setBranches] = useState<BranchOption[]>([]);
  const [branchId, setBranchId] = useState(session?.active_branch?.id || '');
  const [persistedRegisterId, setPersistedRegisterId] = useState(
    () => normalizeRegisterId(localStorage.getItem('pos_register_id') || ''),
  );
  const [persistedBranchId, setPersistedBranchId] = useState(activeBranchId);
  const [registerId, setRegisterId] = useState(persistedRegisterId);
  const [startingCash, setStartingCash] = useState('0.00');
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
    if (activeBranchId) setBranchId(activeBranchId);
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
    if (!activeBranchId || !persistedRegisterId || persistedBranchId !== activeBranchId) {
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
  }, [activeBranchId, canRead, persistedBranchId, persistedRegisterId]);

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
    if (!canRead || !canOpen || viewState !== 'closed' || !selectedBranchIsValidated || !configurationSaved) {
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
      <header className="settings-header"><SettingsIcon size={28} /><div><h1>Configuración de Caja</h1><p>Administra la caja local y su turno operativo.</p></div></header>
      <div className="settings-layout">
        <nav className="settings-tabs" aria-label="Secciones de configuración">
          <TabButton active={activeTab === 'shift'} onClick={() => setActiveTab('shift')} icon={<Clock size={20} />} label="Turno y Caja" />
          <TabButton active={activeTab === 'printers'} onClick={() => setActiveTab('printers')} icon={<Printer size={20} />} label="Impresoras" />
          <TabButton active={activeTab === 'sync'} onClick={() => setActiveTab('sync')} icon={<WifiOff size={20} />} label="Modo Offline" />
        </nav>
        <section className="settings-panel">
          {message && <div ref={feedbackRef} tabIndex={-1} role={messageKind} className={`settings-feedback ${messageKind === 'alert' ? 'is-error' : ''}`}>{message}</div>}
          {activeTab === 'shift' && <>
            <h2>Gestión de turno</h2>
            {!canRead && <p role="alert" className="settings-feedback is-error">No tienes permiso para consultar turnos. Los controles permanecen ocultos.</p>}
            {canRead && viewState === 'loading' && <p role="status">Consultando el estado de la caja…</p>}
            {canRead && viewState === 'error' && <Button variant="secondary" onClick={hasRetryIntent ? retryIntent : () => void loadShift()}>{hasRetryIntent ? 'Reintentar la misma solicitud' : 'Reintentar consulta'}</Button>}
            {canRead && <div className={`shift-status-card ${currentShift ? 'is-open' : ''}`}>
              <div><h3>Estado de la caja</h3><p>{currentShift ? `Turno abierto en ${currentShift.register_code}.` : persistedRegisterId ? `No hay un turno abierto para ${persistedRegisterId}.` : 'Guarda una caja para consultar su turno.'}</p></div>
              {currentShift && canClose && <Button variant="secondary" disabled={viewState !== 'open'} onClick={closeShift}>{viewState === 'submitting' ? 'Cerrando…' : 'Cerrar operativamente'}</Button>}
            </div>}
            <p className="shift-cut-note"><strong>El corte final queda pendiente</strong> después del cierre operativo; este flujo no captura contado ni diferencias.</p>

            {!currentShift && <div className="shift-form-grid">
              <label>Sucursal asignada<select value={branchId} disabled={!isOrganizationScope || selectingBranch || viewState === 'submitting'} onChange={(event) => setBranchId(event.target.value)}><option value="">Selecciona…</option>{branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label>
              <label>Identificador de caja<input value={registerId} disabled={viewState === 'submitting'} onChange={(event) => setRegisterId(event.target.value)} placeholder="Ej. CAJA-02" /></label>
              <Button variant="secondary" onClick={() => void saveConfiguration()} disabled={selectingBranch || viewState === 'submitting' || configurationSaved}>{selectingBranch ? 'Validando…' : configurationSaved ? <><CheckCircle2 size={17} /> Guardado</> : 'Guardar configuración'}</Button>
              {!configurationSaved && <p role="status" className="shift-configuration-note">Hay cambios sin guardar. El estado mostrado y cualquier cierre corresponden a la caja guardada {persistedRegisterId || '(ninguna)'}; guarda antes de abrir un turno nuevo.</p>}
              {canRead && canOpen && <label>Fondo inicial ($)<input inputMode="decimal" value={startingCash} disabled={viewState !== 'closed'} onChange={(event) => setStartingCash(event.target.value)} /></label>}
              {canRead && canOpen && <Button onClick={openShift} disabled={viewState !== 'closed' || !configurationSaved}>{viewState === 'submitting' ? 'Abriendo…' : 'Abrir turno'}</Button>}
            </div>}

            {lastClosure && summary && <section className="shift-closure-summary" aria-label="Último cierre operativo">
              <h3>Último cierre operativo</h3>
              <p>Cerrado por <strong>{lastClosure.closed_by_user_id}</strong> el <time dateTime={lastClosure.closed_at}>{new Date(lastClosure.closed_at).toLocaleString('es-MX', { timeZone: session?.active_branch?.timezone || 'UTC' })}</time>.</p>
              <dl><div><dt>Venta</dt><dd>{money(summary.sales_total_cents)}</dd></div><div><dt>Pagos</dt><dd>{money(summary.payment_total_cents)}</dd></div><div><dt>Efectivo esperado</dt><dd>{money(summary.expected_cash_cents)}</dd></div><div><dt>Fondo inicial</dt><dd>{money(summary.opening_cash_cents)}</dd></div><div><dt>Pagos confirmados</dt><dd>{summary.confirmed_payment_count ?? 'No disponible'}</dd></div><div><dt>Pedidos cerrados</dt><dd>{summary.closed_order_count ?? 'No disponible'}</dd></div></dl>
            </section>}
          </>}
          {activeTab === 'printers' && <div><h2>Configuración de impresoras</h2><p>La configuración de impresión no forma parte del cierre operativo.</p></div>}
          {activeTab === 'sync' && <div><h2>Sincronización y red</h2><p><RefreshCw size={18} aria-hidden="true" /> El modo offline se administra por separado.</p></div>}
        </section>
      </div>
    </div>
  );
};

const TabButton = ({ active, icon, label, onClick }: { active: boolean; icon: React.ReactNode; label: string; onClick: () => void }) => (
  <button type="button" aria-pressed={active} className={active ? 'is-active' : ''} onClick={onClick}>{icon}{label}</button>
);

export default Settings;
