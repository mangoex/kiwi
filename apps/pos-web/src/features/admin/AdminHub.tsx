import { useState, type ComponentType } from 'react';
import { Link } from 'react-router-dom';
import { adminDestination, hasAdminCapability, POS_ADMIN_RETURN_CONTEXT } from '@restaurantos/api-client';
import { confirmWorkspaceNavigation } from '@restaurantos/ui';
import { Building2, Carrot, ChefHat, ClipboardCheck, Package, Receipt, ShieldCheck, Trash2, Truck, MessageSquareText, Clock3, BarChart3, TrendingUp } from 'lucide-react';
import { usePosSession } from '../../session';

interface Card { module?:string; to?:string; permissions?:string[]; label:string; description:string; icon:ComponentType<{size?:number}> }
const cards: Card[] = [
  {to:'/administration/attendance',permissions:['branch.staff.read'],label:'Checador',description:'Entradas y salidas del personal de tu sucursal.',icon:Clock3},
  {to:'/sales-monitor',permissions:['reports.sales.read'],label:'Monitor de ventas',description:'Ventas y operaciones del turno en tiempo real.',icon:BarChart3},
  {to:'/historical-reports',permissions:['reports.ingredient_sales.read','reports.expenses.read'],label:'Reportes históricos',description:'Venta por insumos, gastos y conciliación de sucursal.',icon:TrendingUp},
  {module:'products',label:'Productos y recetas',description:'Catálogo, recetas y disponibilidad autorizada por sucursal.',icon:Package},
  {module:'variations',label:'Comentarios del pedido',description:'Indicaciones para cocina y disponibilidad local.',icon:MessageSquareText},
  {module:'ingredient-extras',label:'Ingredientes adicionales',description:'Porciones extra del catálogo y disponibilidad local.',icon:Carrot},
  {module:'inventory',label:'Inventario',description:'Insumos, existencias y herramientas de almacén.',icon:Carrot},
  {module:'suppliers',label:'Proveedores',description:'Proveedores, contactos y presentaciones de compra.',icon:Building2},
  {module:'purchases',label:'Compras',description:'Documentos, recepciones y conciliación de compras.',icon:Receipt},
  {module:'expenses',label:'Gastos',description:'Pagos operativos, efectivo y estadísticas de la sucursal.',icon:Receipt},
  {module:'expense-concepts',label:'Conceptos de gasto',description:'Catálogo de servicios y gastos operativos.',icon:Building2},
  {module:'production',label:'Producción',description:'Elaborados y lotes de producción de la sucursal.',icon:ChefHat},
  {module:'waste',label:'Mermas',description:'Registros, autorizaciones y reversas auditables.',icon:Trash2},
  {module:'transfers',label:'Traspasos',description:'Envíos, tránsito y recepción entre sucursales.',icon:Truck},
  {module:'counts',label:'Conteos físicos',description:'Capturas, revisiones y ajustes autorizados.',icon:ClipboardCheck},
];
export default function AdminHub() {
  const {session} = usePosSession();
  const [error,setError] = useState('');
  const visible = cards.filter(card=>card.module ? Boolean(adminDestination(session,card.module)) : card.permissions?.some(code=>hasAdminCapability(session,code)));
  return <div style={{padding:32,maxWidth:1280,margin:'0 auto'}}>
    <div style={{display:'flex',alignItems:'center',gap:16}}><ShieldCheck size={32}/><div><h1 style={{margin:0}}>Administración de sucursal</h1>
      <p>Accede a las mismas funciones del administrador con los permisos de tu cuenta.</p></div></div>
    <p style={{padding:16,border:'1px solid #e5e5e5',borderRadius:12}}><strong>{session?.active_branch?.name}</strong> · {session?.user.display_name}</p>
    {error && <p role="alert">{error}</p>}
    <div role="list" style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,260px),1fr))',gap:16,marginTop:28}}>{visible.map(card=>{
      const Icon = card.icon;
      const content = <><Icon size={24}/><h2 style={{fontSize:18,margin:'12px 0 8px'}}>{card.label}</h2><p style={{margin:0,lineHeight:1.5,color:'#525252'}}>{card.description}</p></>;
      const style = {display:'block',padding:24,borderRadius:14,border:'1px solid #dedede',background:'#fff',color:'#171717',textDecoration:'none'};
      return card.module ? <a role="listitem" key={card.module} href={adminDestination(session,card.module)!} style={style} onClick={event=>{
        if (!navigator.onLine) {event.preventDefault();setError('La administración requiere conexión. Tu captura permanece en caja.');return;}
        if (!confirmWorkspaceNavigation()) {event.preventDefault();return;}
        sessionStorage.setItem(POS_ADMIN_RETURN_CONTEXT, JSON.stringify({userId:session!.user.id,branchId:session!.active_branch!.id}));
      }}>{content}</a> : <Link role="listitem" key={card.to} to={card.to!} style={style} onClick={event=>{if (!confirmWorkspaceNavigation()) event.preventDefault();}}>{content}</Link>;
    })}</div>
  </div>;
}
