import React, { useState, useEffect } from 'react';
import { Modal } from '@restaurantos/ui';
import { ShoppingBag, Search, Bell, Plus, Minus, ArrowRight, Coffee, CupSoda, Sandwich, Salad, Wheat, Package, Utensils, Menu as MenuIcon, Users, Grid, Receipt, PiggyBank } from 'lucide-react';

const getProductIcon = (category: string, size: number = 40) => {
  const cat = (category || '').toLowerCase();
  if (cat.includes('café') || cat.includes('matcha')) return <Coffee size={size} strokeWidth={1.5} />;
  if (cat.includes('jugo') || cat.includes('agua') || cat.includes('bebida') || cat.includes('smoothie') || cat.includes('extracto') || cat.includes('drink')) return <CupSoda size={size} strokeWidth={1.5} />;
  if (cat.includes('ensalada')) return <Salad size={size} strokeWidth={1.5} />;
  if (cat.includes('panadería') || cat.includes('pan') || cat.includes('dessert')) return <Wheat size={size} strokeWidth={1.5} />;
  if (cat.includes('emparedado') || cat.includes('sando') || cat.includes('burger')) return <Sandwich size={size} strokeWidth={1.5} />;
  if (cat.includes('combo')) return <Package size={size} strokeWidth={1.5} />;
  return <Utensils size={size} strokeWidth={1.5} />;
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
  const [isCategoriesCollapsed, setCategoriesCollapsed] = useState(false);
  const [isPaymentOpen, setPaymentOpen] = useState(false);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  
  const [ownerName, setOwnerName] = useState('');
  const [ownerPhone, setOwnerPhone] = useState('');
  const [ownerAddress, setOwnerAddress] = useState('');
  const [orderDetails, setOrderDetails] = useState('');
  const [orderType, setOrderType] = useState('dine-in'); // 'dine-in', 'takeout', 'delivery'

  const [categories, setCategories] = useState<string[]>(['Todas']);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        const [catRes, prodRes] = await Promise.all([
          fetch('/api/v1/categories', { headers }),
          fetch(
            localStorage.getItem('pos_branch_id') 
              ? `/api/v1/catalog/products?branch_id=${encodeURIComponent(localStorage.getItem('pos_branch_id')!)}` 
              : '/api/v1/catalog/products',
            { headers }
          )
        ]);
        const catData = await catRes.json();
        const prodData = await prodRes.json();

        if (Array.isArray(catData)) {
          setCategories(['Todas', ...catData.map(c => c.name)]);
        }
        if (Array.isArray(prodData)) {
          const mappedProducts = prodData.map((p: any) => ({
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

  const filteredProducts = products.filter(p => {
    if (activeCategory !== 'Todas' && p.category !== activeCategory) return false;
    if (searchQuery && !p.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

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

  const processTransaction = async () => {
    try {
      const branchId = localStorage.getItem('pos_branch_id');
      const registerId = localStorage.getItem('pos_register_id');
      const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
      const authHeader = token ? { 'Authorization': `Bearer ${token}` } : {};

      const payload = {
        owner_name: ownerName || 'Cliente General',
        order_type: orderType,
        branch_id: branchId || undefined,
        register_id: registerId || undefined,
        lines: cart.map(item => ({
          product_id: item.id,
          quantity: item.quantity,
          notes: ''
        }))
      };
      const response = await fetch('/api/v1/orders', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...authHeader
        },
        body: JSON.stringify(payload)
      });
      if (response.ok) {
        const result = await response.json();
        const orderData = result.data || result;
        
        await fetch(`/api/v1/orders/${orderData.id}/payments`, {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            ...authHeader
          },
          body: JSON.stringify({
            amount_cents: Math.round(total * 100),
            method: 'cash'
          })
        });

        alert(`¡Transacción procesada! Orden #${orderData.folio}`);
        setCart([]);
        setPaymentOpen(false);
        setOwnerName('');
        setOrderDetails('');
      } else {
        alert("Error al crear la orden.");
      }
    } catch (e) {
      console.error(e);
      alert("Error de conexión");
    }
  };

  const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  const tax = subtotal * 0.16; // 16% IVA
  const total = subtotal + tax;

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', backgroundColor: '#f0f2f5', overflow: 'hidden' }}>
      
      {/* Top Navigation Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 24px', background: 'white', borderBottom: '1px solid #e2e8f0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button 
            onClick={() => setCategoriesCollapsed(!isCategoriesCollapsed)}
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <MenuIcon size={24} color="#64748b" />
          </button>
          <div style={{ color: '#10b981', fontWeight: 800, fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>🥝</span> <span style={{ color: '#1e293b' }}>Kiwi POS</span>
          </div>
        </div>

        <div style={{ width: '400px', position: 'relative' }}>
          <div style={{ position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }}>
            <Search size={20} />
          </div>
          <input 
            type="text" 
            placeholder="Search Product..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: '100%', padding: '12px 16px 12px 48px', borderRadius: 8, border: '1px solid #e2e8f0', background: 'white', fontSize: '1rem', outline: 'none', boxSizing: 'border-box' }} 
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center' }}>
           {/* Space for future icons or profile */}
           <div style={{ width: 40, height: 40, borderRadius: '50%', background: '#f1f5f9' }}></div>
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        
        {/* Left Category Sidebar */}
        <div style={{ 
          width: isCategoriesCollapsed ? '90px' : '140px', 
          background: 'white', 
          borderRight: '1px solid #e2e8f0', 
          display: 'flex', 
          flexDirection: 'column', 
          overflowY: 'auto',
          padding: '16px 0',
          transition: 'width 0.3s'
        }}>
          {categories.map(cat => {
            const isActive = activeCategory === cat;
            return (
              <div 
                key={cat}
                onClick={() => setActiveCategory(cat)}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  padding: '16px 8px',
                  cursor: 'pointer',
                  position: 'relative',
                  background: isActive ? '#f8fafc' : 'transparent',
                }}
              >
                {isActive && (
                  <div style={{ position: 'absolute', left: 0, top: '20%', bottom: '20%', width: 4, background: '#10b981', borderRadius: '0 4px 4px 0' }} />
                )}
                <div style={{ 
                  color: isActive ? '#10b981' : '#64748b',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  {getProductIcon(cat, 32)}
                </div>
                {!isCategoriesCollapsed && (
                  <span style={{ fontSize: '0.85rem', fontWeight: isActive ? 600 : 500, color: isActive ? '#1e293b' : '#64748b', textAlign: 'center' }}>
                    {cat === 'Todas' ? 'All Menu' : cat}
                  </span>
                )}
              </div>
            )
          })}
        </div>

        {/* Center Products Area */}
        <div style={{ flex: 1, padding: 24, overflowY: 'auto' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 20 }}>
            {loading ? (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', gridColumn: '1 / -1' }}>Cargando menú...</div>
            ) : filteredProducts.length === 0 ? (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', gridColumn: '1 / -1' }}>No hay productos.</div>
            ) : (
              filteredProducts.map(product => (
                <div 
                  key={product.id} 
                  onClick={() => addToCart(product)}
                  style={{ 
                    background: 'white', borderRadius: 12, padding: 16, cursor: 'pointer', 
                    boxShadow: '0 2px 4px rgba(0,0,0,0.02)', display: 'flex', flexDirection: 'column', alignItems: 'center'
                  }}
                >
                  <div style={{ width: '100%', height: 120, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 12 }}>
                    {product.image_url ? (
                      <img src={product.image_url} alt={product.name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                    ) : (
                      getProductIcon(product.category, 64)
                    )}
                  </div>
                  <div style={{ fontSize: '1rem', fontWeight: 600, color: '#1e293b', marginBottom: 4, textAlign: 'center' }}>{product.name}</div>
                  <div style={{ fontSize: '1rem', fontWeight: 500, color: '#64748b' }}>{formatCurrency(product.price)}</div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Cart Area */}
        <div style={{ width: '400px', background: 'white', borderLeft: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', padding: 24, flexShrink: 0 }}>
          
          {/* Action Buttons Top */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 24 }}>
             <button style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '16px', background: 'white', border: '1px solid #e2e8f0', borderRadius: 8, cursor: 'pointer', color: '#64748b' }}>
               <Users size={24} style={{ marginBottom: 8 }} />
               <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Customer</span>
             </button>
             <button style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '16px', background: 'white', border: '1px solid #e2e8f0', borderRadius: 8, cursor: 'pointer', color: '#64748b' }}>
               <Grid size={24} style={{ marginBottom: 8 }} />
               <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Tables</span>
             </button>
             <button style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '16px', background: 'white', border: '1px solid #e2e8f0', borderRadius: 8, cursor: 'pointer', color: '#64748b' }}>
               <PiggyBank size={24} style={{ marginBottom: 8 }} />
               <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Discount</span>
             </button>
             <button style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '16px', background: 'white', border: '1px solid #e2e8f0', borderRadius: 8, cursor: 'pointer', color: '#64748b' }}>
               <Receipt size={24} style={{ marginBottom: 8 }} />
               <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Save Bill</span>
             </button>
          </div>

          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#1e293b', margin: '0 0 16px 0' }}>Order Details</h2>

          {/* Dine In / Take Away Toggle */}
          <div style={{ display: 'flex', background: '#f8fafc', borderRadius: 8, padding: 4, marginBottom: 24 }}>
            <button 
              onClick={() => setOrderType('dine-in')}
              style={{ flex: 1, padding: '8px', background: orderType === 'dine-in' ? 'white' : 'transparent', border: 'none', borderRadius: 6, fontWeight: 600, color: orderType === 'dine-in' ? '#10b981' : '#64748b', cursor: 'pointer', boxShadow: orderType === 'dine-in' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', borderBottom: orderType === 'dine-in' ? '2px solid #10b981' : 'none' }}
            >
              Dine In
            </button>
            <button 
              onClick={() => setOrderType('takeaway')}
              style={{ flex: 1, padding: '8px', background: orderType !== 'dine-in' ? 'white' : 'transparent', border: 'none', borderRadius: 6, fontWeight: 600, color: orderType !== 'dine-in' ? '#10b981' : '#64748b', cursor: 'pointer', boxShadow: orderType !== 'dine-in' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', borderBottom: orderType !== 'dine-in' ? '2px solid #10b981' : 'none' }}
            >
              Take Away
            </button>
          </div>

          {/* Cart Items */}
          <div style={{ flex: 1, overflowY: 'auto', marginBottom: 24 }}>
            {cart.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}>
                <div style={{ width: 80, height: 80, borderRadius: '50%', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
                  <ShoppingBag size={40} opacity={0.5} />
                </div>
                <h3 style={{ margin: '0 0 8px 0', color: '#1e293b' }}>No Order</h3>
                <p style={{ margin: 0, fontSize: '0.85rem' }}>Tap the product to add into order</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {cart.map(item => (
                  <div key={item.id} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ width: 48, height: 48, borderRadius: 8, background: '#f8fafc', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      {item.image_url ? (
                        <img src={item.image_url} alt={item.name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                      ) : (
                        getProductIcon(item.category, 24)
                      )}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#1e293b', marginBottom: 4 }}>{item.name}</div>
                      <div style={{ fontSize: '0.85rem', color: '#64748b' }}>{formatCurrency(item.price)}</div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                       <div style={{ fontWeight: 600, color: '#1e293b' }}>{formatCurrency(item.price * item.quantity)}</div>
                       <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#f1f5f9', borderRadius: 4, padding: '2px 4px' }}>
                         <button onClick={() => updateQuantity(item.id, -1)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#64748b' }}><Minus size={14} /></button>
                         <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{item.quantity}</span>
                         <button onClick={() => updateQuantity(item.id, 1)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#64748b' }}><Plus size={14} /></button>
                       </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Totals & Process */}
          <div style={{ background: '#f8fafc', borderRadius: 12, padding: 16, marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12, color: '#64748b', fontSize: '0.9rem' }}>
              <span>Subtotal</span>
              <span>{formatCurrency(subtotal)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12, color: '#64748b', fontSize: '0.9rem' }}>
              <span>Tax</span>
              <span>{formatCurrency(tax)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, color: '#64748b', fontSize: '0.9rem' }}>
              <span>Voucher</span>
              <span>$ 0.00</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #e2e8f0', paddingTop: 16, fontSize: '1.25rem', fontWeight: 800, color: '#1e293b' }}>
              <span>Total</span>
              <span>{formatCurrency(total)}</span>
            </div>
          </div>

          <button 
            onClick={() => setPaymentOpen(true)}
            disabled={cart.length === 0}
            style={{ 
              width: '100%', padding: '16px', borderRadius: 8, border: 'none', fontSize: '1rem', fontWeight: 600, 
              background: cart.length === 0 ? '#e2e8f0' : '#10b981', 
              color: cart.length === 0 ? '#94a3b8' : 'white',
              cursor: cart.length === 0 ? 'not-allowed' : 'pointer' 
            }}
          >
            Process Transaction
          </button>
        </div>
      </div>

      {/* Payment Modal for finishing the order */}
      <Modal isOpen={isPaymentOpen} onClose={() => setPaymentOpen(false)} title="Finalizar Venta">
        <div style={{ marginBottom: 16 }}>
           <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>Nombre del Cliente</label>
           <input 
             type="text" 
             value={ownerName}
             onChange={(e) => setOwnerName(e.target.value)}
             placeholder="Ej. Juan Pérez" 
             style={{ width: '100%', padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--glass-border)', fontSize: '1rem', outline: 'none' }}
           />
        </div>
        <button 
           onClick={processTransaction}
           style={{ width: '100%', padding: '16px', borderRadius: 8, border: 'none', fontSize: '1rem', fontWeight: 600, background: '#10b981', color: 'white', cursor: 'pointer' }}
        >
          Confirmar y Pagar {formatCurrency(total)}
        </button>
      </Modal>

    </div>
  );
};

export default PointOfSale;
