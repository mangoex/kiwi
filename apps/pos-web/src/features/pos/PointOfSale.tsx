import React, { useState, useEffect } from 'react';
import { Modal } from '@restaurantos/ui';
import { ShoppingBag, Search, Bell, Plus, Minus, ArrowRight, Coffee, CupSoda, Sandwich, Salad, Wheat, Package, Utensils } from 'lucide-react';

const getProductIcon = (category: string, size: number = 40) => {
  const cat = (category || '').toLowerCase();
  if (cat.includes('café') || cat.includes('matcha')) return <Coffee size={size} strokeWidth={1.5} color="var(--primary)" />;
  if (cat.includes('jugo') || cat.includes('agua') || cat.includes('bebida') || cat.includes('smoothie') || cat.includes('extracto')) return <CupSoda size={size} strokeWidth={1.5} color="var(--primary)" />;
  if (cat.includes('ensalada')) return <Salad size={size} strokeWidth={1.5} color="var(--primary)" />;
  if (cat.includes('panadería') || cat.includes('pan')) return <Wheat size={size} strokeWidth={1.5} color="var(--primary)" />;
  if (cat.includes('emparedado') || cat.includes('sando')) return <Sandwich size={size} strokeWidth={1.5} color="var(--primary)" />;
  if (cat.includes('combo')) return <Package size={size} strokeWidth={1.5} color="var(--primary)" />;
  return <Utensils size={size} strokeWidth={1.5} color="var(--primary)" />;
};

interface Product {
  id: string;
  name: string;
  sku: string;
  category: string;
  price: number;
  description: string;
  station: string;
  image_url?: string;
}

interface CartItem extends Product {
  quantity: number;
}

const PointOfSale = () => {
  const [activeCategory, setActiveCategory] = useState('Todas');
  const [isPaymentOpen, setPaymentOpen] = useState(false);
  const [cart, setCart] = useState<CartItem[]>([]);
  
  const [ownerName, setOwnerName] = useState('');
  const [ownerPhone, setOwnerPhone] = useState('');
  const [ownerAddress, setOwnerAddress] = useState('');
  const [orderDetails, setOrderDetails] = useState('');
  const [orderType, setOrderType] = useState('dine-in');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [categories, setCategories] = useState<string[]>(['Todas']);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [catRes, prodRes] = await Promise.all([
          fetch('/api/v1/categories'),
          fetch(localStorage.getItem('pos_branch_id') ? `/api/v1/catalog/products?branch_id=${encodeURIComponent(localStorage.getItem('pos_branch_id')!)}` : '/api/v1/catalog/products')
        ]);
        const catData = await catRes.json();
        const prodData = await prodRes.json();

        if (Array.isArray(catData)) {
          setCategories(['Todas', ...catData.map(c => c.name)]);
        }
        if (Array.isArray(prodData)) {
          const mappedProducts = prodData.map((p: any, i: number) => ({
            id: p.id,
            name: p.name,
            sku: p.sku,
            category: p.category_name,
            price: p.price_cents / 100,
            description: p.description,
            station: p.station,
            image_url: p.image_url,
          }));
          setProducts(mappedProducts);
        }
      } catch (e) {
        console.error("Error fetching POS data:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const filteredProducts = activeCategory === 'Todas' ? products : products.filter(p => p.category === activeCategory);

  const addToCart = (product: Product) => {
    setCart(prev => {
      const existing = prev.find(item => item.id === product.id);
      if (existing) {
        return prev.map(item => item.id === product.id ? { ...item, quantity: item.quantity + 1 } : item);
      }
      return [...prev, { ...product, quantity: 1 }];
    });
  };

  const updateQuantity = (id: string, delta: number) => {
    setCart(prev => prev.map(item => {
      if (item.id === id) {
        const newQty = item.quantity + delta;
        return newQty > 0 ? { ...item, quantity: newQty } : item;
      }
      return item;
    }).filter(item => item.quantity > 0));
  };

  const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  const tax = subtotal * 0.16; // 16% IVA in Mexico
  const total = subtotal + tax;

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(amount);
  };

  return (
    <div style={{ display: 'flex', height: '100vh', padding: '24px', gap: '24px', backgroundColor: '#eef2f6' }}>
      
      {/* Left side: Order Sidebar */}
      <aside className="pos-order-sidebar-new" style={{ width: '380px', display: 'flex', flexDirection: 'column', background: 'white', borderRadius: '24px', boxShadow: '0 10px 40px rgba(0,0,0,0.04)', overflow: 'hidden', flexShrink: 0 }}>
        
        {/* Top Dropdowns Area */}
        <div style={{ padding: '24px 24px 16px', display: 'flex', gap: 12, borderBottom: '1px solid #f1f5f9' }}>
          <select style={{ flex: 1, padding: '10px 16px', borderRadius: 12, border: '1px solid #e2e8f0', background: '#f8fafc', fontWeight: 600, color: 'var(--text-main)', outline: 'none', appearance: 'none', cursor: 'pointer' }}>
            <option>Mesa 05</option>
            <option>Mesa 06</option>
            <option>Mostrador</option>
          </select>
          <select 
            style={{ flex: 1, padding: '10px 16px', borderRadius: 12, border: '1px solid #e2e8f0', background: '#f8fafc', fontWeight: 600, color: 'var(--text-main)', outline: 'none', appearance: 'none', cursor: 'pointer' }}
            value={orderType}
            onChange={(e) => setOrderType(e.target.value)}
          >
            <option value="dine-in">Comedor</option>
            <option value="takeout">Llevar</option>
            <option value="delivery">Domicilio</option>
          </select>
        </div>

        <div className="pos-order-items-new" style={{ flex: 1, padding: '16px 24px', overflowY: 'auto' }}>
          {cart.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', gap: 16 }}>
              <ShoppingBag size={48} opacity={0.5} />
              <p style={{ fontWeight: 500 }}>Tu orden está vacía</p>
            </div>
          ) : (
            cart.map(item => (
              <div key={item.id} className="pos-order-item-new" style={{ padding: '16px 0', borderBottom: '1px dashed #e2e8f0', display: 'flex', gap: 16, alignItems: 'center' }}>
                <div style={{ width: 48, height: 48, borderRadius: 12, background: '#f8fafc', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, overflow: 'hidden' }}>
                  {item.image_url ? (
                    <img src={item.image_url} alt={item.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  ) : (
                    getProductIcon(item.category, 24)
                  )}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '0.95rem', marginBottom: 4 }}>{item.name}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{formatCurrency(item.price)}</div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
                  <div style={{ fontWeight: 700, color: 'var(--text-main)' }}>{formatCurrency(item.price * item.quantity)}</div>
                  <div className="pos-order-item-actions" style={{ background: '#f8fafc', padding: 4, borderRadius: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <button style={{ width: 24, height: 24, borderRadius: '50%', border: 'none', background: 'white', color: 'var(--text-main)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }} onClick={() => updateQuantity(item.id, -1)}><Minus size={12} strokeWidth={3} /></button>
                    <span style={{ fontSize: '0.9rem', fontWeight: 600, minWidth: 16, textAlign: 'center' }}>{item.quantity}</span>
                    <button style={{ width: 24, height: 24, borderRadius: '50%', border: 'none', background: 'white', color: 'var(--text-main)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }} onClick={() => updateQuantity(item.id, 1)}><Plus size={12} strokeWidth={3} /></button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="pos-order-footer-new" style={{ background: '#f8fafc', padding: '24px', borderTop: '1px solid #f1f5f9' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12, color: 'var(--text-muted)', fontSize: '0.95rem' }}>
            <span>Subtotal</span>
            <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{formatCurrency(subtotal)}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, color: 'var(--text-muted)', fontSize: '0.95rem' }}>
            <span>IVA (16%)</span>
            <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{formatCurrency(tax)}</span>
          </div>
          <div style={{ borderTop: '1px dashed #cbd5e1', margin: '16px 0' }}></div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24, fontSize: '1.25rem', fontWeight: 800 }}>
            <span>TOTAL</span>
            <span style={{ color: 'var(--text-main)' }}>{formatCurrency(total)}</span>
          </div>
          
          <button 
            style={{ width: '100%', padding: '18px', background: '#3b82f6', color: 'white', border: 'none', borderRadius: 16, fontSize: '1.1rem', fontWeight: 600, cursor: cart.length === 0 ? 'not-allowed' : 'pointer', opacity: cart.length === 0 ? 0.5 : 1, boxShadow: '0 8px 16px rgba(59, 130, 246, 0.25)', transition: 'all 0.2s' }} 
            onClick={() => setPaymentOpen(true)} 
            disabled={cart.length === 0}
            onMouseOver={(e) => { if (cart.length > 0) e.currentTarget.style.transform = 'translateY(-2px)'; }}
            onMouseOut={(e) => { e.currentTarget.style.transform = 'translateY(0)'; }}
          >
            Procesar Cobro
          </button>
        </div>
      </aside>

      {/* Right side: Main Menu */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'white', borderRadius: 24, padding: '32px', boxShadow: '0 10px 40px rgba(0,0,0,0.02)', overflow: 'hidden' }}>
        
        {/* Top Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ width: 48, height: 48, borderRadius: '50%', background: '#eff6ff', color: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Coffee size={24} />
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-main)' }}>
                {new Date().toLocaleDateString('en-US', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}
              </span>
              <span style={{ color: '#cbd5e1', margin: '0 4px' }}>-</span>
              <span style={{ fontSize: '1.1rem', fontWeight: 500, color: '#64748b' }}>
                {new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 20px', background: '#ecfdf5', color: '#059669', borderRadius: 24, fontWeight: 600, fontSize: '0.95rem' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981' }}></div>
              Orden Abierta
            </div>
            <button style={{ width: 44, height: 44, borderRadius: '50%', border: '1px solid #e2e8f0', background: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
              <Bell size={20} color="#64748b" />
            </button>
          </div>
        </div>

        {/* Categories (Cards style) */}
        <div className="pos-categories" style={{ display: 'flex', gap: 16, overflowX: 'auto', paddingBottom: 16, marginBottom: 24 }}>
          {categories.map(cat => {
            const isActive = activeCategory === cat;
            return (
              <button 
                key={cat}
                onClick={() => setActiveCategory(cat)}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 12,
                  minWidth: 100,
                  height: 110,
                  padding: 16,
                  borderRadius: 20,
                  border: isActive ? '1px solid #3b82f6' : '1px solid #f1f5f9',
                  background: 'white',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  boxShadow: isActive ? '0 4px 12px rgba(59, 130, 246, 0.15)' : '0 2px 8px rgba(0,0,0,0.02)'
                }}
              >
                <div style={{ 
                  width: 48, height: 48, borderRadius: '50%', 
                  background: isActive ? '#3b82f6' : '#f8fafc',
                  color: isActive ? 'white' : '#64748b',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  {getProductIcon(cat, 24)}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                  <span style={{ fontSize: '0.95rem', fontWeight: 600, color: isActive ? '#3b82f6' : 'var(--text-main)' }}>{cat}</span>
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                    {cat === 'Todas' ? products.length : products.filter(p => p.category === cat).length} Artículos
                  </span>
                </div>
              </button>
            )
          })}
        </div>

        <div style={{ marginBottom: 32, position: 'relative' }}>
          <div style={{ position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }}>
            <Search size={20} />
          </div>
          <input 
            type="text" 
            placeholder="Buscar un antojo..." 
            style={{ width: '100%', padding: '16px 48px 16px 20px', borderRadius: 16, border: '1px solid #e2e8f0', background: 'white', fontSize: '1rem', outline: 'none', boxSizing: 'border-box', boxShadow: '0 2px 8px rgba(0,0,0,0.02)' }} 
          />
        </div>

        {/* Products Grid */}
        <div className="pos-products-grid" style={{ flex: 1, overflowY: 'auto', paddingRight: 8, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 24, alignContent: 'start' }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', gridColumn: '1 / -1' }}>Cargando menú...</div>
          ) : filteredProducts.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', gridColumn: '1 / -1' }}>No hay productos en esta categoría.</div>
          ) : (
            filteredProducts.map(product => {
              // Categorize colors
              let badgeBg = '#f1f5f9';
              let badgeColor = '#64748b';
              const catLower = (product.category || '').toLowerCase();
              if (catLower.includes('pan') || catLower.includes('sandwich')) { badgeBg = '#fff7ed'; badgeColor = '#ea580c'; }
              if (catLower.includes('bebida') || catLower.includes('jugo')) { badgeBg = '#eff6ff'; badgeColor = '#3b82f6'; }
              if (catLower.includes('postre') || catLower.includes('cake')) { badgeBg = '#fdf4ff'; badgeColor = '#d946ef'; }
              if (catLower.includes('café') || catLower.includes('matcha')) { badgeBg = '#f0fdf4'; badgeColor = '#16a34a'; }

              return (
                <div 
                  key={product.id} 
                  className="pos-product-card-new" 
                  onClick={() => addToCart(product)}
                  style={{ 
                    background: 'white', border: '1px solid #f1f5f9', borderRadius: 24, padding: 16, 
                    cursor: 'pointer', transition: 'all 0.2s', boxShadow: '0 4px 12px rgba(0,0,0,0.03)',
                    display: 'flex', flexDirection: 'column'
                  }}
                  onMouseOver={(e) => { e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.boxShadow = '0 12px 24px rgba(0,0,0,0.06)'; }}
                  onMouseOut={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.03)'; }}
                >
                  <div style={{ width: '100%', height: 160, background: '#f8fafc', borderRadius: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16, overflow: 'hidden' }}>
                    {product.image_url ? (
                      <img src={product.image_url} alt={product.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    ) : (
                      getProductIcon(product.category, 64)
                    )}
                  </div>
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                    <div style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: 12, lineHeight: 1.3 }}>{product.name}</div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto' }}>
                      <span style={{ background: badgeBg, color: badgeColor, padding: '4px 8px', borderRadius: 8, fontSize: '0.75rem', fontWeight: 600 }}>
                        {product.category || 'Item'}
                      </span>
                      <span style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>{formatCurrency(product.price)}</span>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Payment Modal (Keep exactly as before) */}
      <Modal isOpen={isPaymentOpen} onClose={() => setPaymentOpen(false)} title="Cobrar Cuenta">
        <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
          <button 
            style={{ flex: 1, padding: '12px', background: orderType === 'dine-in' ? 'var(--primary)' : 'var(--app-bg)', color: orderType === 'dine-in' ? 'white' : 'var(--text-main)', borderRadius: '12px', border: 'none', fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s' }}
            onClick={() => setOrderType('dine-in')}
          >Comedor</button>
          <button 
            style={{ flex: 1, padding: '12px', background: orderType === 'takeout' ? 'var(--primary)' : 'var(--app-bg)', color: orderType === 'takeout' ? 'white' : 'var(--text-main)', borderRadius: '12px', border: 'none', fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s' }}
            onClick={() => setOrderType('takeout')}
          >Para Llevar</button>
          <button 
            style={{ flex: 1, padding: '12px', background: orderType === 'delivery' ? 'var(--primary)' : 'var(--app-bg)', color: orderType === 'delivery' ? 'white' : 'var(--text-main)', borderRadius: '12px', border: 'none', fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s' }}
            onClick={() => setOrderType('delivery')}
          >Domicilio</button>
        </div>

        <div style={{ marginBottom: orderType !== 'dine-in' ? 16 : 24 }}>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>Nombre del Cliente / Propietario</label>
          <input 
            type="text" 
            value={ownerName}
            onChange={(e) => setOwnerName(e.target.value)}
            placeholder="Ej. Juan Pérez" 
            style={{ width: '100%', padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--glass-border)', fontSize: '1rem', outline: 'none' }}
          />
        </div>
        
        {orderType !== 'dine-in' && (
          <div style={{ marginBottom: orderType === 'delivery' ? 16 : 24 }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>Teléfono</label>
            <input 
              type="tel" 
              value={ownerPhone}
              onChange={(e) => setOwnerPhone(e.target.value)}
              placeholder="Ej. 555 123 4567" 
              style={{ width: '100%', padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--glass-border)', fontSize: '1rem', outline: 'none' }}
            />
          </div>
        )}

        {orderType === 'delivery' && (
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>Domicilio de Entrega</label>
            <input 
              type="text" 
              value={ownerAddress}
              onChange={(e) => setOwnerAddress(e.target.value)}
              placeholder="Ej. Av. Reforma 222, Int 4" 
              style={{ width: '100%', padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--glass-border)', fontSize: '1rem', outline: 'none' }}
            />
          </div>
        )}
        
        {orderType !== 'dine-in' && (
          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>Detalles o Referencias</label>
            <input 
              type="text" 
              value={orderDetails}
              onChange={(e) => setOrderDetails(e.target.value)}
              placeholder="Ej. Sin cebolla, portón negro..." 
              style={{ width: '100%', padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--glass-border)', fontSize: '1rem', outline: 'none' }}
            />
          </div>
        )}
        
        <div style={{ textAlign: 'center', fontSize: '3rem', fontWeight: 800, marginBottom: 32, color: 'var(--text-main)', letterSpacing: '-1px' }}>
          {formatCurrency(total)}
        </div>
        
        <div style={{ display: 'flex', gap: 12, marginTop: 32 }}>
          <button 
            style={{ flex: 1, padding: '16px', background: 'var(--app-bg)', color: 'var(--text-main)', borderRadius: '12px', border: 'none', fontWeight: 600, fontSize: '1rem', cursor: 'pointer' }} 
            onClick={() => setPaymentOpen(false)}
            disabled={isSubmitting}
          >Cancelar</button>
          <button 
            style={{ flex: 2, padding: '16px', background: 'var(--primary)', color: 'white', borderRadius: '12px', border: 'none', fontWeight: 600, fontSize: '1rem', cursor: isSubmitting ? 'not-allowed' : 'pointer', opacity: isSubmitting ? 0.7 : 1 }} 
            disabled={isSubmitting || cart.length === 0}
            onClick={async () => { 
              setIsSubmitting(true);
              try {
                const response = await fetch('/api/v1/orders', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    lines: cart.map(item => ({ product_id: String(item.id), quantity: item.quantity })),
                    owner_name: ownerName || 'Cliente General',
                    order_type: orderType,
                    branch_id: localStorage.getItem('pos_branch_id') || undefined,
                    register_id: localStorage.getItem('pos_register_id') || undefined,
                    metadata: {
                      phone: ownerPhone,
                      address: ownerAddress,
                      notes: orderDetails
                    }
                  })
                });
                if (response.ok) {
                  const orderData = await response.json();
                  const paymentRes = await fetch(`/api/v1/orders/${orderData.id}/payments`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      amount_cents: Math.round(total * 100),
                      method: 'cash'
                    })
                  });
                  if (paymentRes.ok) {
                    setPaymentOpen(false); 
                    setCart([]); 
                    setOwnerName('');
                    setOwnerPhone('');
                    setOwnerAddress('');
                    setOrderDetails('');
                    setOrderType('dine-in');
                    alert("¡Cobro realizado con éxito!");
                  } else {
                    alert("Pedido creado, pero error al procesar el cobro.");
                  }
                } else {
                  alert("Error al crear el pedido.");
                }
              } catch (e) {
                alert("Error de red.");
              } finally {
                setIsSubmitting(false);
              }
            }}
          >
            {isSubmitting ? 'Procesando...' : 'Completar Pago'}
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default PointOfSale;
