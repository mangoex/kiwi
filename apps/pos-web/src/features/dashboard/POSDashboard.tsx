import React, { useState } from 'react';
import { Sidebar, SidebarItem, Modal } from '@restaurantos/ui';
import { LayoutDashboard, Settings, ShoppingBag, CreditCard, Search, User, Check, X, Bell, LogOut, Clock, Plus, Minus, Home, Package, ShoppingCart, Users, Trash2, ArrowRight } from 'lucide-react';

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

const POSDashboard = () => {
  const [activeCategory, setActiveCategory] = useState('All');
  const [isPaymentOpen, setPaymentOpen] = useState(false);
  const [cart, setCart] = useState<CartItem[]>([]);

  const categories = ['All', 'Foods', 'Beverage', 'Desserts', 'Other'];
  
  const products: Product[] = [
    { id: 1, name: 'Healthy Salad', price: 10000, category: 'Foods', image: PRODUCT_IMAGES[0] },
    { id: 2, name: 'Smoky Beef Grill', price: 30000, category: 'Foods', image: PRODUCT_IMAGES[1] },
    { id: 3, name: 'Tropical Smoothie', price: 15000, category: 'Beverage', image: PRODUCT_IMAGES[2] },
    { id: 4, name: 'Salmon Coco Sauce', price: 45000, category: 'Foods', image: PRODUCT_IMAGES[3] },
    { id: 5, name: 'Spicy Seafood Noodle', price: 25000, category: 'Foods', image: PRODUCT_IMAGES[4] },
    { id: 6, name: 'Kimchi Fried Rice', price: 20000, category: 'Foods', image: PRODUCT_IMAGES[5] },
  ];

  const filteredProducts = activeCategory === 'All' ? products : products.filter(p => p.category === activeCategory);

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
  const tax = subtotal * 0.1;
  const total = subtotal + tax;

  return (
    <div className="pos-layout">
      {/* Left Sidebar Menu */}
      <Sidebar>
        <div style={{ padding: '24px 16px', fontSize: '1.5rem', fontWeight: 800, color: 'var(--primary)', letterSpacing: '-0.5px' }}>
          Resto<span style={{color: 'var(--text-main)'}}>OS</span>
        </div>
        
        <div style={{ padding: '0 16px', marginBottom: 32 }}>
          <div style={{ background: 'var(--app-bg)', padding: '12px 16px', borderRadius: '12px', display: 'flex', alignItems: 'center', gap: 12, color: 'var(--text-muted)' }}>
            <Search size={18} />
            <input type="text" placeholder="Search menu..." style={{ background: 'transparent', border: 'none', outline: 'none', width: '100%', fontSize: '0.95rem' }} />
          </div>
        </div>
        
        <SidebarItem icon={<Home size={22} />} label="Dashboard" />
        <SidebarItem icon={<Package size={22} />} label="Inventory" />
        <SidebarItem icon={<ShoppingCart size={22} />} label="Point of Sale" active />
        <SidebarItem icon={<Users size={22} />} label="Customers" />
        <SidebarItem icon={<Clock size={22} />} label="History" />
        
        <div style={{ flex: 1 }} />
        
        <SidebarItem icon={<Settings size={22} />} label="Settings" />
        <SidebarItem icon={<LogOut size={22} />} label="Log out" />
      </Sidebar>

      {/* Main Content Area */}
      <main className="pos-main-content">
        <div className="pos-dashboard-header">
          <div>
            <h1 className="pos-dashboard-title">Point of Sale</h1>
            <div className="pos-dashboard-date">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</div>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <button style={{ background: 'white', border: '1px solid var(--glass-border)', borderRadius: '50%', width: 48, height: 48, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', boxShadow: '0 2px 10px rgba(0,0,0,0.05)' }}>
              <Bell size={20} color="var(--text-main)" />
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, background: 'white', padding: '8px 16px 8px 8px', borderRadius: '30px', boxShadow: '0 2px 10px rgba(0,0,0,0.05)' }}>
              <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--primary)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>JD</div>
              <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>John Doe</span>
            </div>
          </div>
        </div>

        <div className="pos-categories">
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

        <div className="pos-products-grid">
          {filteredProducts.map(product => (
            <div key={product.id} className="pos-product-card" onClick={() => addToCart(product)}>
              <div className="pos-product-image-wrapper">
                <img src={product.image} alt={product.name} className="pos-product-image" />
              </div>
              <div className="pos-product-info">
                <div className="pos-product-title">{product.name}</div>
                <div className="pos-product-price">Rp {product.price.toLocaleString()}</div>
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* Right Order Sidebar */}
      <aside className="pos-order-sidebar">
        <div className="pos-order-header">
          <span>Current Order</span>
          <span style={{ background: 'var(--primary)', color: 'white', fontSize: '0.85rem', padding: '4px 10px', borderRadius: '12px' }}>Order #1042</span>
        </div>
        
        <div className="pos-order-items">
          {cart.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', gap: 16 }}>
              <ShoppingBag size={48} opacity={0.5} />
              <p>Your cart is empty</p>
            </div>
          ) : (
            cart.map(item => (
              <div key={item.id} className="pos-order-item">
                <img src={item.image} alt={item.name} className="pos-order-item-img" />
                <div className="pos-order-item-details">
                  <div className="pos-order-item-title">{item.name}</div>
                  <div className="pos-order-item-price">Rp {(item.price * item.quantity).toLocaleString()}</div>
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
            <span>Rp {subtotal.toLocaleString()}</span>
          </div>
          <div className="pos-order-summary-row">
            <span>Tax (10%)</span>
            <span>Rp {tax.toLocaleString()}</span>
          </div>
          <div className="pos-order-summary-row pos-order-summary-total">
            <span>Total Payment</span>
            <span>Rp {total.toLocaleString()}</span>
          </div>
          
          <button className="pos-pay-btn" onClick={() => setPaymentOpen(true)} disabled={cart.length === 0} style={{ opacity: cart.length === 0 ? 0.5 : 1, cursor: cart.length === 0 ? 'not-allowed' : 'pointer' }}>
            <span>Charge Rp {total.toLocaleString()}</span>
            <ArrowRight size={20} />
          </button>
        </div>
      </aside>

      {/* Payment Modal */}
      <Modal isOpen={isPaymentOpen} onClose={() => setPaymentOpen(false)} title="Collect Payment">
        <div style={{ display: 'flex', gap: 12, marginBottom: 32 }}>
          <button style={{ flex: 1, padding: '16px', background: 'var(--primary)', color: 'white', borderRadius: '12px', border: 'none', fontWeight: 600, fontSize: '1rem', cursor: 'pointer' }}>Full Payment</button>
          <button style={{ flex: 1, padding: '16px', background: 'var(--app-bg)', color: 'var(--text-main)', borderRadius: '12px', border: 'none', fontWeight: 600, fontSize: '1rem', cursor: 'pointer' }}>Split Bill</button>
        </div>
        
        <div style={{ textAlign: 'center', fontSize: '3rem', fontWeight: 800, marginBottom: 32, color: 'var(--text-main)', letterSpacing: '-1px' }}>
          Rp {total.toLocaleString()}
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, '.', 0, 'C'].map(key => (
            <button key={key} style={{ padding: '16px', fontSize: '1.25rem', fontWeight: 600, background: 'var(--app-bg)', border: 'none', borderRadius: '12px', cursor: 'pointer', transition: 'background 0.2s' }}>
              {key}
            </button>
          ))}
        </div>
        
        <div style={{ display: 'flex', gap: 12, marginTop: 32 }}>
          <button style={{ flex: 1, padding: '16px', background: 'var(--app-bg)', color: 'var(--text-main)', borderRadius: '12px', border: 'none', fontWeight: 600, fontSize: '1rem', cursor: 'pointer' }} onClick={() => setPaymentOpen(false)}>Cancel</button>
          <button style={{ flex: 2, padding: '16px', background: 'var(--primary)', color: 'white', borderRadius: '12px', border: 'none', fontWeight: 600, fontSize: '1rem', cursor: 'pointer' }} onClick={() => { setPaymentOpen(false); setCart([]); }}>Complete Payment</button>
        </div>
      </Modal>
    </div>
  );
};

export default POSDashboard;

