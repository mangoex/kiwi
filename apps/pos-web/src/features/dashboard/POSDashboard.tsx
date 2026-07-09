import React, { useState } from 'react';
import { Sidebar, SidebarItem, Card, Button, Input, Modal, Badge } from '@restaurantos/ui';
import { LayoutDashboard, Settings, ShoppingBag, CreditCard, Search, User, Check, X, Bell, LogOut, Clock, Plus, Minus, Home, Package, ShoppingCart, Users, Trash2 } from 'lucide-react';

const POSDashboard = () => {
  const [activeCategory, setActiveCategory] = useState('All');
  const [isPaymentOpen, setPaymentOpen] = useState(false);

  const categories = ['All', 'Foods', 'Beverage', 'Other'];
  
  const products = [
    { id: 1, name: 'Healthy Salad', price: 10000, category: 'Foods' },
    { id: 2, name: 'Smooky Beef', price: 30000, category: 'Foods' },
    { id: 3, name: 'Tropical Smoothies', price: 10000, category: 'Beverage' },
    { id: 4, name: 'Salmon Coco Sauce', price: 10000, category: 'Foods' },
    { id: 5, name: 'Indomie Seafood', price: 10000, category: 'Foods' },
    { id: 6, name: 'Kimchi Rice', price: 10000, category: 'Foods' },
  ];

  const filteredProducts = activeCategory === 'All' ? products : products.filter(p => p.category === activeCategory);

  return (
    <div className="pos-layout">
      {/* Left Sidebar Menu */}
      <Sidebar>
        <div style={{ padding: '12px 16px', fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-blue)', marginBottom: 24 }}>
          RestaurantOS
        </div>
        <Input icon={<Search size={16} />} placeholder="Search" style={{ marginBottom: 24 }} />
        
        <SidebarItem icon={<Home size={20} />} label="Dashboard" />
        <SidebarItem icon={<Package size={20} />} label="Inventory" />
        <SidebarItem icon={<ShoppingCart size={20} />} label="Sales" active />
        <SidebarItem icon={<Users size={20} />} label="Customers" />
        
        <div style={{ flex: 1 }} />
        
        <SidebarItem icon={<Settings size={20} />} label="Settings" />
        <SidebarItem icon={<LogOut size={20} />} label="Log out" />
      </Sidebar>

      {/* Main Content Area */}
      <main className="pos-main-content">
        <div className="pos-dashboard-header">
          <h1 className="pos-dashboard-title">Sales Transaction</h1>
          <div className="pos-dashboard-date">{new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</div>
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
            <Card key={product.id} className="pos-product-card">
              <div className="pos-product-image" />
              <div className="pos-product-title">{product.name}</div>
              <div className="pos-product-price">Rp {product.price.toLocaleString()}</div>
            </Card>
          ))}
        </div>
      </main>

      {/* Right Order Sidebar */}
      <aside className="pos-order-sidebar">
        <div className="pos-order-header">Detail Order</div>
        
        <div className="pos-order-items">
          {/* Sample Order Item */}
          <div className="pos-order-item">
            <div className="pos-order-item-img" />
            <div className="pos-order-item-details">
              <div className="pos-order-item-title">Healthy Salad</div>
              <div className="pos-order-item-price">Rp 10.000</div>
            </div>
            <div className="pos-order-item-actions">
              <Button size="sm" variant="ghost"><Minus size={14} /></Button>
              <span>1</span>
              <Button size="sm" variant="ghost"><Plus size={14} /></Button>
              <Button size="sm" variant="danger" style={{ marginLeft: 8 }}><Trash2 size={14} /></Button>
            </div>
          </div>
        </div>

        <div className="pos-order-footer">
          <div className="pos-order-summary-row">
            <span>Subtotal (1)</span>
            <span>Rp 10.000</span>
          </div>
          <div className="pos-order-summary-row">
            <span>Service Tax</span>
            <span>Rp 1.000</span>
          </div>
          <div className="pos-order-summary-row pos-order-summary-total">
            <span>Total payment</span>
            <span>Rp 11.000</span>
          </div>
          
          <Button fullWidth onClick={() => setPaymentOpen(true)}>Make Order</Button>
        </div>
      </aside>

      {/* Payment Modal */}
      <Modal isOpen={isPaymentOpen} onClose={() => setPaymentOpen(false)} title="Collect Payment">
        <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
          <Button fullWidth variant="primary">Full Payment</Button>
          <Button fullWidth variant="secondary">Split Bill</Button>
        </div>
        
        <div style={{ textAlign: 'center', fontSize: '2rem', fontWeight: 700, marginBottom: 24 }}>
          Rp 11.000
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, '.', 0, 'C'].map(key => (
            <Button key={key} variant="secondary" size="lg">{key}</Button>
          ))}
        </div>
        
        <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
          <Button fullWidth variant="secondary" onClick={() => setPaymentOpen(false)}>Cancel</Button>
          <Button fullWidth variant="primary">Complete Payment</Button>
        </div>
      </Modal>
    </div>
  );
};

export default POSDashboard;
