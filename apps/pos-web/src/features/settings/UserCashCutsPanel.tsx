import { useEffect, useRef, useState } from 'react';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import {
  buildUserCashCutCountedPayload,
  buildUserCashCutCreatePayload,
  buildUserCashCutFinalizePayload,
  buildUserCashCutReopenRequestPayload,
  createUserCashCutIntent,
  formatCashCutMxn,
  keepUserCashCutIntent,
  parseUserCashCut,
  parseUserCashCutCents,
  type UserCashCutCreatePayload,
  type UserCashCutCountedPayload,
  type UserCashCutFinalizePayload,
  type UserCashCutReopenRequestPayload,
  type UserCashCutView,
} from './userCashCuts';

interface CutList {
  items: unknown[];
  next_cursor: string | null;
}

interface CutDetail {
  cash_cut: unknown;
  operations: Array<{
    operation_type: string;
    operation_id: string;
    signed_amount_cents: number;
  }>;
  reopen: { id: string; status: string } | null;
}

interface ShiftList {
  items: Array<{ id?: unknown; status?: unknown }>;
  next_cursor: string | null;
}

interface EligibleShift {
  id: string;
  branchId: string;
  registerId: string;
  cashierUserId: string;
  periodStart: string;
  periodEnd: string;
}

type CommandIntent = ReturnType<typeof createUserCashCutIntent<UserCashCutCreatePayload>>;
type CutCommandIntent<T> = Readonly<{
  command: string;
  key: string;
  payload: T;
  cutId: string;
}>;
type ReopenRequestIntent = Readonly<{
  command: 'reopen-request';
  key: string;
  payload: UserCashCutReopenRequestPayload;
  cutId: string;
  requestId: null;
}>;
type ReopenDecisionIntent = Readonly<{
  command: 'reopen-approve' | 'reopen-reject' | 'reopen-compensate';
  key: string;
  cutId: string;
  requestId: string;
}>;
type ReopenIntent = ReopenRequestIntent | ReopenDecisionIntent;

function formatCashCutSnapshotTime(value: string, timeZone: string): string {
  try {
    return new Intl.DateTimeFormat('es-MX', {
      timeZone,
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value));
  } catch {
    return 'Fecha no disponible';
  }
}

function commandMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'permission_denied') return 'No tienes permiso para realizar este comando.';
    if (error.code === 'idempotency_conflict') return 'La intención ya no coincide. Crea una nueva solicitud.';
    if (error.code === 'cash_cut_version_conflict') return 'La versión cambió. Actualiza el corte antes de continuar.';
    return error.message || 'No fue posible completar el comando.';
  }
  return 'No se confirmó el comando. Puedes reintentar la misma intención.';
}

function eligibleShiftFromDetail(
  value: unknown,
  branchId: string,
  registerId: string,
): EligibleShift | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const detail = value as { cash_shift?: Record<string, unknown>; closure?: Record<string, unknown> | null };
  const shift = detail.cash_shift;
  const closure = detail.closure;
  if (!shift || shift.status !== 'OPERATIVELY_CLOSED'
    || shift.branch_id !== branchId || shift.register_code !== registerId
    || typeof shift.id !== 'string' || typeof shift.cashier_user_id !== 'string'
    || typeof shift.opened_at !== 'string' || !closure || typeof closure.closed_at !== 'string') {
    return null;
  }
  return {
    id: shift.id,
    branchId,
    registerId,
    cashierUserId: shift.cashier_user_id,
    periodStart: shift.opened_at,
    periodEnd: closure.closed_at,
  };
}

export function UserCashCutsPanel({
  branchId,
  registerId,
  canCreate,
  canReopenRequest,
  canReopenAuthorize,
}: {
  branchId: string;
  registerId: string;
  canCreate: boolean;
  canReopenRequest: boolean;
  canReopenAuthorize: boolean;
}) {
  const [items, setItems] = useState<UserCashCutView[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [selected, setSelected] = useState<CutDetail | null>(null);
  const [state, setState] = useState<'loading' | 'empty' | 'ready' | 'error'>('loading');
  const [error, setError] = useState('');
  const [eligibleShift, setEligibleShift] = useState<EligibleShift | null>(null);
  const [shiftCandidates, setShiftCandidates] = useState<string[]>([]);
  const [shiftMessage, setShiftMessage] = useState('');
  const [countedInput, setCountedInput] = useState('');
  const [createIntent, setCreateIntent] = useState<CommandIntent | null>(null);
  const [countIntent, setCountIntent] = useState<CutCommandIntent<UserCashCutCountedPayload> | null>(null);
  const [finalizeIntent, setFinalizeIntent] = useState<CutCommandIntent<UserCashCutFinalizePayload> | null>(null);
  const [reopenCountedInput, setReopenCountedInput] = useState('');
  const [reopenReason, setReopenReason] = useState('');
  const [reopenEvidence, setReopenEvidence] = useState('');
  const [reopenIntent, setReopenIntent] = useState<ReopenIntent | null>(null);
  const [commandState, setCommandState] = useState<'idle' | 'submitting' | 'conflict' | 'error'>('idle');
  const eligibleShiftLoadToken = useRef(0);
  const eligibleShiftScope = useRef({ branchId, registerId });
  eligibleShiftScope.current = { branchId, registerId };

  const load = async (next?: string | null) => {
    setState('loading');
    setError('');
    try {
      const params = new URLSearchParams({ branch_id: branchId, limit: '100' });
      if (next) params.set('cursor', next);
      const page = await fetchApi<CutList>(`/cash/user-cuts?${params}`);
      const parsed = page.items.map(parseUserCashCut);
      setItems((previous) => (next ? [...previous, ...parsed] : parsed));
      setCursor(page.next_cursor);
      setState(parsed.length || next ? 'ready' : 'empty');
    } catch {
      setState('error');
      setError('No fue posible cargar los cortes de usuario.');
    }
  };

  useEffect(() => {
    setSelected(null);
    setItems([]);
    setCursor(null);
    setCreateIntent(null);
    setCountIntent(null);
    setFinalizeIntent(null);
    setReopenIntent(null);
    void load(null);
  }, [branchId, registerId]);

  const select = async (id: string) => {
    if (countIntent && countIntent.cutId !== id) setCountIntent(null);
    if (finalizeIntent && finalizeIntent.cutId !== id) setFinalizeIntent(null);
    try {
      setSelected(await fetchApi<CutDetail>(`/cash/user-cuts/${id}`));
    } catch {
      setError('No fue posible cargar el detalle.');
    }
  };

  const inspectShift = async (shiftId: string) => {
    setEligibleShift(null);
    setShiftMessage('Consultando el cierre operativo…');
    try {
      const detail = await fetchApi<unknown>(`/cash/shifts/${encodeURIComponent(shiftId)}`);
      const eligible = eligibleShiftFromDetail(detail, branchId, registerId);
      if (!eligible) {
        setShiftMessage('El turno no es elegible: requiere cierre operativo, cajero canónico y periodo completo.');
        return;
      }
      setEligibleShift(eligible);
      setShiftMessage('Turno elegible para crear un corte en borrador.');
    } catch {
      setShiftMessage('No fue posible verificar el turno seleccionado.');
    }
  };

  const loadEligibleShifts = async () => {
    const requestToken = ++eligibleShiftLoadToken.current;
    const scope = { branchId, registerId };
    const isActiveScope = () => (
      requestToken === eligibleShiftLoadToken.current
      && eligibleShiftScope.current.branchId === scope.branchId
      && eligibleShiftScope.current.registerId === scope.registerId
    );
    setShiftCandidates([]);
    if (!canCreate || !branchId || !registerId) return;
    setShiftMessage('Cargando turnos cerrados…');
    try {
      const shifts: ShiftList['items'] = [];
      const seenCursors = new Set<string>();
      let cursor: string | null = null;
      do {
        const params = new URLSearchParams({
          branch_id: scope.branchId,
          register_id: scope.registerId,
          limit: '100',
        });
        if (cursor) params.set('cursor', cursor);
        const page = await fetchApi<ShiftList>(`/cash/shifts?${params}`);
        if (!isActiveScope()) return;
        shifts.push(...page.items);
        if (!page.next_cursor) break;
        if (seenCursors.has(page.next_cursor)) {
          setShiftMessage('No fue posible cargar los turnos: cursor de paginación inválido.');
          return;
        }
        seenCursors.add(page.next_cursor);
        cursor = page.next_cursor;
      } while (cursor);
      if (!isActiveScope()) return;
      const cutShiftIds = new Set(items.map((cut) => cut.cash_shift_id));
      const candidates = shifts.filter((shift) => (
        typeof shift.id === 'string'
        && shift.status === 'OPERATIVELY_CLOSED'
        && !cutShiftIds.has(shift.id)
      ));
      setShiftCandidates(candidates.map((shift) => shift.id as string));
      if (!candidates.length) {
        setShiftMessage('No hay turnos cerrados elegibles para esta caja.');
        return;
      }
      setShiftMessage('Selecciona un turno cerrado para verificar su periodo canónico.');
    } catch {
      if (!isActiveScope()) return;
      setShiftMessage('No fue posible cargar los turnos cerrados.');
    }
  };

  useEffect(() => {
    void loadEligibleShifts();
  }, [branchId, registerId, canCreate, items]);

  const runCreate = async (intent: CommandIntent) => {
    setCommandState('submitting');
    try {
      const result = await fetchApi<{ cash_cut: unknown }>('/cash/user-cuts', {
        method: 'POST',
        headers: { 'Idempotency-Key': intent.key },
        body: JSON.stringify(intent.payload),
      });
      const cut = parseUserCashCut(result.cash_cut);
      setCreateIntent(null);
      setEligibleShift(null);
      await load(null);
      await select(cut.id);
      setCommandState('idle');
    } catch (reason) {
      const conflict = reason instanceof ApiError && reason.code === 'idempotency_conflict';
      setCreateIntent(keepUserCashCutIntent(intent, conflict ? 'idempotency_conflict' : 'retry'));
      setCommandState(conflict ? 'conflict' : 'error');
      setError(commandMessage(reason));
    }
  };

  const createDraft = () => {
    if (!eligibleShift) return;
    const payload = buildUserCashCutCreatePayload({
      branch_id: eligibleShift.branchId,
      register_id: eligibleShift.registerId,
      cash_shift_id: eligibleShift.id,
      cashier_user_id: eligibleShift.cashierUserId,
      period_start: eligibleShift.periodStart,
      period_end: eligibleShift.periodEnd,
    });
    const intent = createUserCashCutIntent('create', crypto.randomUUID(), payload);
    setCreateIntent(intent);
    void runCreate(intent);
  };

  const runCount = async (intent: NonNullable<typeof countIntent>) => {
    setCommandState('submitting');
    try {
      await fetchApi(`/cash/user-cuts/${encodeURIComponent(intent.cutId)}/counted-cash`, {
        method: 'POST', headers: { 'Idempotency-Key': intent.key }, body: JSON.stringify(intent.payload),
      });
      setCountIntent(null);
      setCountedInput('');
      await load(null);
      await select(intent.cutId);
      setCommandState('idle');
    } catch (reason) {
      const conflict = reason instanceof ApiError && reason.code === 'idempotency_conflict';
      setCountIntent(keepUserCashCutIntent(intent, conflict ? 'idempotency_conflict' : 'retry'));
      setCommandState(conflict ? 'conflict' : 'error');
      setError(commandMessage(reason));
    }
  };

  const countDraft = (cut: UserCashCutView) => {
    const cents = parseUserCashCutCents(countedInput);
    if (cents === null) {
      setError('El efectivo contado debe ser un importe MXN no negativo con máximo dos decimales.');
      return;
    }
    if (!window.confirm('¿Confirmas el efectivo contado?')) return;
    const intent: CutCommandIntent<UserCashCutCountedPayload> = Object.freeze({
      ...createUserCashCutIntent(
        'counted-cash', crypto.randomUUID(), buildUserCashCutCountedPayload(cents, cut.version),
      ),
      cutId: cut.id,
    });
    setCountIntent(intent);
    void runCount(intent);
  };

  const runFinalize = async (intent: NonNullable<typeof finalizeIntent>) => {
    setCommandState('submitting');
    try {
      await fetchApi(`/cash/user-cuts/${encodeURIComponent(intent.cutId)}/finalize`, {
        method: 'POST', headers: { 'Idempotency-Key': intent.key }, body: JSON.stringify(intent.payload),
      });
      setFinalizeIntent(null);
      await load(null);
      await select(intent.cutId);
      setCommandState('idle');
    } catch (reason) {
      const conflict = reason instanceof ApiError && reason.code === 'idempotency_conflict';
      setFinalizeIntent(keepUserCashCutIntent(intent, conflict ? 'idempotency_conflict' : 'retry'));
      setCommandState(conflict ? 'conflict' : 'error');
      setError(commandMessage(reason));
    }
  };

  const finalizeCounted = (cut: UserCashCutView) => {
    if (!window.confirm('¿Confirmas finalizar este corte contado?')) return;
    const intent: CutCommandIntent<UserCashCutFinalizePayload> = Object.freeze({
      ...createUserCashCutIntent(
        'finalize', crypto.randomUUID(), buildUserCashCutFinalizePayload(cut.version),
      ),
      cutId: cut.id,
    });
    setFinalizeIntent(intent);
    void runFinalize(intent);
  };

  const refreshAfterReopen = async (cutId: string) => {
    await load(null);
    await select(cutId);
  };

  const runReopen = async (intent: ReopenIntent) => {
    const endpoint = intent.command === 'reopen-request'
      ? `/cash/user-cuts/${encodeURIComponent(intent.cutId)}/reopen-requests`
      : `/cash/user-cuts/reopen-requests/${encodeURIComponent(intent.requestId || '')}/${intent.command.slice('reopen-'.length)}`;
    setCommandState('submitting');
    try {
      await fetchApi(endpoint, {
        method: 'POST',
        headers: { 'Idempotency-Key': intent.key },
        body: intent.command === 'reopen-request' ? JSON.stringify(intent.payload) : undefined,
      });
      setReopenIntent(null);
      setReopenCountedInput('');
      setReopenReason('');
      setReopenEvidence('');
      await refreshAfterReopen(intent.cutId);
      setCommandState('idle');
    } catch (reason) {
      const conflict = reason instanceof ApiError && reason.code === 'idempotency_conflict';
      setReopenIntent(keepUserCashCutIntent(intent, conflict ? 'idempotency_conflict' : 'retry'));
      setCommandState(conflict ? 'conflict' : 'error');
      setError(commandMessage(reason));
    }
  };

  const requestReopen = (cut: UserCashCutView) => {
    const cents = parseUserCashCutCents(reopenCountedInput);
    const evidenceRefs = reopenEvidence.split('\n').map((value) => value.trim()).filter(Boolean);
    if (cents === null || !reopenReason.trim() || !evidenceRefs.length) {
      setError('Captura efectivo corregido, motivo y al menos una evidencia.');
      return;
    }
    if (!window.confirm('¿Confirmas solicitar la reapertura del corte?')) return;
    const intent: ReopenIntent = Object.freeze({
      command: 'reopen-request',
      key: crypto.randomUUID(),
      payload: buildUserCashCutReopenRequestPayload(cents, reopenReason, evidenceRefs),
      cutId: cut.id,
      requestId: null,
    });
    setReopenIntent(intent);
    void runReopen(intent);
  };

  const decideReopen = (cut: UserCashCutView, requestId: string, decision: 'approve' | 'reject') => {
    if (!window.confirm(decision === 'approve' ? '¿Confirmas aprobar la reapertura?' : '¿Confirmas rechazar la reapertura?')) return;
    const intent: ReopenIntent = Object.freeze({
      command: decision === 'approve' ? 'reopen-approve' : 'reopen-reject',
      key: crypto.randomUUID(),
      cutId: cut.id,
      requestId,
    });
    setReopenIntent(intent);
    void runReopen(intent);
  };

  const compensateReopen = (cut: UserCashCutView, requestId: string) => {
    if (!window.confirm('¿Confirmas registrar la compensación de reapertura?')) return;
    const intent: ReopenIntent = Object.freeze({
      command: 'reopen-compensate',
      key: crypto.randomUUID(),
      cutId: cut.id,
      requestId,
    });
    setReopenIntent(intent);
    void runReopen(intent);
  };

  const invalidateReopenIntent = () => {
    if (reopenIntent) setReopenIntent(null);
  };

  const retry = () => {
    if (reopenIntent) void runReopen(reopenIntent);
    else if (createIntent) void runCreate(createIntent);
    else if (countIntent) void runCount(countIntent);
    else if (finalizeIntent) void runFinalize(finalizeIntent);
  };

  return (
    <section className="user-cash-cuts" aria-labelledby="user-cuts-title">
      <h2 id="user-cuts-title">Cortes por usuario</h2>
      {canCreate && (
        <section aria-labelledby="create-user-cut-title">
          <h3 id="create-user-cut-title">Crear corte</h3>
          <p role="status">{shiftMessage}</p>
          <ul aria-label="Turnos cerrados elegibles">
            {shiftCandidates.map((shiftId) => (
              <li key={shiftId}>
                <button type="button" onClick={() => void inspectShift(shiftId)}>Seleccionar turno {shiftId}</button>
              </li>
            ))}
          </ul>
          {eligibleShift && <button type="button" disabled={commandState === 'submitting'} onClick={createDraft}>Crear borrador</button>}
        </section>
      )}
      {state === 'loading' && <p role="status">Cargando cortes…</p>}
      {(state === 'error' || commandState === 'error' || commandState === 'conflict') && <p role="alert">{error}</p>}
      {(commandState === 'error' || commandState === 'conflict') && (createIntent || countIntent || finalizeIntent || reopenIntent) && <button type="button" onClick={retry}>Reintentar la misma solicitud</button>}
      {state === 'empty' && <p>No hay cortes para esta sucursal.</p>}
      <ul aria-label="Historial de cortes por usuario">
        {items.map((cut) => (
          <li key={cut.id}>
            <button type="button" onClick={() => void select(cut.id)}>
              {cut.status} · {cut.register_code_snapshot} · {formatCashCutMxn(cut.expected_cash_cents ?? cut.opening_cash_cents)}
            </button>
          </li>
        ))}
      </ul>
      {cursor && <button type="button" onClick={() => void load(cursor)}>Siguiente</button>}
      {selected && (
        <UserCashCutDetail
          detail={selected}
          canCreate={canCreate}
          canReopenRequest={canReopenRequest}
          canReopenAuthorize={canReopenAuthorize}
          countedInput={countedInput}
          reopenCountedInput={reopenCountedInput}
          reopenReason={reopenReason}
          reopenEvidence={reopenEvidence}
          commandState={commandState}
          onCountedInput={(value) => { setCountedInput(value); if (countIntent) setCountIntent(null); }}
          onReopenCountedInput={(value) => { setReopenCountedInput(value); invalidateReopenIntent(); }}
          onReopenReason={(value) => { setReopenReason(value); invalidateReopenIntent(); }}
          onReopenEvidence={(value) => { setReopenEvidence(value); invalidateReopenIntent(); }}
          onCount={countDraft}
          onFinalize={finalizeCounted}
          onRequestReopen={requestReopen}
          onDecideReopen={decideReopen}
          onCompensateReopen={compensateReopen}
        />
      )}
    </section>
  );
}

function UserCashCutDetail({
  detail,
  canCreate,
  canReopenRequest,
  canReopenAuthorize,
  countedInput,
  reopenCountedInput,
  reopenReason,
  reopenEvidence,
  commandState,
  onCountedInput,
  onReopenCountedInput,
  onReopenReason,
  onReopenEvidence,
  onCount,
  onFinalize,
  onRequestReopen,
  onDecideReopen,
  onCompensateReopen,
}: {
  detail: CutDetail;
  canCreate: boolean;
  canReopenRequest: boolean;
  canReopenAuthorize: boolean;
  countedInput: string;
  reopenCountedInput: string;
  reopenReason: string;
  reopenEvidence: string;
  commandState: 'idle' | 'submitting' | 'conflict' | 'error';
  onCountedInput: (value: string) => void;
  onReopenCountedInput: (value: string) => void;
  onReopenReason: (value: string) => void;
  onReopenEvidence: (value: string) => void;
  onCount: (cut: UserCashCutView) => void;
  onFinalize: (cut: UserCashCutView) => void;
  onRequestReopen: (cut: UserCashCutView) => void;
  onDecideReopen: (cut: UserCashCutView, requestId: string, decision: 'approve' | 'reject') => void;
  onCompensateReopen: (cut: UserCashCutView, requestId: string) => void;
}) {
  const cut = parseUserCashCut(detail.cash_cut);
  const mayRequestReopen = detail.reopen === null
    || detail.reopen.status === 'REJECTED'
    || detail.reopen.status === 'COMPENSATED';
  return (
    <article aria-label="Detalle del corte">
      <h3>Detalle: {cut.status}</h3>
      <dl>
        <div><dt>Caja</dt><dd>{cut.register_code_snapshot}</dd></div>
        <div><dt>Cajero</dt><dd>{cut.cashier_user_id}</dd></div>
        <div><dt>Zona horaria</dt><dd>{cut.timezone}</dd></div>
        <div><dt>Inicio del periodo</dt><dd>{formatCashCutSnapshotTime(cut.period_start, cut.timezone)}</dd></div>
        <div><dt>Fin del periodo</dt><dd>{formatCashCutSnapshotTime(cut.period_end, cut.timezone)}</dd></div>
        <div><dt>Fondo inicial</dt><dd>{formatCashCutMxn(cut.opening_cash_cents)}</dd></div>
        {cut.expected_cash_cents !== null && <div><dt>Efectivo esperado</dt><dd>{formatCashCutMxn(cut.expected_cash_cents)}</dd></div>}
        {cut.counted_cash_cents !== null && <div><dt>Efectivo contado</dt><dd>{formatCashCutMxn(cut.counted_cash_cents)}</dd></div>}
        {cut.difference_cents !== null && <div><dt>Diferencia</dt><dd>{formatCashCutMxn(cut.difference_cents)}</dd></div>}
      </dl>
      {canCreate && cut.status === 'DRAFT' && (
        <form onSubmit={(event) => { event.preventDefault(); onCount(cut); }}>
          <label>
            Efectivo contado (MXN)
            <input value={countedInput} inputMode="decimal" onChange={(event) => onCountedInput(event.target.value)} />
          </label>
          <button type="submit" disabled={commandState === 'submitting'}>Confirmar contado</button>
        </form>
      )}
      {canCreate && cut.status === 'COUNTED' && <button type="button" disabled={commandState === 'submitting'} onClick={() => onFinalize(cut)}>Finalizar corte</button>}
      {canReopenRequest && cut.status === 'FINALIZED' && mayRequestReopen && (
        <form onSubmit={(event) => { event.preventDefault(); onRequestReopen(cut); }}>
          <h4>Solicitar reapertura</h4>
          <label>
            Efectivo corregido (MXN)
            <input value={reopenCountedInput} inputMode="decimal" onChange={(event) => onReopenCountedInput(event.target.value)} />
          </label>
          <label>
            Motivo
            <textarea value={reopenReason} onChange={(event) => onReopenReason(event.target.value)} />
          </label>
          <label>
            Evidencias (una referencia por línea)
            <textarea value={reopenEvidence} onChange={(event) => onReopenEvidence(event.target.value)} />
          </label>
          <button type="submit" disabled={commandState === 'submitting'}>Solicitar reapertura</button>
        </form>
      )}
      {canReopenAuthorize && detail.reopen?.status === 'REQUESTED' && (
        <section aria-label="Decisión de reapertura">
          <button type="button" disabled={commandState === 'submitting'} onClick={() => onDecideReopen(cut, detail.reopen!.id, 'approve')}>Aprobar reapertura</button>
          <button type="button" disabled={commandState === 'submitting'} onClick={() => onDecideReopen(cut, detail.reopen!.id, 'reject')}>Rechazar reapertura</button>
        </section>
      )}
      {canReopenAuthorize && detail.reopen?.status === 'APPROVED' && <button type="button" disabled={commandState === 'submitting'} onClick={() => onCompensateReopen(cut, detail.reopen!.id)}>Compensar reapertura</button>}
      <h4>Operaciones asociadas</h4>
      <ul>
        {detail.operations.map((operation) => (
          <li key={operation.operation_id}>{operation.operation_type}: {formatCashCutMxn(operation.signed_amount_cents)}</li>
        ))}
      </ul>
    </article>
  );
}
