import React, { useEffect, useReducer, useState } from 'react';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { resolvePosBranchId, usePosSession } from '../../session';
import {
  buildCashCompensationPayload,
  canCompensateLedgerItem,
  cashCompensationStateLabel,
  cashMovementCapabilities,
  cashMovementTypeLabel,
  initialCashCompensationFormState,
  type CashCompensationState,
  nextCashIdempotencyKey,
  parseCashCents,
  reduceCashCompensationFormState,
} from './cashMovementForm';

type Concept = { concept_id: string; name: string; code: string };
type CurrentShift = { cash_shift: { id: string } | null };
type CashSummary = { expected_cash_cents: number };
type LedgerItem = {
  id: string;
  movement_type: string;
  amount_cents: number;
  reason: string;
  compensation_state: CashCompensationState;
  compensated_by_movement_id: string | null;
};
type Ledger = { items: LedgerItem[]; next_cursor: string | null };
type CashMovementResponse = { current_summary: CashSummary };

export { parseCashCents } from './cashMovementForm';

function centsToMxn(cents: number) {
  return (cents / 100).toFixed(2);
}

export default function CashMovements() {
  const { hasPermission } = usePosSession();
  const capabilities = cashMovementCapabilities({
    canRead: hasPermission('cash.movement.read'),
    canWithdraw: hasPermission('cash.movement.withdraw'),
    canDeposit: hasPermission('cash.movement.deposit'),
    canCompensate: hasPermission('cash.movement.compensate'),
  });
  const branchId = resolvePosBranchId();
  const registerId = localStorage.getItem('pos_register_id') || '';
  const [type, setType] = useState<'withdrawal' | 'deposit'>(capabilities.initialType);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [ledger, setLedger] = useState<LedgerItem[]>([]);
  const [amount, setAmount] = useState('');
  const [reference, setReference] = useState('');
  const [evidence, setEvidence] = useState('');
  const [key, setKey] = useState<string | null>(null);
  const [compensation, dispatchCompensation] = useReducer(
    reduceCashCompensationFormState<LedgerItem>,
    undefined,
    initialCashCompensationFormState<LedgerItem>,
  );
  const [currentSummary, setCurrentSummary] = useState<CashSummary | null>(null);
  const [shiftReady, setShiftReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [ledgerLoading, setLedgerLoading] = useState(false);
  const [status, setStatus] = useState('');

  useEffect(() => {
    if (!capabilities.canWrite) return;
    if ((type === 'withdrawal' && !capabilities.canWithdraw) || (type === 'deposit' && !capabilities.canDeposit)) {
      setType(capabilities.initialType);
    }
  }, [
    capabilities.canDeposit,
    capabilities.canWithdraw,
    capabilities.canWrite,
    capabilities.initialType,
    type,
  ]);

  async function refreshLedger(): Promise<boolean> {
    if (!capabilities.canRead || !branchId) return false;
    setLedgerLoading(true);
    try {
      const data = await fetchApi<Ledger>(
        `/cash/movements?branch_id=${encodeURIComponent(branchId)}&limit=25`,
      );
      setLedger(data.items);
      return true;
    } catch {
      setStatus('No se pudo cargar el ledger de caja.');
      return false;
    } finally {
      setLedgerLoading(false);
    }
  }

  useEffect(() => {
    void refreshLedger();
  }, [branchId, capabilities.canRead]);

  useEffect(() => {
    if (!capabilities.canWrite || !branchId || !registerId) return;
    setShiftReady(false);
    void fetchApi<CurrentShift>(`/cash-shifts/current?branch_id=${encodeURIComponent(branchId)}&register_id=${encodeURIComponent(registerId)}`)
      .then(data => setShiftReady(Boolean(data.cash_shift)))
      .catch(() => setStatus('No se pudo verificar el turno actual.'));
  }, [branchId, capabilities.canWrite, registerId]);

  useEffect(() => {
    if (!capabilities.canWrite || !shiftReady) return;
    setConcepts([]);
    void fetchApi<Concept[]>(`/cash/concepts/effective?branch_id=${encodeURIComponent(branchId)}&movement_type=${type}`)
      .then(setConcepts)
      .catch(() => setStatus('No se pudieron cargar conceptos.'));
  }, [branchId, capabilities.canWrite, shiftReady, type]);

  if (!capabilities.canUse) return null;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cents = parseCashCents(amount);
    const concept = (event.currentTarget.elements.namedItem('concept_id') as HTMLSelectElement).value;
    if (!cents || !concept || !reference.trim() || !evidence.trim() || !shiftReady) {
      setStatus('Captura los datos requeridos y confirma un turno abierto.');
      return;
    }
    const commandKey = nextCashIdempotencyKey(key);
    setKey(commandKey);
    setLoading(true);
    setStatus('Registrando…');
    try {
      const result = await fetchApi<CashMovementResponse>('/cash/movements', {
        method: 'POST', headers: { 'Idempotency-Key': commandKey },
        body: JSON.stringify({ branch_id: branchId, register_id: registerId, movement_type: type, concept_id: concept, amount_cents: cents, reference: reference.trim(), evidence_refs: [evidence.trim()] }),
      });
      setCurrentSummary(result.current_summary);
      const refreshed = await refreshLedger();
      setAmount(''); setReference(''); setEvidence(''); setKey(null);
      setStatus(refreshed ? 'Movimiento confirmado.' : 'Movimiento confirmado; actualiza el ledger.');
    } catch (error) {
      if (error instanceof ApiError && error.code === 'idempotency_conflict') {
        setKey(null); setStatus('La solicitud cambió y fue rechazada; genera una nueva intención.');
      } else setStatus('Operación no confirmada. Reintenta con la misma intención.');
    } finally { setLoading(false); }
  }

  async function submitCompensation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const intent = compensation.intent;
    if (!intent) return;
    const payload = buildCashCompensationPayload(intent.reason, intent.evidence);
    if (!payload.reason || !payload.evidence_refs[0]) {
      setStatus('Captura motivo y evidencia para compensar.');
      return;
    }
    const commandKey = nextCashIdempotencyKey(intent.idempotencyKey);
    dispatchCompensation({ type: 'begin_submit', idempotencyKey: commandKey });
    setStatus('Compensando…');
    try {
      const result = await fetchApi<CashMovementResponse>(
        `/cash/movements/${encodeURIComponent(intent.target.id)}/compensations`,
        {
          method: 'POST',
          headers: { 'Idempotency-Key': commandKey },
          body: JSON.stringify(payload),
        },
      );
      setCurrentSummary(result.current_summary);
      const refreshed = await refreshLedger();
      dispatchCompensation({ type: 'complete' });
      setStatus(refreshed ? 'Movimiento compensado.' : 'Movimiento compensado; actualiza el ledger.');
    } catch (error) {
      if (error instanceof ApiError && error.code === 'idempotency_conflict') {
        dispatchCompensation({ type: 'complete' });
        setStatus('La compensación cambió y fue rechazada; genera una nueva intención.');
      } else {
        dispatchCompensation({ type: 'uncertain_failure' });
        setStatus('Compensación no confirmada. Reintenta con la misma intención.');
      }
    }
  }

  return <section style={{ maxWidth: 620, margin: '2rem auto', padding: '1.5rem' }}>
    <h1>Movimientos de caja</h1>
    {capabilities.canRead && <section aria-label="Ledger de caja">
      <h2>Ledger</h2>
      {ledgerLoading && <p role="status">Cargando ledger…</p>}
      {!ledgerLoading && !ledger.length && <p role="status">No hay movimientos para esta sucursal.</p>}
      <ul>{ledger.map(item => <li key={item.id}>
        {cashMovementTypeLabel(item.movement_type)}: ${centsToMxn(item.amount_cents)} — {item.reason}
        <span> · Estado: {cashCompensationStateLabel(item.compensation_state)}</span>
        {item.compensated_by_movement_id && <span> · Compensado por: {item.compensated_by_movement_id}</span>}
        {canCompensateLedgerItem(capabilities.canCompensate, item.compensation_state) && <button type="button" onClick={() => dispatchCompensation({ type: 'open', target: item })} disabled={compensation.loading}>Compensar</button>}
      </li>)}</ul>
    </section>}
    {currentSummary && <p role="status">Efectivo esperado: ${centsToMxn(currentSummary.expected_cash_cents)}</p>}
    {!capabilities.canWrite && <p role="status">Tu perfil sólo puede consultar el ledger de caja.</p>}
    {capabilities.canWrite && <>
      {!registerId && <p role="alert">Configura la caja POS antes de registrar movimientos.</p>}
      {!loading && shiftReady && !concepts.length && <p role="status">No hay conceptos efectivos para este tipo.</p>}
      <form onSubmit={submit} style={{ display: 'grid', gap: 12 }}>
        <label>Tipo<select value={type} onChange={e => setType(e.target.value as 'withdrawal' | 'deposit')}>
          <option value="withdrawal" disabled={!capabilities.canWithdraw}>Retiro</option>
          <option value="deposit" disabled={!capabilities.canDeposit}>Depósito</option>
        </select></label>
        <label>Concepto<select name="concept_id" required disabled={!shiftReady || loading}>{concepts.map(c => <option value={c.concept_id} key={c.concept_id}>{c.code} — {c.name}</option>)}</select></label>
        <label>Importe (MXN)<input value={amount} onChange={e => setAmount(e.target.value)} inputMode="decimal" maxLength={18} required /></label>
        <label>Referencia<input value={reference} onChange={e => setReference(e.target.value)} maxLength={600} required /></label>
        <label>Evidencia<input value={evidence} onChange={e => setEvidence(e.target.value)} maxLength={600} required /></label>
        <button type="submit" disabled={loading || !shiftReady || !concepts.length}>Confirmar movimiento</button>
      </form>
    </>}
    {compensation.intent && <form aria-label="Compensar movimiento" onSubmit={submitCompensation} style={{ display: 'grid', gap: 12, marginTop: 20 }}>
      <h2>Compensar movimiento</h2>
      <p>Se compensará {cashMovementTypeLabel(compensation.intent.target.movement_type)}: ${centsToMxn(compensation.intent.target.amount_cents)}.</p>
      <label>Motivo<input value={compensation.intent.reason} onChange={e => dispatchCompensation({ type: 'set_reason', reason: e.target.value })} maxLength={600} required disabled={compensation.loading} /></label>
      <label>Evidencia<input value={compensation.intent.evidence} onChange={e => dispatchCompensation({ type: 'set_evidence', evidence: e.target.value })} maxLength={600} required disabled={compensation.loading} /></label>
      <button type="submit" disabled={compensation.loading}>Confirmar compensación</button>
      <button type="button" onClick={() => dispatchCompensation({ type: 'cancel' })} disabled={compensation.loading}>Cancelar</button>
    </form>}
    {status && <p role={status.includes('no confirmada') || status.includes('rechazada') ? 'alert' : 'status'}>{status}</p>}
  </section>;
}
