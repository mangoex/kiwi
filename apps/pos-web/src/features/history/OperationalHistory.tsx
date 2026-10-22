import {useEffect,useRef,useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {fetchApi,type BranchFinancialAccess} from '@restaurantos/api-client';
import {Button} from '@restaurantos/ui';
import {usePosSession} from '../../session';
import {parseAttendedOrder,parseOperationalOrders,type AttendedOrder,type OperationalOrder} from './operationalOrders';
import {useCashierOrderRequest} from '../pos/useCashierOrderRequest';
import {CashierPaymentDialog} from '../pos/CashierPaymentDialog';
import {CashierOrderActionDialog} from '../pos/CashierOrderActionDialog';
import {cashierOrderActions} from '../pos/cashierOrderActions';
import {OrderExceptionDialog} from '../pos/OrderExceptionDialog';
import {readExceptionIntent,type ExceptionIntent} from '../pos/orderExceptionIntent';
import {formatMxnCents} from '../pos/cartMoney';

export default function OperationalHistory({access}:{access:BranchFinancialAccess}) {
  const {session,hasPermission}=usePosSession();const navigate=useNavigate();
  const register=(localStorage.getItem('pos_register_id') || '').trim();
  const {request,authority,local,configError}=useCashierOrderRequest(access.branch_id,session!.user.id,register);
  const [rows,setRows]=useState<OperationalOrder[]>([]);const [cursor,setCursor]=useState<string|null>(null);
  const [selected,setSelected]=useState<AttendedOrder|null>(null);const [query,setQuery]=useState('');
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const [pay,setPay]=useState(false);const [fulfill,setFulfill]=useState(false);const [cancel,setCancel]=useState(false);
  const [classification,setClassification]=useState('');const [recovery,setRecovery]=useState<ExceptionIntent|null>(null);
  const sequence=useRef(0);const detailSequence=useRef(0);
  const allowed=access.state==='active' && !local && !configError && hasPermission('orders.read');
  async function load(next:string|null=null) {
    const current=++sequence.current; setBusy(true);setError('');
    if(!allowed){setBusy(false);return;}
    try {
      const params=new URLSearchParams({branch_id:access.branch_id,limit:'25'});
      if(query.trim().length>=2) params.set('q',query.trim());if(next)params.set('cursor',next);
      const page=parseOperationalOrders(await fetchApi(`/orders/accounts?${params}`,{},'v2'),access.branch_id,access.policy_version!);
      if(current!==sequence.current)return;
      if(next && next===page.next_cursor) throw new Error('No se puede avanzar la consulta.');
      setRows(previous=>next?[...previous,...page.items]:page.items);setCursor(page.next_cursor);
    } catch(failure){if(current===sequence.current){setRows([]);setCursor(null);setError(failure instanceof Error?failure.message:'No se pudo consultar.');}}
    finally{if(current===sequence.current)setBusy(false);}
  }
  async function open(row:OperationalOrder) {
    const current=++detailSequence.current;setSelected(null);setClassification('');setError('');
    try {
      const detail=parseAttendedOrder(await fetchApi(`/orders/${encodeURIComponent(row.id)}?expected_version=${row.version}`,{},'v2'),
        access.branch_id,access.policy_version!,row.id,row.version,session!.scope.authorization_version!);
      if(current===detailSequence.current)setSelected(detail);
    } catch {if(current===detailSequence.current)setError('No tienes contexto vigente para consultar este pedido. Actualiza la lista o solicita revisión al encargado.');}
  }
  useEffect(()=>{void load();try{setRecovery(readExceptionIntent());}catch(failure){setError(String(failure));}
    return()=>{sequence.current++;detailSequence.current++;};},[access.branch_id,access.policy_version,allowed]);
  const actions=selected?cashierOrderActions({...selected,service_type:selected.order_type},new Set(['orders.fulfill','orders.cancel'].filter(hasPermission))):null;
  const refreshed=async()=>{setSelected(null);await load();};
  if(!allowed)return <main className="orders-history-page"><h1>Pedidos</h1><p role="alert">La consulta protegida requiere sesión y operación central compatibles. {configError}</p></main>;
  return <main className="orders-history-page"><h1>Pedidos</h1>
    <form className="sales-monitor-filters" onSubmit={event=>{event.preventDefault();setSelected(null);void load();}}>
      <label>Buscar folio o cliente<input value={query} maxLength={120} onChange={event=>setQuery(event.target.value)}/></label>
      <Button disabled={busy} type="submit">Actualizar pedidos</Button></form>
    {error && <p role="alert">{error}</p>}{busy && <p role="status">Consultando…</p>}
    {recovery && <OrderExceptionDialog authority={JSON.stringify([session!.user.id,access.branch_id])}
      orderId={recovery.orderId} folio="Operación pendiente" version={recovery.version} policyVersion={access.policy_version!}
      action={recovery.action} command={recovery.command} onClose={()=>setRecovery(null)} onApplied={()=>{void refreshed();}}/>}
    <div className="orders-history-layout"><section className="orders-history-list" aria-label="Listado operativo">
      <div className="orders-history-table-scroll"><table><thead><tr><th>Folio</th><th>Cliente</th><th>Estado</th><th>Acción</th></tr></thead>
        <tbody>{rows.map(row=><tr key={row.id}><td>{row.folio}</td><td>{row.customer_label || 'Cliente general'}</td><td>{row.status}</td>
          <td><Button variant="secondary" onClick={()=>void open(row)}>Atender pedido</Button></td></tr>)}</tbody></table></div>
      {!busy && rows.length===0 && <p>No hay pedidos para esta consulta.</p>}
      {cursor && <Button disabled={busy} onClick={()=>void load(cursor)}>Cargar más</Button>}
    </section><section className="orders-history-detail" aria-label="Pedido atendido">
      {selected ? <><h2>{selected.folio}</h2><p>{selected.status} · {selected.payment_status==='CONFIRMED'?'Pagado':'Pago pendiente'}</p>
        <ul>{selected.lines.map(line=><li key={line.id}>{line.quantity} × {line.product_name} · {formatMxnCents(line.line_total_cents)}
          {line.line_notes && <p>{line.line_notes}</p>}{line.selected_modifiers.map((modifier,index)=><p key={index}>{String(modifier.kitchen_text || modifier.option_name || modifier.text || '')}</p>)}</li>)}</ul>
        <p>Total de este pedido: {formatMxnCents(selected.total_cents)}</p>
        {selected.editable && hasPermission('orders.amend') && <Button onClick={()=>navigate(`/pos/orders/${encodeURIComponent(selected.id)}/edit?version=${selected.version}`)}>Editar pedido</Button>}
        {selected.payment_status==='PENDING' && hasPermission('payments.confirm') && <Button disabled={!register} onClick={()=>setPay(true)}>Cobrar pedido</Button>}
        {actions?.fulfillment && <Button onClick={()=>setFulfill(true)}>{actions.fulfillment.label}</Button>}
        {actions?.cancellation && <section><h3>Cancelación autorizada</h3>
          {actions.cancellation==='classification_required' && <label>Producto elaborado<select value={classification} onChange={event=>setClassification(event.target.value)}>
            <option value="">Selecciona el destino autorizado</option><option value="waste">Merma</option><option value="recovery">Recuperación</option></select></label>}
          <Button variant="secondary" disabled={actions.cancellation==='classification_required' && !classification} onClick={()=>setCancel(true)}>Solicitar autorización</Button></section>}
      </> : <p>Selecciona el pedido que estás atendiendo para consultar su detalle autorizado.</p>}
    </section></div>
    {pay && selected && <CashierPaymentDialog orderId={selected.id} folio={selected.folio} authority={authority} registerId={register} request={request}
      initialMethod={selected.payment_method_intent || 'cash'} onClose={()=>{setPay(false);void refreshed();}} onPaid={async()=>{await load();}}/>}
    {fulfill && selected && actions?.fulfillment && <CashierOrderActionDialog orderId={selected.id} folio={selected.folio} authority={authority} request={request}
      command={actions.fulfillment.command} label={actions.fulfillment.label} paid={selected.payment_status==='CONFIRMED'} onClose={()=>setFulfill(false)} onApplied={async()=>{setFulfill(false);await refreshed();}}/>}
    {cancel && selected && <OrderExceptionDialog authority={JSON.stringify([session!.user.id,access.branch_id])} orderId={selected.id} folio={selected.folio}
      version={selected.version} policyVersion={access.policy_version!} action="cancel" command={classification?{classification}:{}}
      onClose={()=>setCancel(false)} onApplied={()=>{setCancel(false);void refreshed();}}>
      <p>Cancelar el pedido {selected.folio}{classification?` y registrar ${classification==='waste'?'merma':'recuperación'}`:''}.</p>
    </OrderExceptionDialog>}
  </main>;
}
