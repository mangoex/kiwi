import React, { useState } from 'react';
import { Sidebar, SidebarItem, Card, Button, Badge } from '@restaurantos/ui';
import { ChefHat, CheckCircle2, CheckCircle, Clock, Play, ListOrdered, Settings, UtensilsCrossed, Monitor, ArrowRight } from 'lucide-react';

const KitchenBoard = () => {
  return (
    <div className="kds-layout">
      <header className="kds-header">
        <div style={{ fontSize: '1.5rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 12 }}>
          <ChefHat size={28} color="var(--color-orange)" />
          Sistema KDS
        </div>
        <div style={{ display: 'flex', gap: 16 }}>
          <Badge variant="info">Estación: Cocina Caliente</Badge>
          <div style={{ fontWeight: 500 }}>{new Date().toLocaleTimeString()}</div>
        </div>
      </header>

      <div className="kds-board">
        {/* Pending Column */}
        <div className="kds-column" style={{ borderColor: 'var(--color-border)' }}>
          <div className="kds-column-header" style={{ borderBottomColor: 'var(--color-border)' }}>
            <div className="kds-column-title">
              <Clock size={20} color="var(--color-text-muted)" /> Pendiente
            </div>
            <div className="kds-column-count">3</div>
          </div>
          
          <Card className="kds-order-card" style={{ borderLeftColor: 'var(--color-border)' }}>
            <div style={{ padding: 16 }}>
              <div className="kds-order-header">
                <div className="kds-order-number">#1042</div>
                <div className="kds-order-time">hace 2m</div>
              </div>
              <div className="kds-order-items">
                <div className="kds-order-item"><span>1x Ensalada Saludable</span></div>
                <div className="kds-order-item"><span>2x Smoothie Tropical</span></div>
              </div>
              <div className="kds-order-footer">
                <Button size="sm" variant="primary">Empezar</Button>
              </div>
            </div>
          </Card>
        </div>

        {/* Cooking Column */}
        <div className="kds-column" style={{ borderColor: 'var(--color-orange-light)', backgroundColor: 'rgba(245, 158, 11, 0.05)' }}>
          <div className="kds-column-header" style={{ borderBottomColor: 'var(--color-orange)' }}>
            <div className="kds-column-title" style={{ color: 'var(--color-orange)' }}>
              <ChefHat size={20} /> Preparando
            </div>
            <div className="kds-column-count">2</div>
          </div>

          <Card className="kds-order-card" style={{ borderLeftColor: 'var(--color-orange)' }}>
            <div style={{ padding: 16 }}>
              <div className="kds-order-header">
                <div className="kds-order-number">#1041</div>
                <div className="kds-order-time" style={{ color: 'var(--color-orange)' }}>hace 8m</div>
              </div>
              <div className="kds-order-items">
                <div className="kds-order-item"><span>1x Corte Ahumado</span><Badge variant="warning">Término Medio</Badge></div>
                <div className="kds-order-item"><span>1x Sopa de Mariscos</span></div>
              </div>
              <div className="kds-order-footer">
                <Button size="sm" variant="primary" style={{ backgroundColor: 'var(--color-green)' }}>Listo <ArrowRight size={16} style={{ marginLeft: 4 }}/></Button>
              </div>
            </div>
          </Card>
        </div>

        {/* Ready Column */}
        <div className="kds-column" style={{ borderColor: 'var(--color-green-light)', backgroundColor: 'rgba(16, 185, 129, 0.05)' }}>
          <div className="kds-column-header" style={{ borderBottomColor: 'var(--color-green)' }}>
            <div className="kds-column-title" style={{ color: 'var(--color-green)' }}>
              <CheckCircle size={20} /> Listo para Servir
            </div>
            <div className="kds-column-count">1</div>
          </div>

          <Card className="kds-order-card" style={{ borderLeftColor: 'var(--color-green)' }}>
            <div style={{ padding: 16 }}>
              <div className="kds-order-header">
                <div className="kds-order-number">#1039</div>
                <div className="kds-order-time">hace 12m</div>
              </div>
              <div className="kds-order-items">
                <div className="kds-order-item"><span>3x Arroz Frito</span></div>
              </div>
              <div className="kds-order-footer">
                <Button size="sm" variant="secondary">Entregar Orden</Button>
              </div>
            </div>
          </Card>
        </div>

      </div>
    </div>
  );
};

export default KitchenBoard;
