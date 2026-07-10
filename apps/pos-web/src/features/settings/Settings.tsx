import React, { useState } from 'react';
import { Settings as SettingsIcon, Printer, Clock, Wallet, WifiOff, Save, CheckCircle2, RefreshCw } from 'lucide-react';
import { Button } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';

const Settings = () => {
  const [activeTab, setActiveTab] = useState('shift');
  const [printerIp, setPrinterIp] = useState('192.168.1.100');
  const [autoPrint, setAutoPrint] = useState(true);
  const [startingCash, setStartingCash] = useState('500.00');
  const [shiftActive, setShiftActive] = useState(false);
  const [saved, setSaved] = useState(false);
  
  const [branchId, setBranchId] = useState(localStorage.getItem('pos_branch_id') || '');
  const [registerId, setRegisterId] = useState(localStorage.getItem('pos_register_id') || 'CAJA-01');
  
  const [branches, setBranches] = useState<any[]>([]);

  React.useEffect(() => {
    fetchApi<any[]>('/branches').then(data => {
      if(Array.isArray(data)) setBranches(data);
    }).catch(e => console.error(e));
  }, []);

  React.useEffect(() => {
    if (branchId && registerId) {
      fetchApi<{ cash_shift: unknown | null }>(
        `/cash-shifts/current?branch_id=${encodeURIComponent(branchId)}&register_id=${encodeURIComponent(registerId)}`
      )
        .then(data => {
          if (data && data.cash_shift) {
            setShiftActive(true);
          } else {
            setShiftActive(false);
          }
        })
        .catch(e => console.error(e));
    }
  }, [branchId, registerId]);

  const handleSave = () => {
    localStorage.setItem('pos_branch_id', branchId);
    localStorage.setItem('pos_register_id', registerId || 'CAJA-01');
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleToggleShift = async () => {
    if (!branchId || !registerId) {
      alert("Por favor, guarda la sucursal y caja primero.");
      return;
    }
    
    if (!shiftActive) {
      try {
        await fetchApi('/cash-shifts/open', {
          method: 'POST',
          body: JSON.stringify({
            opening_cash_cents: Math.round(parseFloat(startingCash || '0') * 100),
            branch_id: branchId,
            register_id: registerId
          })
        });
        setShiftActive(true);
        alert("Turno abierto exitosamente.");
      } catch (e) {
        console.error(e);
        alert("Error al abrir turno.");
      }
    } else {
      try {
        await fetchApi('/cash-shifts/close', {
          method: 'POST',
          body: JSON.stringify({
            counted_cash_cents: 0,
            branch_id: branchId,
            register_id: registerId
          })
        });
        setShiftActive(false);
        alert("Turno cerrado exitosamente.");
      } catch (e) {
        console.error(e);
        alert("Error al cerrar turno.");
      }
    }
  };

  return (
    <div style={{ padding: '32px 40px', display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '40px' }}>
        <div style={{ background: 'var(--primary)', color: 'white', padding: '12px', borderRadius: '16px' }}>
          <SettingsIcon size={28} />
        </div>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.75rem', color: 'var(--text-main)', letterSpacing: '-0.5px' }}>Configuración de Caja</h1>
          <p style={{ margin: '4px 0 0 0', color: 'var(--text-muted)' }}>Administra tu turno, impresoras y opciones locales</p>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '32px', flex: 1 }}>
        {/* Sidebar Menu */}
        <div style={{ width: '260px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <TabButton active={activeTab === 'shift'} onClick={() => setActiveTab('shift')} icon={<Clock size={20} />} label="Turno y Caja" />
          <TabButton active={activeTab === 'printers'} onClick={() => setActiveTab('printers')} icon={<Printer size={20} />} label="Impresoras" />
          <TabButton active={activeTab === 'sync'} onClick={() => setActiveTab('sync')} icon={<WifiOff size={20} />} label="Modo Offline" />
        </div>

        {/* Content Area */}
        <div style={{ flex: 1, background: 'var(--surface)', borderRadius: '24px', padding: '32px', boxShadow: '0 4px 20px rgba(0,0,0,0.03)' }}>
          
          {activeTab === 'shift' && (
            <div className="fade-in">
              <h2 style={{ marginTop: 0, marginBottom: '24px', color: 'var(--text-main)' }}>Gestión de Turno</h2>
              
              <div style={{ background: shiftActive ? 'rgba(34, 197, 94, 0.05)' : 'var(--surface-sunken)', border: `1px solid ${shiftActive ? 'rgba(34, 197, 94, 0.2)' : 'var(--border)'}`, borderRadius: '16px', padding: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '32px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ background: shiftActive ? '#22c55e' : 'var(--text-muted)', color: 'white', padding: '12px', borderRadius: '50%' }}>
                    <Wallet size={24} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-main)' }}>Estado de la Caja</h3>
                    <p style={{ margin: '4px 0 0 0', color: 'var(--text-muted)' }}>
                      {shiftActive ? 'Caja abierta y operando.' : 'La caja está cerrada actualmente.'}
                    </p>
                  </div>
                </div>
                <Button variant={shiftActive ? 'secondary' : 'primary'} onClick={handleToggleShift}>
                  {shiftActive ? 'Cerrar Turno (Corte de Caja)' : 'Abrir Turno'}
                </Button>
              </div>

              {!shiftActive && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '400px', marginBottom: '32px' }}>
                  <label style={{ fontWeight: 500, color: 'var(--text-main)' }}>Sucursal Asignada</label>
                  <select 
                    value={branchId} 
                    onChange={e => setBranchId(e.target.value)}
                    style={{ padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--surface-sunken)', fontSize: '1rem', width: '100%', boxSizing: 'border-box' }}
                  >
                    <option value="">Seleccione una sucursal...</option>
                    {branches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select>

                  <label style={{ fontWeight: 500, color: 'var(--text-main)' }}>Identificador de la Caja</label>
                  <input 
                    type="text" 
                    value={registerId} 
                    onChange={e => setRegisterId(e.target.value)}
                    placeholder="Ej. CAJA-01"
                    style={{ padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--surface-sunken)', fontSize: '1rem', width: '100%', boxSizing: 'border-box' }}
                  />
                  <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>Nombre o ID único para esta caja registradora.</p>
                  
                  <Button variant="primary" onClick={handleSave} style={{ alignSelf: 'flex-start' }}>Guardar Cambios</Button>
                  {saved && <span style={{ color: '#22c55e', fontSize: '0.85rem', fontWeight: 600 }}>¡Guardado exitosamente!</span>}
                </div>
              )}

              {!shiftActive && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '400px' }}>
                  <label style={{ fontWeight: 500, color: 'var(--text-main)' }}>Fondo de Caja Inicial ($)</label>
                  <input 
                    type="number" 
                    value={startingCash} 
                    onChange={e => setStartingCash(e.target.value)}
                    style={{ padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--surface-sunken)', fontSize: '1rem', width: '100%', boxSizing: 'border-box' }}
                  />
                  <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>Efectivo base para dar cambio al iniciar el turno.</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'printers' && (
            <div className="fade-in">
              <h2 style={{ marginTop: 0, marginBottom: '24px', color: 'var(--text-main)' }}>Configuración de Impresoras</h2>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '500px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ fontWeight: 500, color: 'var(--text-main)' }}>IP de la Impresora de Tickets (ESC/POS)</label>
                  <input 
                    type="text" 
                    value={printerIp} 
                    onChange={e => setPrinterIp(e.target.value)}
                    placeholder="Ej. 192.168.1.100"
                    style={{ padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--surface-sunken)', fontSize: '1rem', width: '100%', boxSizing: 'border-box' }}
                  />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px', border: '1px solid var(--border)', borderRadius: '12px' }}>
                  <div>
                    <h4 style={{ margin: 0, color: 'var(--text-main)' }}>Impresión Automática</h4>
                    <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>Imprimir el ticket al cobrar la orden</p>
                  </div>
                  <label className="switch">
                    <input type="checkbox" checked={autoPrint} onChange={() => setAutoPrint(!autoPrint)} />
                    <span className="slider round"></span>
                  </label>
                </div>

                <div style={{ display: 'flex', gap: '16px', marginTop: '16px' }}>
                  <Button variant="primary" onClick={handleSave} style={{ flex: 1, display: 'flex', justifyContent: 'center', gap: '8px' }}>
                    {saved ? <CheckCircle2 size={18} /> : <Save size={18} />}
                    {saved ? 'Guardado' : 'Guardar Cambios'}
                  </Button>
                  <Button variant="secondary" style={{ display: 'flex', justifyContent: 'center', gap: '8px' }}>
                    Probar Impresión
                  </Button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'sync' && (
            <div className="fade-in">
              <h2 style={{ marginTop: 0, marginBottom: '24px', color: 'var(--text-main)' }}>Sincronización y Red</h2>
              
              <div style={{ background: 'var(--surface-sunken)', border: '1px solid var(--border)', borderRadius: '16px', padding: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ background: 'var(--primary)', color: 'white', padding: '12px', borderRadius: '50%' }}>
                    <RefreshCw size={24} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-main)' }}>Sincronización Local</h3>
                    <p style={{ margin: '4px 0 0 0', color: 'var(--text-muted)' }}>El menú está guardado en caché local.</p>
                  </div>
                </div>
                <Button variant="secondary">
                  Forzar Sincronización
                </Button>
              </div>
            </div>
          )}

        </div>
      </div>

      <style>{`
        .switch { position: relative; display: inline-block; width: 50px; height: 28px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; }
        .slider:before { position: absolute; content: ""; height: 20px; width: 20px; left: 4px; bottom: 4px; background-color: white; transition: .4s; }
        input:checked + .slider { background-color: var(--primary); }
        input:checked + .slider:before { transform: translateX(22px); }
        .slider.round { border-radius: 34px; }
        .slider.round:before { border-radius: 50%; }
        .fade-in { animation: fadeIn 0.3s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
};

const TabButton = ({ active, icon, label, onClick }: { active: boolean; icon: React.ReactNode; label: string; onClick: () => void }) => (
  <button 
    onClick={onClick}
    style={{
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      padding: '16px',
      background: active ? 'var(--primary)' : 'transparent',
      color: active ? 'white' : 'var(--text-main)',
      border: 'none',
      borderRadius: '16px',
      fontSize: '1rem',
      fontWeight: active ? 600 : 500,
      cursor: 'pointer',
      transition: 'all 0.2s',
      textAlign: 'left'
    }}
    onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'var(--surface)'; }}
    onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent'; }}
  >
    {icon}
    {label}
  </button>
);

export default Settings;
