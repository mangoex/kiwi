import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {assertProjectionContract,fetchApi,type BranchFinancialAccess} from '@restaurantos/api-client';
import schema from '../../../../../packages/contracts/schemas/channel-order-operational-v2.schema.json';
import type {OperationalOrder} from '../history/operationalOrders';
export default function OperationalChannelOrders({provider,path,access}:{provider:string;path:string;access:BranchFinancialAccess}) {
  const [orders,setOrders]=useState<OperationalOrder[]>([]);const [error,setError]=useState('');
  useEffect(()=>{let current=true;
    if(access.state!=='active'){setOrders([]);setError('Política suspendida.');return;}
    void fetchApi<unknown>(`/pos/${path}/orders?branch_id=${encodeURIComponent(access.branch_id)}`).then(value=>{
      if(!Array.isArray(value))throw new Error('Listado incompatible.');
      for(const item of value){assertProjectionContract(item,schema);if(item.branch_id!==access.branch_id || item.policy_version!==access.policy_version || item.channel!==provider)throw new Error('Canal fuera de alcance.');}
      if(current){setOrders(value);setError('');}
    }).catch(failure=>{if(current){setOrders([]);setError(String(failure));}});
    return()=>{current=false;};
  },[provider,path,access.branch_id,access.policy_version,access.state]);
  return <main className="orders-history-page"><h1>Pedidos {provider}</h1>{error && <p role="alert">{error}</p>}
    <p>Los estados se gestionan mediante el recorrido autorizado del pedido. Esta bandeja muestra información operativa.</p>
    <table><thead><tr><th>Folio</th><th>Cliente</th><th>Estado</th></tr></thead><tbody>{orders.map(order=><tr key={order.id}><td>{order.folio}</td><td>{order.customer_label}</td><td>{order.status}</td></tr>)}</tbody></table>
    <Link to="/history">Atender un pedido con contexto vigente</Link>
  </main>;
}
