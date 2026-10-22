import {useEffect, useRef, useState} from 'react';
import {ApiError, fetchApi, type BranchFinancialAccess} from '@restaurantos/api-client';
import {cashRecord, parseCashReceipt, parseOperationalCutPage, parseOperationalShift,
  type CashReceipt, type OperationalCut, type OperationalShift} from './cashProjections';
import {formatCashCutMxn, parseUserCashCut, type UserCashCutView} from './userCashCuts';
import {parseExactCents} from './shiftOperations';
import {clearShiftIntent,loadShiftIntent,saveShiftIntent,type ShiftIntent} from './cashShiftIntent';

const message = (error: unknown) => error instanceof ApiError && error.code === 'cash_policy_suspended'
  ? 'La operación de caja está suspendida. Contacta al Dueño.'
  : 'No se pudo verificar la información. Actualiza la sesión antes de continuar.';
const time = (value: string, timezone: string) => new Intl.DateTimeFormat('es-MX', {
  timeZone:timezone,dateStyle:'medium',timeStyle:'short',
}).format(new Date(value));

export function OperationalCutsPanel({access, registerId, timezone}: {
  access: BranchFinancialAccess; registerId: string; timezone: string;
}) {
  const [items,setItems] = useState<OperationalCut[]>([]);
  const [cursor,setCursor] = useState<string|null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [financial,setFinancial] = useState<UserCashCutView|null>(null);
  const [hasCompensations,setHasCompensations] = useState(false);
  const request = useRef<AbortController|null>(null);
  const seen = useRef(new Set<string>());
  const allowed = access.state === 'active' && access.capabilities['cash.user_cut.operational.read'];
  const revision = access.policy_version!;
  async function load(next: string|null = null) {
    if (!allowed) return;
    request.current?.abort(); const controller = new AbortController(); request.current = controller;
    setBusy(true); setError(''); setFinancial(null);
    try {
      const params = new URLSearchParams({branch_id:access.branch_id,register_id:registerId,limit:'50'});
      if(next) params.set('cursor',next);
      const page = parseOperationalCutPage(await fetchApi(`/cash/user-cuts?${params}`,{signal:controller.signal},'v2'),access.branch_id,revision);
      if(controller.signal.aborted) return;
      if(page.next_cursor && seen.current.has(page.next_cursor)) throw new Error('Cursor repetido');
      if(!next) seen.current.clear();
      if(page.next_cursor) seen.current.add(page.next_cursor);
      setItems(previous => next ? [...previous,...page.items] : page.items); setCursor(page.next_cursor);
    } catch(reason) { if(!controller.signal.aborted) {setItems([]);setCursor(null);setError(message(reason));} }
    finally {if(!controller.signal.aborted) setBusy(false);}
  }
  useEffect(() => {void load();return () => request.current?.abort();},[access.branch_id,revision,registerId,allowed]);
  async function readFinancial(id: string) {
    if(!allowed || !access.datasets.includes('cash.cuts')) return;
    request.current?.abort(); const controller = new AbortController(); request.current = controller;
    setFinancial(null); setError(''); setBusy(true);
    try {
      const value = cashRecord(await fetchApi(`/financial/cash/user-cuts/${encodeURIComponent(id)}`,{signal:controller.signal},'v2'),
        ['projection','schema_version','policy_version','cash_cut','operations','compensations']);
      if(value.projection !== 'financial' || value.schema_version !== 2 || value.policy_version !== revision
        || !Array.isArray(value.operations) || !Array.isArray(value.compensations)) throw new Error('Contrato financiero inválido');
      const cut = parseUserCashCut(value.cash_cut);
      if(cut.id !== id || cut.branch_id !== access.branch_id) throw new Error('Corte fuera de alcance');
      if(!controller.signal.aborted) {setFinancial(cut);setHasCompensations(value.compensations.length > 0);}
    } catch(reason) {if(!controller.signal.aborted) setError(message(reason));}
    finally {if(!controller.signal.aborted) setBusy(false);}
  }
  if(access.state === 'suspended') return <p role="alert">La operación de caja está suspendida. Contacta al Dueño.</p>;
  if(!allowed) return <p>No tienes permiso para consultar cortes de esta sucursal.</p>;
  return <section aria-label="Cortes operativos">
    <h2>Cortes por usuario</h2>
    <p>Consulta el estado de cada corte. La nueva captura y finalización aún no están habilitadas.</p>
    <button type="button" disabled={busy} onClick={() => void load()}>Actualizar cortes</button>
    {error && <p role="alert">{error}</p>}
    {busy && <p role="status">Consultando…</p>}
    {!busy && !error && items.length === 0 && <p>No hay cortes para esta caja.</p>}
    <ul>{items.map(cut => <li key={cut.id}>
      <strong>{cut.register_id} · {cut.status}</strong> · Responsable: {cut.responsible_user_id}
      <p>Creado: <time dateTime={cut.created_at}>{time(cut.created_at,timezone)}</time></p>
      {access.datasets.includes('cash.cuts') && <button type="button" disabled={busy}
        onClick={() => void readFinancial(cut.id)}>Consultar resultado financiero</button>}
    </li>)}</ul>
    {cursor && <button type="button" disabled={busy} onClick={() => void load(cursor)}>Cargar más</button>}
    {financial && <section aria-label="Resultado financiero autorizado">
      <h3>Resultado registrado del corte</h3>
      <p>{financial.id}</p>
      <dl>{([['Esperado',financial.expected_cash_cents],['Declarado',financial.counted_cash_cents],['Diferencia',financial.difference_cents]] as const)
        .map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value === null ? 'Sin registro' : formatCashCutMxn(value)}</dd></div>)}</dl>
      {hasCompensations && <p role="status">Este corte tiene compensaciones posteriores. Los importes mostrados corresponden al registro original.</p>}
      <button type="button" onClick={() => setFinancial(null)}>Ocultar resultado</button>
    </section>}
  </section>;
}

export function OperationalShiftPanel({access,registerId,onRegisterChange,permissions,timezone,actorId,organizationId}: {
  access: BranchFinancialAccess; registerId:string; onRegisterChange:(value:string)=>void;
  permissions:readonly string[]; timezone:string; actorId:string; organizationId:string;
}) {
  const [shift,setShift] = useState<OperationalShift|null>(null);
  const [receipt,setReceipt] = useState<CashReceipt|null>(null);
  const [opening,setOpening] = useState('');
  const [busy,setBusy] = useState(false);
  const [loaded,setLoaded] = useState(false);
  const [error,setError] = useState('');
  const [intent,setIntent] = useState<ShiftIntent|null>(null);
  const lock = useRef(false);
  const request = useRef<AbortController|null>(null);
  const scope = {organization:organizationId,actor:actorId,branch:access.branch_id,register:registerId};
  const [recoveryBlocked,setRecoveryBlocked] = useState(false);
  const revision = access.policy_version!;
  const allowed = access.state === 'active' && permissions.includes('cash.shift.read');
  async function load() {
    if(!allowed) return;
    request.current?.abort(); const controller = new AbortController(); request.current = controller;
    setLoaded(false); setShift(null);setBusy(true);setError('');
    try {
      const params = new URLSearchParams({branch_id:access.branch_id,register_id:registerId});
      const value = cashRecord(await fetchApi(`/cash/shifts/current?${params}`,{signal:controller.signal},'v2'),['cash_shift']);
      const result = value.cash_shift === null ? null : parseOperationalShift(value.cash_shift,access.branch_id,revision);
      if(result && result.register_id !== registerId) throw new Error('Caja fuera de alcance');
      if(!controller.signal.aborted) {setShift(result);setLoaded(true);}
    } catch(reason) {if(!controller.signal.aborted) setError(message(reason));}
    finally {if(!controller.signal.aborted) setBusy(false);}
  }
  useEffect(() => {
    try {setIntent(loadShiftIntent(scope));setRecoveryBlocked(false);}
    catch {setRecoveryBlocked(true);setError('La solicitud pendiente requiere revisión antes de operar esta caja.');}
    void load();return () => request.current?.abort();
  },[access.branch_id,revision,registerId,allowed,actorId,organizationId]);
  async function execute(command: ShiftIntent) {
    if(lock.current || !allowed || recoveryBlocked) return;
    lock.current = true;setBusy(true);setError('');setReceipt(null);setIntent(command);
    try {
      saveShiftIntent(scope,command);
      const endpoint = command.action === 'open' ? '/cash/shifts/open'
        : `/cash/shifts/${encodeURIComponent(command.resource!)}/close-operationally`;
      const result = parseCashReceipt(await fetchApi(endpoint,{method:'POST',headers:{'Idempotency-Key':command.key},
        body:JSON.stringify(command.payload)},'v2'),revision,command.action,command.resource);
      clearShiftIntent(scope,command.key);
      setReceipt(result);setIntent(null); await load();
    } catch(reason) {
      // Uncertain writes retain their exact key and payload; reading never retries a command.
      if(reason instanceof ApiError && reason.code === 'operational_command_terminal') {
        clearShiftIntent(scope,command.key);setIntent(null);
      }
      setLoaded(false);setError('No se confirmó la operación. Verifica el estado o reintenta la misma solicitud.');
    } finally {lock.current = false;setBusy(false);}
  }
  function open() {
    const cents = parseExactCents(opening);
    if(cents === null) {setError('Captura el fondo con máximo dos decimales.');return;}
    if(!loaded || shift || !registerId.trim() || !permissions.includes('cash.shift.open')) return;
    void execute({action:'open',key:crypto.randomUUID(),payload:{branch_id:access.branch_id,register_id:registerId,opening_cash_cents:cents}});
  }
  if(access.state === 'suspended') return <p role="alert">La operación de caja está suspendida. Contacta al Dueño.</p>;
  if(!allowed) return <p>No tienes permiso para consultar turnos de esta sucursal.</p>;
  return <section aria-label="Turno operativo">
    <h2>Turno y caja</h2>
    <label>Caja <input value={registerId} disabled={busy || !!shift || !!intent || recoveryBlocked}
      onChange={event => onRegisterChange(event.target.value)} /></label>
    <button type="button" disabled={busy || !!intent} onClick={() => void load()}>Actualizar estado</button>
    {busy && <p role="status">Verificando operación…</p>}
    {error && <p role="alert">{error}</p>}
    {recoveryBlocked && <p role="alert">Hay evidencia local pendiente que no se pudo validar. La operación permanece bloqueada.</p>}
    {loaded && <p>{shift ? `Turno abierto · ${time(shift.opened_at,timezone)}` : 'Sin turno abierto'}</p>}
    {loaded && !shift && !intent && !recoveryBlocked && permissions.includes('cash.shift.open') && <div>
      <label>Fondo inicial ($ MXN) <input inputMode="decimal" value={opening} onChange={event => setOpening(event.target.value)} disabled={busy}/></label>
      <button type="button" disabled={busy || !registerId.trim()} onClick={open}>Abrir turno</button>
    </div>}
    {loaded && shift && !intent && !recoveryBlocked && permissions.includes('cash.shift.close') && <button type="button" disabled={busy}
      onClick={() => void execute({action:'close',key:crypto.randomUUID(),resource:shift.id,payload:{}})}>Cerrar turno operativamente</button>}
    {intent && <button type="button" disabled={busy} onClick={() => void execute(intent)}>Reintentar la misma solicitud</button>}
    {receipt && <p role="status">{receipt.action === 'open' ? 'Apertura confirmada.' : 'Cierre operativo confirmado. El corte final sigue pendiente.'} Acuse: {receipt.command_id}</p>}
  </section>;
}
