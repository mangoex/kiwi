import React, { useEffect, useState } from 'react';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { resolvePosBranchId, usePosSession } from '../../session';
import {
  cashMovementCapabilities,
  nextCashIdempotencyKey,
  parseCashCents,
} from './cashMovementForm';

type Concept = { concept_id: string; name: string; code: string };
type CurrentShift = { cash_shift: { id: string } | null };
type LedgerItem = { id: string; movement_type: string; amount_cents: number; reason: string };
type Ledger = { items: LedgerItem[]; next_cursor: string | null };

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

  useEffect(() => {
    if (!capabilities.canRead || !branchId) return;
    setLedgerLoading(true);
    void fetchApi<Ledger>(`/cash/movements?branch_id=${encodeURIComponent(branchId)}&limit=25`)
      .then(data => setLedger(data.items))
      .catch(() => setStatus('No se pudo cargar el ledger de caja.'))
      .finally(() => setLedgerLoading(false));
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

  async function submit(event: React.FormEvent) {
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
      await fetchApi('/cash/movements', {
        method: 'POST', headers: { 'Idempotency-Key': commandKey },
        body: JSON.stringify({ branch_id: branchId, register_id: registerId, movement_type: type, concept_id: concept, amount_cents: cents, reference: reference.trim(), evidence_refs: [evidence.trim()] }),
      });
      setAmount(''); setReference(''); setEvidence(''); setKey(null); setStatus('Movimiento confirmado.');
    } catch (error) {
      if (error instanceof ApiError && error.code === 'idempotency_conflict') {
        setKey(null); setStatus('La solicitud cambió y fue rechazada; genera una nueva intención.');
      } else setStatus('Operación no confirmada. Reintenta con la misma intención.');
    } finally { setLoading(false); }
  }

  return <section style={{ maxWidth: 620, margin: '2rem auto', padding: '1.5rem' }}>
    <h1>Movimientos de caja</h1>
    {capabilities.canRead && <section aria-label="Ledger de caja">
      <h2>Ledger</h2>
      {ledgerLoading && <p role="status">Cargando ledger…</p>}
      {!ledgerLoading && !ledger.length && <p role="status">No hay movimientos para esta sucursal.</p>}
      <ul>{ledger.map(item => <li key={item.id}>{item.movement_type}: ${centsToMxn(item.amount_cents)} — {item.reason}</li>)}</ul>
    </section>}
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
    {status && <p role={status.includes('no confirmada') || status.includes('rechazada') ? 'alert' : 'status'}>{status}</p>}
  </section>;
}
