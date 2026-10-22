import {useRef,useState,type ReactNode} from 'react';
import {Button,Modal} from '@restaurantos/ui';
import {ApiError,fetchApi} from '@restaurantos/api-client';
import {cashRecord} from '../settings/cashProjections';
import {clearExceptionIntent,readExceptionIntent,saveExceptionIntent,type ExceptionIntent} from './orderExceptionIntent';

export function OrderExceptionDialog({authority,orderId,folio,version,policyVersion,action,command,children,onClose,onApplied}: {
  authority:string;orderId:string;folio:string;version:number;policyVersion:number;action:'amend'|'cancel';
  command:Record<string,unknown>;children?:ReactNode;onClose:()=>void;onApplied:()=>void;
}) {
  const [initial]=useState(()=>{try{return {intent:readExceptionIntent(),error:''};}catch{return {intent:null,error:'No se puede verificar la operación pendiente.'};}});
  const [pending,setPending]=useState<ExceptionIntent|null>(initial.intent);
  const [identity,setIdentity]=useState(''); const [secret,setSecret]=useState(''); const [reason,setReason]=useState('');
  const [error,setError]=useState(initial.error); const [busy,setBusy]=useState(false); const [done,setDone]=useState(false);
  const lock=useRef(false);
  const compatible=!initial.error && (!pending || (pending.authority===authority && pending.orderId===orderId && pending.action===action));
  async function applied(intent:ExceptionIntent):Promise<boolean> {
    const receipt=cashRecord(await fetchApi(`/orders/${intent.orderId}/exception-authorizations/${intent.authorizationId}/receipt`,{},'v2'),
      ['projection','schema_version','policy_version','authorization_id','order_id','action','applied']);
    if(receipt.projection!=='operational' || receipt.schema_version!==2 || receipt.policy_version!==policyVersion
      || receipt.authorization_id!==intent.authorizationId || receipt.order_id!==intent.orderId || receipt.action!==intent.action
      || typeof receipt.applied!=='boolean') throw new Error('No se pudo verificar el acuse.');
    return receipt.applied;
  }
  async function confirm() {
    if(lock.current || !compatible) return;
    lock.current=true;setBusy(true);setError('');
    let intent=pending;
    try {
      if(!intent) {
        const approval=cashRecord(await fetchApi(`/orders/${orderId}/exception-authorizations`,{method:'POST',body:JSON.stringify({
          action,expected_version:version,reason,command,supervisor_identity:identity.trim(),supervisor_secret:secret,
        })},'v2'),['authorization_id','expires_at','order_id','action','expected_version']);
        setSecret('');
        if(typeof approval.authorization_id!=='string' || approval.order_id!==orderId || approval.action!==action
          || approval.expected_version!==version || typeof approval.expires_at!=='string') throw new Error('Autorización no verificable.');
        intent={authority,orderId,action,version,reason,command,authorizationId:approval.authorization_id,key:crypto.randomUUID()};
        saveExceptionIntent(intent);setPending(intent);
      }
      if(!await applied(intent)) {
        await fetchApi(`/orders/${intent.orderId}/${intent.action==='amend'?'amendments':'cancel'}`,{
          method:'POST',headers:{'Idempotency-Key':intent.key},body:JSON.stringify({...intent.command,
            expected_version:intent.version,reason:intent.reason,exception_authorization_id:intent.authorizationId}),
        });
        if(!await applied(intent)) throw new Error('No se confirmó la aplicación; conserva esta operación.');
      }
      clearExceptionIntent(intent.key);setPending(null);setDone(true);onApplied();
    } catch(failure) {
      // A fresh central receipt distinguishes rejection from a lost successful response.
      if(intent && failure instanceof ApiError && !failure.operationalIntentPending && [403,409].includes(failure.status)) {
        try {
          if(await applied(intent)) {clearExceptionIntent(intent.key);setPending(null);setDone(true);onApplied();return;}
          clearExceptionIntent(intent.key);setPending(null);
        } catch { /* Keep the exact intent while its outcome cannot be verified. */ }
      }
      setError(failure instanceof Error?failure.message:'No se pudo confirmar la operación.');
    } finally {setSecret('');lock.current=false;setBusy(false);}
  }
  return <Modal isOpen onClose={()=>{if(!lock.current){setSecret('');onClose();}}} title={`${action==='amend'?'Autorizar cambios':'Autorizar cancelación'} · ${folio}`}>
    {done ? <p role="status">Operación confirmada.</p> : <>
      {!compatible && <p role="alert">Recupera la operación pendiente en su sucursal y pedido originales.</p>}
      {pending ? <p>Recupera la misma operación. No se volverán a aplicar sus efectos.</p> : <>
        <p>El encargado o Dueño debe revisar este pedido y autorizar esta acción con su propia cuenta.</p>{children}
        <label>Motivo<textarea value={reason} maxLength={1000} onChange={event=>setReason(event.target.value)} disabled={busy}/></label>
        <label>Cuenta del autorizador<input autoComplete="username" value={identity} maxLength={180} onChange={event=>setIdentity(event.target.value)} disabled={busy}/></label>
        <label>Contraseña del autorizador<input type="password" autoComplete="current-password" value={secret} maxLength={1024} onChange={event=>setSecret(event.target.value)} disabled={busy}/></label>
      </>}
    </>}
    {error && <p role="alert">{error}</p>}
    <Button disabled={busy || !compatible || (!done && !pending && (!identity.trim() || !secret || !reason.trim()))}
      onClick={()=>done?onClose():void confirm()}>{done?'Cerrar':busy?'Verificando…':pending?'Recuperar operación':'Autorizar y aplicar'}</Button>
  </Modal>;
}
