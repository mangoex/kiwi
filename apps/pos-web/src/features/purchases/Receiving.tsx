import {useEffect,useRef,useState} from 'react';
import {ApiError,fetchApi,financialAccessForBranch} from '@restaurantos/api-client';
import {Button} from '@restaurantos/ui';
import {usePosSession} from '../../session';
import {parseReceivingPage,parseReceivingReceipt,receivingLines,receivingRejectedBeforeEffects,type ReceivingOrder} from './receivingContract';

interface PendingReceipt {authority:string;branch:string;order:string;key:string;body:{branch_id:string;warehouse_id:string;expected_version:number;discrepancy_reason:string;lines:{allocation_id:string;quantity:string}[]}}
function readPending(storageKey:string):PendingReceipt|null {
  const raw=sessionStorage.getItem(storageKey);if(raw===null)return null;
  if(raw.length>100000)throw new Error('No se puede verificar la recepción pendiente.');
  const row=JSON.parse(raw) as PendingReceipt;
  if(!row || Object.keys(row).sort().join()!==['authority','branch','order','key','body'].sort().join()
    || typeof row.authority!=='string' || typeof row.branch!=='string' || typeof row.order!=='string'
    || typeof row.key!=='string' || !row.body || row.body.branch_id!==row.branch
    || !Number.isSafeInteger(row.body.expected_version) || !Array.isArray(row.body.lines))throw new Error('No se puede verificar la recepción pendiente.');
  return row;
}
export default function Receiving() {
  const {session,hasPermission}=usePosSession();const branch=session?.active_branch?.id || '';
  const access=session?financialAccessForBranch(session,branch):null;
  const authority=JSON.stringify([session?.user.id,branch]);
  const storageKey=`pos_receiving_pending_v2:${authority}`;
  const allowed=access?.state==='active' && hasPermission('purchases.receive');
  const [orders,setOrders]=useState<ReceivingOrder[]>([]);const [cursor,setCursor]=useState<string|null>(null);
  const [selected,setSelected]=useState<ReceivingOrder|null>(null);const [warehouse,setWarehouse]=useState('');
  const [values,setValues]=useState<Record<string,string>>({});const [reason,setReason]=useState('');
  const [pending,setPending]=useState<PendingReceipt|null>(null);const [blocked,setBlocked]=useState(false);
  const [error,setError]=useState('');const [receipt,setReceipt]=useState('');const [busy,setBusy]=useState(false);
  const lock=useRef(false);const generation=useRef(0);
  async function load(next:string|null=null) {
    const token=++generation.current;if(!allowed)return;
    try{const query=new URLSearchParams({branch_id:branch,limit:'25'});if(next)query.set('cursor',next);
      const page=parseReceivingPage(await fetchApi(`/purchases/receiving?${query}`,{},'v2'),branch,access!.policy_version!);
      if(token!==generation.current)return;setOrders(previous=>next?[...previous,...page.items]:page.items);setCursor(page.next_cursor);
    }catch(failure){if(token===generation.current){setOrders([]);setCursor(null);setError(String(failure));}}
  }
  useEffect(()=>{try{setPending(readPending(storageKey));}catch(failure){setBlocked(true);setError(String(failure));}void load();return()=>{generation.current++;};},[branch,access?.policy_version,allowed,storageKey]);
  const lines=selected?.lines.filter(line=>line.warehouse_id===warehouse) || [];
  async function receive() {
    if(lock.current || blocked || !allowed)return;lock.current=true;setBusy(true);setError('');setReceipt('');let intent=pending;
    try{
      if(!intent){if(!selected || !warehouse)throw new Error('Selecciona una orden y almacén.');
        const items=receivingLines(lines,values);if(!items.length)throw new Error('Captura al menos una cantidad recibida.');
        if(!reason.trim() && lines.some(line=>Number(values[line.allocation_id] || '0')<Number(line.pending_quantity)))throw new Error('Indica el motivo de la entrega parcial.');
        intent={authority,branch,order:selected.id,key:crypto.randomUUID(),body:{branch_id:branch,warehouse_id:warehouse,
          expected_version:selected.version,discrepancy_reason:reason.trim(),lines:items}};
        if(readPending(storageKey))throw new Error('Recupera primero la recepción pendiente.');
        const raw=JSON.stringify(intent);sessionStorage.setItem(storageKey,raw);
        if(sessionStorage.getItem(storageKey)!==raw)throw new Error('No se pudo conservar la recepción.');setPending(intent);
      }
      if(intent.authority!==authority || intent.branch!==branch)throw new Error('Recupera esta recepción en su cuenta y sucursal originales.');
      const result=await fetchApi(`/corporate-purchases/${encodeURIComponent(intent.order)}/receipts`,{method:'POST',headers:{'Idempotency-Key':intent.key},body:JSON.stringify(intent.body)});
      const identifier=parseReceivingReceipt(result,branch,access!.policy_version!,intent.order);
      sessionStorage.removeItem(storageKey);setPending(null);setReceipt(identifier);setSelected(null);setValues({});setReason('');await load();
    }catch(failure){
      // A central rejection before effects permits correction; an unknown outcome keeps the same key.
      if(failure instanceof ApiError && receivingRejectedBeforeEffects(failure)){
        sessionStorage.removeItem(storageKey);setPending(null);
        setSelected(null);setValues({});await load();
      }
      setError(failure instanceof Error?failure.message:'No se pudo confirmar la recepción.');
    }finally{lock.current=false;setBusy(false);}
  }
  if(!allowed)return <main><h1>Recepción de compras</h1><p role="alert">Se requiere recepción autorizada y política activa en esta sucursal.</p></main>;
  return <main className="sales-monitor-page"><h1>Recepción de compras</h1><p>Compara la entrega con la orden. Registra cantidades y el motivo de cualquier diferencia.</p>
    {error && <p role="alert">{error}</p>}{receipt && <p role="status">Recepción confirmada. Acuse {receipt}</p>}
    {pending ? <section><h2>Recepción pendiente de confirmar</h2><p>Orden {pending.order}. Conservamos las cantidades originales para evitar duplicarlas.</p>
      <ul>{pending.body.lines.map(line=><li key={line.allocation_id}>{line.quantity} · partida {line.allocation_id}</li>)}</ul><p>{pending.body.discrepancy_reason}</p>
      <Button disabled={busy || blocked || pending.authority!==authority} onClick={()=>void receive()}>Recuperar recepción</Button></section> : <>
      <Button disabled={busy} variant="secondary" onClick={()=>void load()}>Actualizar órdenes</Button>
      <ul>{orders.map(order=><li key={order.id}><Button variant="secondary" onClick={()=>{setSelected(order);setWarehouse(order.lines[0]?.warehouse_id || '');setValues({});setReason('');setError('');}}>{order.folio} · {order.status}</Button></li>)}</ul>
      {cursor && <Button onClick={()=>void load(cursor)}>Cargar más</Button>}
      {selected && <form onSubmit={event=>{event.preventDefault();void receive();}}><h2>{selected.folio}</h2>
        <label>Almacén<select value={warehouse} onChange={event=>{setWarehouse(event.target.value);setValues({});}}>{[...new Set(selected.lines.map(line=>line.warehouse_id))].map(id=><option key={id} value={id}>{id}</option>)}</select></label>
        {lines.map(line=><label key={line.allocation_id} style={{display:'block',margin:'16px 0'}}>{line.item_name} · {line.presentation_name} · pendiente {Number(line.pending_quantity).toFixed(2)}
          <input aria-label={`Recibido ${line.item_name}`} inputMode="decimal" value={values[line.allocation_id] || ''} disabled={busy}
            onChange={event=>setValues(previous=>({...previous,[line.allocation_id]:event.target.value}))}/></label>)}
        <label>Motivo de diferencia<textarea value={reason} maxLength={1000} disabled={busy} onChange={event=>setReason(event.target.value)}/></label>
        <Button type="submit" disabled={busy || blocked}>Confirmar recepción</Button></form>}
    </>}
  </main>;
}
