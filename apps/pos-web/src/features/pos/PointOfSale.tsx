import React, { useState } from 'react';
import { Modal } from '@restaurantos/ui';
import { ShoppingBag, Search, Bell, Plus, Minus, ArrowRight } from 'lucide-react';

// Product images (placeholders for UI)
const PRODUCT_IMAGES = [
  'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400&q=80',
  'https://images.unsplash.com/photo-1600891964092-4316c288032e?w=400&q=80',
  'https://images.unsplash.com/photo-1623065422902-30a2d299bbe4?w=400&q=80',
  'https://images.unsplash.com/photo-1481931098730-318b6f776db0?w=400&q=80',
  'https://images.unsplash.com/photo-1617093901362-a5652599bc0e?w=400&q=80',
  'https://images.unsplash.com/photo-1588168333986-5078d3ae3976?w=400&q=80'
];

interface Product {
  id: number;
  name: string;
  price: number;
  category: string;
  image: string;
}

interface CartItem extends Product {
  quantity: number;
}

const PointOfSale = () => {
  const [activeCategory, setActiveCategory] = useState('Todas');
  const [isPaymentOpen, setPaymentOpen] = useState(false);
  const [cart, setCart] = useState<CartItem[]>([]);
  
  const [ownerName, setOwnerName] = useState('');
  const [orderType, setOrderType] = useState('dine-in');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const categories = ['Todas', 'Comidas', 'Bebidas', 'Postres', 'Otros'];
  
  const products: Product[] = [
    { id: 1, name: 'Ensalada Saludable', price: 100, category: 'Comidas', image: PRODUCT_IMAGES[0] },
    { id: 2, name: 'Corte de Carne Ahumado', price: 300, category: 'Comidas', image: PRODUCT_IMAGES[1] },
    { id: 3, name: 'Smoothie Tropical', price: 150, category: 'Bebidas', image: PRODUCT_IMAGES[2] },
    { id: 4, name: 'Salmón en Salsa de Coco', price: 450, category: 'Comidas', image: PRODUCT_IMAGES[3] },
    { id: 5, name: 'Fideos Picantes con Mariscos', price: 250, category: 'Comidas', image: PRODUCT_IMAGES[4] },
    { id: 6, name: 'Arroz Frito Kimchi', price: 200, category: 'Comidas', image: PRODUCT_IMAGES[5] },
  ];

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

  const updateQuantity = (id: number, delta: number) => {
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
    <>
      <div className="pos-dashboard-header" style={{ padding: '24px 32px' }}>
        <div>
          <h1 className="pos-dashboard-title">Punto de Venta</h1>
          <div className="pos-dashboard-date">{new Date().toLocaleDateString('es-MX', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</div>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ background: 'white', padding: '12px 16px', borderRadius: '12px', display: 'flex', alignItems: 'center', gap: 12, color: 'var(--text-muted)', boxShadow: '0 2px 10px rgba(0,0,0,0.05)', minWidth: 300 }}>
            <Search size={18} />
            <input type="text" placeholder="Buscar menú..." style={{ background: 'transparent', border: 'none', outline: 'none', width: '100%', fontSize: '0.95rem' }} />
          </div>
          <button style={{ background: 'white', border: '1px solid var(--glass-border)', borderRadius: '50%', width: 48, height: 48, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', boxShadow: '0 2px 10px rgba(0,0,0,0.05)' }}>
            <Bell size={20} color="var(--text-main)" />
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, background: 'white', padding: '8px 16px 8px 8px', borderRadius: '30px', boxShadow: '0 2px 10px rgba(0,0,0,0.05)' }}>
            <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--primary)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>JD</div>
            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>Juan Pérez</span>
          </div>
        </div>
      </div>

      <div style={{ padding: '0 32px', display: 'flex', flex: 1, gap: 32, overflow: 'hidden' }}>
        {/* Left side: Menu items */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="pos-categories" style={{ padding: 0 }}>
            {categories.map(cat => (
              <button 
                key={cat}
                className={`pos-category-btn ${activeCategory === cat ? 'active' : ''}`}
                onClick={() => setActiveCategory(cat)}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="pos-products-grid" style={{ padding: 0, paddingBottom: 24, flex: 1, overflowY: 'auto' }}>
            {filteredProducts.map(product => (
              <div key={product.id} className="pos-product-card" onClick={() => addToCart(product)}>
                <div className="pos-product-image-wrapper">
                  <img src={product.image} alt={product.name} className="pos-product-image" />
                </div>
                <div className="pos-product-info">
                  <div className="pos-product-title">{product.name}</div>
                  <div className="pos-product-price">{formatCurrency(product.price)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right side: Order Sidebar inside the page */}
        <aside className="pos-order-sidebar" style={{ position: 'relative', width: 400, borderLeft: 'none', background: 'white', borderRadius: 24, boxShadow: '0 10px 40px rgba(0,0,0,0.05)', marginBottom: 24, display: 'flex', flexDirection: 'column' }}>
          <div className="pos-order-header">
            <span>Orden Actual</span>
            <span style={{ background: 'var(--primary)', color: 'white', fontSize: '0.85rem', padding: '4px 10px', borderRadius: '12px' }}>Orden #1042</span>
          </div>
          
          <div className="pos-order-items" style={{ flex: 1 }}>
            {cart.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', gap: 16 }}>
                <ShoppingBag size={48} opacity={0.5} />
                <p>Tu carrito está vacío</p>
              </div>
            ) : (
              cart.map(item => (
                <div key={item.id} className="pos-order-item">
                  <img src={item.image} alt={item.name} className="pos-order-item-img" />
                  <div className="pos-order-item-details">
                    <div className="pos-order-item-title">{item.name}</div>
                    <div className="pos-order-item-price">{formatCurrency(item.price * item.quantity)}</div>
                  </div>
                  <div className="pos-order-item-actions">
                    <button onClick={() => updateQuantity(item.id, -1)}><Minus size={14} /></button>
                    <span>{item.quantity}</span>
                    <button onClick={() => updateQuantity(item.id, 1)}><Plus size={14} /></button>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="pos-order-footer">
            <div className="pos-order-summary-row">
              <span>Subtotal</span>
              <span>{formatCurrency(subtotal)}</span>
            </div>
            <div className="pos-order-summary-row">
              <span>Impuesto (16%)</span>
              <span>{formatCurrency(tax)}</span>
            </div>
            <div className="pos-order-summary-row pos-order-summary-total">
              <span>Total a Pagar</span>
              <span>{formatCurrency(total)}</span>
            </div>
            
            <button className="pos-pay-btn" onClick={() => setPaymentOpen(true)} disabled={cart.length === 0} style={{ opacity: cart.length === 0 ? 0.5 : 1, cursor: cart.length === 0 ? 'not-allowed' : 'pointer' }}>
              <span>Cobrar {formatCurrency(total)}</span>
              <ArrowRight size={20} />
            </button>
          </div>
        </aside>
      </div>

      {/* Payment Modal */}
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

        <div style={{ marginBottom: 24 }}>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>Nombre del Cliente / Propietario</label>
          <input 
            type="text" 
            value={ownerName}
            onChange={(e) => setOwnerName(e.target.value)}
            placeholder="Ej. Juan Pérez" 
            style={{ width: '100%', padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--glass-border)', fontSize: '1rem', outline: 'none' }}
          />
        </div>
        
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
                    order_type: orderType
                  })
                });
                if (response.ok) {
                  setPaymentOpen(false); 
                  setCart([]); 
                  setOwnerName('');
                  setOrderType('dine-in');
                  alert("¡Cobro realizado con éxito!");
                } else {
                  alert("Error al procesar el cobro.");
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
    </>
  );
};

export default PointOfSale;
