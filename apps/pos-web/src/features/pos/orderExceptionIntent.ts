export interface ExceptionIntent {
  authority:string; orderId:string; action:'amend'|'cancel'; version:number;
  command:Record<string,unknown>; reason:string; authorizationId:string; key:string;
}
export const EXCEPTION_INTENT_KEY='pos_order_exception_v2';
const id=/^[a-zA-Z0-9-]{1,180}$/;
export function validateExceptionIntent(value:unknown):ExceptionIntent {
  if(!value || typeof value!=='object' || Array.isArray(value)) throw new Error('Autorización pendiente inválida.');
  const row=value as ExceptionIntent;
  if(Object.keys(row).sort().join('|')!==['authority','orderId','action','version','command','reason','authorizationId','key'].sort().join('|')
    || typeof row.authority!=='string' || !row.authority || typeof row.orderId!=='string' || !id.test(row.orderId)
    || typeof row.authorizationId!=='string' || !id.test(row.authorizationId) || typeof row.key!=='string' || !id.test(row.key)
    || !Number.isSafeInteger(row.version) || row.version<1 || typeof row.reason!=='string' || !row.reason.trim() || row.reason.length>1000
    || !row.command || typeof row.command!=='object' || Array.isArray(row.command)
    || !['amend','cancel'].includes(row.action)) throw new Error('Autorización pendiente inválida.');
  const allowed=row.action==='amend' ? ['lines','delivery_selection','delivery_quote_reference']:['classification'];
  if(Object.keys(row.command).some(key=>!allowed.includes(key))
    || (row.action==='amend' && !Array.isArray(row.command.lines))) throw new Error('Contenido de autorización inválido.');
  return row;
}
export function readExceptionIntent():ExceptionIntent|null {
  const raw=sessionStorage.getItem(EXCEPTION_INTENT_KEY);
  if(raw===null) return null;
  if(raw.length>220000) throw new Error('Autorización pendiente inválida.');
  return validateExceptionIntent(JSON.parse(raw));
}
export function saveExceptionIntent(value:ExceptionIntent):void {
  validateExceptionIntent(value);
  if(readExceptionIntent()) throw new Error('Recupera primero la excepción pendiente.');
  const raw=JSON.stringify(value); sessionStorage.setItem(EXCEPTION_INTENT_KEY,raw);
  if(sessionStorage.getItem(EXCEPTION_INTENT_KEY)!==raw) throw new Error('No se pudo conservar la operación.');
}
export function clearExceptionIntent(key:string):void {
  if(readExceptionIntent()?.key===key) sessionStorage.removeItem(EXCEPTION_INTENT_KEY);
}
