import {useEffect,useRef,useState} from 'react';
import {fetchApi,type BranchFinancialAccess} from '@restaurantos/api-client';
import {parseOperationalReport,type OperationalReport,type OperationalPeriod} from './operationalReport';

export default function OperationalReportPanel({access,timezone}:{access:BranchFinancialAccess;timezone:string}) {
  const [period,setPeriod]=useState<OperationalPeriod>('day');
  const [date,setDate]=useState(()=>new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()));
  const [data,setData]=useState<OperationalReport|null>(null);
  const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  const request=useRef<AbortController|null>(null);
  const allowed=access.state==='active' && access.capabilities['reports.operational.read'];
  async function load() {
    request.current?.abort(); setData(null); setError('');
    if(!allowed) return;
    const controller=new AbortController(); request.current=controller; setBusy(true);
    try {
      const params=new URLSearchParams({branch_id:access.branch_id,period,anchor_date:date});
      const result=parseOperationalReport(await fetchApi(`/reports/operations?${params}`,{signal:controller.signal},'v2'),access.branch_id,access.policy_version!,period);
      if(!controller.signal.aborted) setData(result);
    } catch {if(!controller.signal.aborted) setError('No se pudo verificar el reporte. Actualiza la sesión y vuelve a consultar.');}
    finally {if(!controller.signal.aborted) setBusy(false);}
  }
  useEffect(()=>{void load();return()=>request.current?.abort();},[access.branch_id,access.policy_version,allowed,period,date]);
  if(!allowed) return <main className="sales-monitor-page"><p role="alert">No tienes acceso al reporte operativo de esta sucursal.</p></main>;
  return <main className="sales-monitor-page">
    <h1>Reporte operativo</h1><p>Tickets y los diez productos más vendidos · {timezone}</p>
    <form className="sales-monitor-filters" onSubmit={event=>{event.preventDefault();void load();}}>
      <label>Periodo<select value={period} onChange={event=>setPeriod(event.target.value as OperationalPeriod)}>
        <option value="day">Día</option><option value="week">Semana</option><option value="month">Mes</option>
      </select></label><label>Fecha<input type="date" required value={date} onChange={event=>setDate(event.target.value)}/></label>
      <button type="submit" disabled={busy || !date}>Actualizar</button>
    </form>
    {busy && <p role="status">Consultando…</p>}{error && <p role="alert">{error}</p>}
    {data && <section aria-label="Resultados operativos"><p>Tickets: <strong>{data.ticket_count}</strong></p>
      <h2>Top 10 de productos</h2>{data.top_products.length===0 ? <p>Sin productos en este periodo.</p>
        : <ol>{data.top_products.map(row=><li key={row.position} value={row.position}>{row.name}</li>)}</ol>}
    </section>}
  </main>;
}
