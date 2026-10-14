import React, { useEffect, useRef, useState } from 'react';
import {
  ApiError, listPendingOperationalIntents, resolveOperationalIntent,
  subscribeToOperationalIntentChange, type OperationalIntentReceipt,
} from '@restaurantos/api-client';

const credential = () => localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
const labels: Record<OperationalIntentReceipt['kind'], string> = {
  'order.create': 'Pedido', 'payment.confirm': 'Pago', 'cash.movement.create': 'Movimiento de caja',
  'cash.shift.open': 'Apertura de caja', 'cash.shift.close': 'Cierre de caja',
  'cash.shift.close.register': 'Cierre de caja', 'cash.movement.compensate': 'Compensación de caja',
};

/** Own minimum receipts remain recoverable when an operational context cannot be issued. */
export default function OperationalIntentRecovery({sessionIdentity}: {sessionIdentity: object | null}) {
  const [pending, setPending] = useState<OperationalIntentReceipt[]>([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [recovering, setRecovering] = useState<string | null>(null);
  const boundCredential = useRef<string | null>(null);
  const generation = useRef(0);

  useEffect(() => {
    const current = credential();
    boundCredential.current = current;
    const ticket = ++generation.current;
    let sequence = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const stillCurrent = () => ticket === generation.current && credential() === current;
    setPending([]); setMessage(''); setError(''); setRecovering(null);
    const refresh = async () => {
      const request = ++sequence;
      if (!current || !stillCurrent()) return;
      try {
        const rows = await listPendingOperationalIntents();
        if (stillCurrent() && request === sequence) {setPending(rows); setError('');}
      } catch (reason) {
        if (stillCurrent() && request === sequence) {
          setError(reason instanceof ApiError ? reason.message : 'No se pudieron consultar las operaciones pendientes.');
        }
      }
    };
    const schedule = () => {clearTimeout(timer); timer = setTimeout(() => {void refresh();}, 200);};
    const focus = () => {void refresh();};
    const storage = () => {if (!stillCurrent()) {sequence++; setPending([]); setMessage(''); setError('');}};
    void refresh();
    const unsubscribe = subscribeToOperationalIntentChange(schedule);
    window.addEventListener('focus', focus); window.addEventListener('storage', storage);
    return () => {
      generation.current++; clearTimeout(timer); unsubscribe();
      window.removeEventListener('focus', focus); window.removeEventListener('storage', storage);
    };
  }, [sessionIdentity]);

  const renderCredential = credential(), renderGeneration = generation.current;
  const recover = async (intent: OperationalIntentReceipt) => {
    const current = credential(), ticket = renderGeneration;
    if (!current || current !== renderCredential || ticket !== generation.current
      || current !== boundCredential.current || recovering) return;
    setRecovering(intent.id); setError(''); setMessage('');
    try {
      const result = await resolveOperationalIntent(intent.id);
      if (ticket !== generation.current || credential() !== current) return;
      const acknowledged = result?.state === 'acknowledged'
        && typeof result.resource_id === 'string'
        && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(result.resource_id)
        && (intent.resource_id === null || result.resource_id === intent.resource_id);
      const noEffect = result?.state === 'no_effect' && result.resource_id === null
        && intent.state === 'prepared' && intent.resource_id === null;
      if (!result || result.id !== intent.id || result.kind !== intent.kind
        || result.branch_id !== intent.branch_id || (!acknowledged && !noEffect)) {
        throw new ApiError(503, 'operational_command_receipt_invalid', 'El servidor no confirmó un resultado final. La recuperación sigue pendiente.');
      }
      setPending(rows => rows.filter(row => row.id !== intent.id));
      setMessage(acknowledged
        ? `${labels[intent.kind]} confirmado. Se recuperó su resultado; consulta el historial antes de repetirlo.`
        : 'El servidor confirmó que esta intención no produjo efectos. Puedes recapturarla con un comando nuevo.');
    } catch (reason) {
      if (ticket === generation.current && credential() === current) {
        setError(reason instanceof ApiError ? reason.message : 'La recuperación sigue pendiente. Reintenta al reconectar.');
      }
    } finally {
      if (ticket === generation.current && credential() === current) setRecovering(null);
    }
  };

  if (!pending.length && !message && !error) return null;
  return <section aria-label="Recuperación de operaciones" style={{margin:16,padding:16,border:'1px solid #d97706',borderRadius:8,background:'#fffbeb',maxWidth:720,width:'calc(100% - 32px)',boxSizing:'border-box'}}>
    {Boolean(pending.length) && <>
      <h2 style={{marginTop:0,fontSize:18}}>Recupera las operaciones pendientes</h2>
      <p>Consulta el resultado del servidor antes de cambiar de sucursal o repetir una operación.</p>
      <ul style={{paddingLeft:20}}>{pending.map(intent => <li key={intent.id} style={{marginTop:12}}>
        <span>{labels[intent.kind]} · {intent.state === 'applied' ? 'Efecto confirmado' : 'Resultado pendiente'}</span>{' '}
        <button style={{minHeight:44,padding:'8px 16px'}} disabled={Boolean(recovering)} onClick={() => {void recover(intent);}}>
          {recovering === intent.id ? 'Recuperando…' : 'Recuperar resultado'}
        </button>
      </li>)}</ul>
    </>}
    {message && <p role="status">{message}</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
