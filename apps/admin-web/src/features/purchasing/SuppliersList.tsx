import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Truck, PackagePlus } from 'lucide-react';
import '../../premium-catalogs.css';

interface Supplier { id: string; code: string; commercial_name: string; tax_id?: string; credit_days: number; contacts: Array<{ id: string; name: string; phone?: string; primary_for_orders: boolean }>; }
interface Item { id: string; name: string; sku: string; base_unit_id: string; unit_code: string; }
interface Unit { id: string; name: string; code: string; }
interface Presentation { id: string; code: string; name: string; supplier_name: string; item_name: string; last_net_price: number; cost_per_base_unit: number; base_unit_code: string; }

const SuppliersList = () => {
  const queryClient = useQueryClient();
  const branchId = localStorage.getItem('admin_branch_id') || localStorage.getItem('pos_branch_id') || '';
  const [supplierOpen, setSupplierOpen] = useState(false);
  const [presentationOpen, setPresentationOpen] = useState(false);
  const [supplierForm, setSupplierForm] = useState({ code: '', commercial_name: '', legal_name: '', tax_id: '', credit_days: '0' });
  const [presentationForm, setPresentationForm] = useState({ supplier_id: '', item_id: '', code: '', name: '', package_type: 'bag', commercial_unit_id: '', usable_content: '', last_net_price: '' });
  const query = branchId ? `?branch_id=${branchId}` : '';

  const { data: suppliers = [] } = useQuery<Supplier[]>({ queryKey: ['suppliers'], queryFn: () => fetchApi(`/suppliers${query}`) });
  const { data: presentations = [] } = useQuery<Presentation[]>({ queryKey: ['purchase-presentations'], queryFn: () => fetchApi(`/purchase-presentations${query}`) });
  const { data: items = [] } = useQuery<Item[]>({ queryKey: ['inventory', 'items'], queryFn: () => fetchApi('/inventory/items') });
  const { data: units = [] } = useQuery<Unit[]>({ queryKey: ['inventory', 'units'], queryFn: () => fetchApi('/inventory/units') });

  const supplierMutation = useMutation({
    mutationFn: () => fetchApi('/suppliers', { method: 'POST', body: JSON.stringify({ ...supplierForm, credit_days: Number(supplierForm.credit_days), delivery_days: [], payment_methods: [] }) }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['suppliers'] }); setSupplierOpen(false); },
  });
  const presentationMutation = useMutation({
    mutationFn: () => {
      const item = items.find((candidate) => candidate.id === presentationForm.item_id);
      return fetchApi('/purchase-presentations', { method: 'POST', body: JSON.stringify({
        ...presentationForm,
        base_unit_id: item?.base_unit_id,
        base_unit_yield: presentationForm.usable_content,
        commercial_quantity: '1', yield_percent: '1', tax_rate: '0',
      }) });
    },
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['purchase-presentations'] }); setPresentationOpen(false); },
  });

  return <>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
      <div><h1 className="premium-header-title">Proveedores y presentaciones</h1><p className="premium-header-subtitle">Catálogo central; los precios capturados todavía no afectan el costo contable.</p></div>
      <div style={{ display: 'flex', gap: 8 }}>
        <Button variant="secondary" onClick={() => setPresentationOpen(true)}><PackagePlus size={17} /> Presentación</Button>
        <Button variant="primary" onClick={() => setSupplierOpen(true)}><Plus size={17} /> Proveedor</Button>
      </div>
    </div>
    <div className="premium-card" style={{ marginBottom: 24, overflowX: 'auto' }}>
      <table className="premium-table"><thead><tr><th>Código</th><th>Proveedor</th><th>RFC</th><th>Crédito</th><th>Contacto de pedidos</th></tr></thead>
        <tbody>{suppliers.map((supplier) => <tr key={supplier.id}><td>{supplier.code}</td><td><span style={{ display: 'flex', gap: 8 }}><Truck size={17} />{supplier.commercial_name}</span></td><td>{supplier.tax_id || '—'}</td><td>{supplier.credit_days} días</td><td>{supplier.contacts.find((contact) => contact.primary_for_orders)?.name || 'Sin asignar'}</td></tr>)}</tbody>
      </table>
    </div>
    <div className="premium-card" style={{ overflowX: 'auto' }}>
      <table className="premium-table"><thead><tr><th>Código</th><th>Presentación</th><th>Proveedor</th><th>Insumo</th><th>Último precio</th><th>Costo unidad base</th></tr></thead>
        <tbody>{presentations.map((presentation) => <tr key={presentation.id}><td>{presentation.code}</td><td>{presentation.name}</td><td>{presentation.supplier_name}</td><td>{presentation.item_name}</td><td>${Number(presentation.last_net_price).toFixed(2)}</td><td>${Number(presentation.cost_per_base_unit).toFixed(4)} / {presentation.base_unit_code}</td></tr>)}</tbody>
      </table>
    </div>

    <Modal isOpen={supplierOpen} onClose={() => setSupplierOpen(false)} title="Nuevo proveedor">
      <Fields values={supplierForm} setValues={setSupplierForm} labels={{ code: 'Código', commercial_name: 'Nombre comercial', legal_name: 'Razón social', tax_id: 'RFC', credit_days: 'Días de crédito' }} />
      <Actions close={() => setSupplierOpen(false)} save={() => supplierMutation.mutate()} saving={supplierMutation.isPending} />
    </Modal>
    <Modal isOpen={presentationOpen} onClose={() => setPresentationOpen(false)} title="Nueva presentación de compra">
      <div style={{ display: 'grid', gap: 12 }}>
        <Select label="Proveedor" value={presentationForm.supplier_id} setValue={(value) => setPresentationForm({ ...presentationForm, supplier_id: value })} options={suppliers.map((supplier) => [supplier.id, supplier.commercial_name])} />
        <Select label="Insumo" value={presentationForm.item_id} setValue={(value) => setPresentationForm({ ...presentationForm, item_id: value })} options={items.map((item) => [item.id, `${item.name} (${item.unit_code})`])} />
        <Select label="Unidad comercial" value={presentationForm.commercial_unit_id} setValue={(value) => setPresentationForm({ ...presentationForm, commercial_unit_id: value })} options={units.map((unit) => [unit.id, `${unit.name} (${unit.code})`])} />
        <Fields values={presentationForm} setValues={setPresentationForm} labels={{ code: 'Código', name: 'Nombre', package_type: 'Tipo de empaque', usable_content: 'Contenido aprovechable en unidad base', last_net_price: 'Precio neto' }} only={['code', 'name', 'package_type', 'usable_content', 'last_net_price']} />
      </div>
      <Actions close={() => setPresentationOpen(false)} save={() => presentationMutation.mutate()} saving={presentationMutation.isPending} />
    </Modal>
  </>;
};

const Fields = <T extends Record<string, string>>({ values, setValues, labels, only }: { values: T; setValues: (value: T) => void; labels: Partial<Record<keyof T, string>>; only?: Array<keyof T> }) => (
  <div style={{ display: 'grid', gap: 12 }}>{(only || Object.keys(labels) as Array<keyof T>).map((key) => <label key={String(key)} style={{ display: 'grid', gap: 4 }}><span>{labels[key]}</span><Input value={values[key]} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValues({ ...values, [key]: event.target.value })} /></label>)}</div>
);
const Select = ({ label, value, setValue, options }: { label: string; value: string; setValue: (value: string) => void; options: string[][] }) => <label style={{ display: 'grid', gap: 4 }}><span>{label}</span><select value={value} onChange={(event) => setValue(event.target.value)} style={{ padding: 10, borderRadius: 8 }}><option value="">Selecciona</option>{options.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>;
const Actions = ({ close, save, saving }: { close: () => void; save: () => void; saving: boolean }) => <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}><Button variant="secondary" onClick={close}>Cancelar</Button><Button variant="primary" onClick={save} disabled={saving}>{saving ? 'Guardando...' : 'Guardar'}</Button></div>;

export default SuppliersList;
