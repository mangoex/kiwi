import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Badge, Button, Input, Modal } from '@restaurantos/ui';
import { Bike, ClipboardList, Edit, Plus, UserRoundX } from 'lucide-react';

import '../../premium-catalogs.css';

interface Driver {
  id: string;
  branch_id: string;
  branch_name: string;
  name: string;
  license_number: string;
  motorcycle_plate: string;
  phone: string;
  address: string;
  emergency_contact_name: string;
  status: 'active' | 'inactive';
}

interface Branch {
  id: string;
  name: string;
  status: string;
}

interface DeliveryHistory {
  id: string;
  folio: string;
  customer_name_snapshot: string;
  order_total_cents: number;
  currency: string;
  line_count: number;
  item_quantity: number;
  order_status: string;
  assigned_at: string;
}

const EMPTY_FORM = {
  name: '',
  license_number: '',
  motorcycle_plate: '',
  branch_id: '',
  phone: '',
  address: '',
  emergency_contact_name: '',
};

const DriversList = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingDriver, setEditingDriver] = useState<Driver | null>(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState('');
  const [historyDriver, setHistoryDriver] = useState<Driver | null>(null);
  const [deliveryHistory, setDeliveryHistory] = useState<DeliveryHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');

  const driversQuery = useQuery<Driver[]>({
    queryKey: ['drivers'],
    queryFn: () => fetchApi('/drivers'),
  });
  const branchesQuery = useQuery<Branch[]>({
    queryKey: ['branches'],
    queryFn: () => fetchApi('/branches'),
  });
  const activeBranches = (branchesQuery.data || []).filter((branch) => branch.status === 'active');

  const saveMutation = useMutation({
    mutationFn: (payload: typeof EMPTY_FORM) =>
      fetchApi(editingDriver ? `/drivers/${editingDriver.id}` : '/drivers', {
        method: editingDriver ? 'PUT' : 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['drivers'] });
      setIsModalOpen(false);
      setEditingDriver(null);
      setFormData(EMPTY_FORM);
      setFormError('');
    },
    onError: (reason) => {
      setFormError(
        reason instanceof ApiError
          ? reason.message
          : 'No fue posible guardar el repartidor.',
      );
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (driverId: string) =>
      fetchApi(`/drivers/${driverId}`, { method: 'DELETE' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['drivers'] });
    },
  });

  const openModal = (driver?: Driver) => {
    setFormError('');
    if (driver) {
      setEditingDriver(driver);
      setFormData({
        name: driver.name,
        license_number: driver.license_number,
        motorcycle_plate: driver.motorcycle_plate,
        branch_id: driver.branch_id,
        phone: driver.phone,
        address: driver.address,
        emergency_contact_name: driver.emergency_contact_name,
      });
    } else {
      setEditingDriver(null);
      setFormData({ ...EMPTY_FORM, branch_id: activeBranches[0]?.id || '' });
    }
    setIsModalOpen(true);
  };

  const updateField = (field: keyof typeof EMPTY_FORM, value: string) => {
    setFormData((current) => ({ ...current, [field]: value }));
  };

  const saveDriver = () => {
    const missing = Object.values(formData).some((value) => !value.trim());
    if (missing) {
      setFormError('Completa todos los datos del repartidor.');
      return;
    }
    setFormError('');
    saveMutation.mutate(formData);
  };

  const deactivateDriver = (driver: Driver) => {
    if (!window.confirm(`¿Desactivar a ${driver.name}? Su historial se conservará.`)) {
      return;
    }
    deactivateMutation.mutate(driver.id);
  };

  const openHistory = async (driver: Driver) => {
    setHistoryDriver(driver);
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const rows = await fetchApi<DeliveryHistory[]>(`/drivers/${driver.id}/deliveries`);
      setDeliveryHistory(Array.isArray(rows) ? rows : []);
    } catch (reason) {
      setHistoryError(
        reason instanceof ApiError
          ? reason.message
          : 'No fue posible cargar el historial de entregas.',
      );
      setDeliveryHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const formatCurrency = (cents: number, currency: string) =>
    new Intl.NumberFormat('es-MX', { style: 'currency', currency }).format(cents / 100);

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 20, marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Repartidores</h1>
          <p className="premium-header-subtitle">
            Catálogo de repartidores propios y la sucursal donde operan.
          </p>
        </div>
        <button
          className="premium-add-btn"
          type="button"
          onClick={() => openModal()}
          disabled={branchesQuery.isLoading || activeBranches.length === 0}
        >
          <Plus size={18} />
          Nuevo repartidor
        </button>
      </div>

      {branchesQuery.isError && (
        <p role="alert" style={{ color: 'var(--color-red)', marginBottom: 16 }}>
          No fue posible cargar las sucursales.
        </p>
      )}
      {!branchesQuery.isLoading && !branchesQuery.isError && activeBranches.length === 0 && (
        <p role="alert" style={{ color: '#92400e', marginBottom: 16 }}>
          Se requiere al menos una sucursal activa para registrar repartidores.
        </p>
      )}
      {deactivateMutation.isError && (
        <p role="alert" style={{ color: 'var(--color-red)', marginBottom: 16 }}>
          No fue posible desactivar el repartidor.
        </p>
      )}

      <div className="premium-card">
        {driversQuery.isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>
            Cargando repartidores…
          </div>
        ) : driversQuery.isError ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>
            No fue posible cargar los repartidores.
          </div>
        ) : !driversQuery.data?.length ? (
          <div className="premium-empty-state">
            <Bike size={64} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>
              No hay repartidores registrados
            </h3>
            <p style={{ color: 'var(--color-text-muted)' }}>
              Agrega el primer repartidor y asígnalo a una sucursal.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Repartidor</th>
                  <th>Sucursal</th>
                  <th>Licencia</th>
                  <th>Placas</th>
                  <th>Teléfono</th>
                  <th>Domicilio</th>
                  <th>Contacto</th>
                  <th>Estado</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {driversQuery.data.map((driver) => (
                  <tr key={driver.id}>
                    <td style={{ fontWeight: 600 }}>{driver.name}</td>
                    <td>{driver.branch_name}</td>
                    <td>{driver.license_number}</td>
                    <td>{driver.motorcycle_plate}</td>
                    <td>{driver.phone}</td>
                    <td style={{ minWidth: 220 }}>{driver.address}</td>
                    <td>{driver.emergency_contact_name}</td>
                    <td>
                      <Badge variant={driver.status === 'active' ? 'success' : 'default'}>
                        {driver.status === 'active' ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                        <button
                          type="button"
                          className="premium-action-btn edit"
                          aria-label={`Ver entregas de ${driver.name}`}
                          onClick={() => void openHistory(driver)}
                        >
                          <ClipboardList size={18} />
                        </button>
                        <button
                          type="button"
                          className="premium-action-btn edit"
                          aria-label={`Editar a ${driver.name}`}
                          onClick={() => openModal(driver)}
                        >
                          <Edit size={18} />
                        </button>
                        {driver.status === 'active' && (
                          <button
                            type="button"
                            className="premium-action-btn delete"
                            aria-label={`Desactivar a ${driver.name}`}
                            onClick={() => deactivateDriver(driver)}
                          >
                            <UserRoundX size={18} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingDriver ? 'Editar repartidor' : 'Nuevo repartidor'}
      >
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <label style={{ display: 'grid', gap: 5, fontWeight: 500, fontSize: '.875rem' }}>
            Nombre
            <Input value={formData.name} onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateField('name', event.target.value)} />
          </label>
          <label style={{ display: 'grid', gap: 5, fontWeight: 500, fontSize: '.875rem' }}>
            Sucursal asignada
            <select
              value={formData.branch_id}
              onChange={(event) => updateField('branch_id', event.target.value)}
              style={{ width: '100%', minHeight: 42, border: '1px solid #d1d5db', borderRadius: 8, padding: '0 10px', background: '#fff' }}
            >
              <option value="">Selecciona una sucursal</option>
              {activeBranches.map((branch) => (
                <option key={branch.id} value={branch.id}>{branch.name}</option>
              ))}
            </select>
          </label>
          <label style={{ display: 'grid', gap: 5, fontWeight: 500, fontSize: '.875rem' }}>
            Licencia
            <Input value={formData.license_number} onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateField('license_number', event.target.value)} />
          </label>
          <label style={{ display: 'grid', gap: 5, fontWeight: 500, fontSize: '.875rem' }}>
            Placas de la motocicleta
            <Input value={formData.motorcycle_plate} onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateField('motorcycle_plate', event.target.value)} />
          </label>
          <label style={{ display: 'grid', gap: 5, fontWeight: 500, fontSize: '.875rem' }}>
            Teléfono
            <Input value={formData.phone} onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateField('phone', event.target.value)} />
          </label>
          <label style={{ display: 'grid', gap: 5, fontWeight: 500, fontSize: '.875rem' }}>
            Persona de contacto
            <Input value={formData.emergency_contact_name} onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateField('emergency_contact_name', event.target.value)} />
          </label>
          <label style={{ gridColumn: '1 / -1', display: 'grid', gap: 5, fontWeight: 500, fontSize: '.875rem' }}>
            Domicilio
            <textarea
              value={formData.address}
              onChange={(event) => updateField('address', event.target.value)}
              rows={3}
              maxLength={500}
              style={{ width: '100%', resize: 'vertical', border: '1px solid #d1d5db', borderRadius: 8, padding: 10, font: 'inherit' }}
            />
          </label>
          {formError && (
            <p role="alert" style={{ gridColumn: '1 / -1', color: 'var(--color-red)', margin: 0 }}>
              {formError}
            </p>
          )}
          <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 8 }}>
            <Button variant="secondary" onClick={() => setIsModalOpen(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={saveDriver} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Guardando…' : 'Guardar'}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={Boolean(historyDriver)}
        onClose={() => setHistoryDriver(null)}
        title={historyDriver ? `Historial de entregas · ${historyDriver.name}` : 'Historial de entregas'}
      >
        {historyLoading ? (
          <p style={{ color: 'var(--color-text-muted)' }}>Cargando entregas…</p>
        ) : historyError ? (
          <p role="alert" style={{ color: 'var(--color-red)' }}>{historyError}</p>
        ) : deliveryHistory.length === 0 ? (
          <p style={{ color: 'var(--color-text-muted)' }}>Este repartidor todavía no tiene pedidos asignados.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Pedido</th>
                  <th>Cliente</th>
                  <th>Importe</th>
                  <th>Líneas</th>
                  <th>Unidades</th>
                  <th>Estado</th>
                  <th>Asignado</th>
                </tr>
              </thead>
              <tbody>
                {deliveryHistory.map((delivery) => (
                  <tr key={delivery.id}>
                    <td style={{ fontWeight: 600 }}>{delivery.folio}</td>
                    <td>{delivery.customer_name_snapshot}</td>
                    <td>{formatCurrency(delivery.order_total_cents, delivery.currency)}</td>
                    <td>{delivery.line_count}</td>
                    <td>{delivery.item_quantity}</td>
                    <td>{delivery.order_status}</td>
                    <td>{new Date(delivery.assigned_at).toLocaleString('es-MX')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Modal>
    </>
  );
};

export default DriversList;
