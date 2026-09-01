import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

export interface HubCardItem {
  title: string;
  description: string;
  icon: React.ReactNode;
  iconBg: string;
  iconColor: string;
  path: string;
  badge?: string;
}

interface CategoryHubViewProps {
  title: string;
  subtitle: string;
  badge?: string;
  cards: HubCardItem[];
}

export const CategoryHubView: React.FC<CategoryHubViewProps> = ({
  title,
  subtitle,
  badge,
  cards,
}) => {
  const navigate = useNavigate();

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', paddingBottom: '40px' }}>
      {/* Hub Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <h1 className="premium-header-title" style={{ margin: 0 }}>
            {title}
          </h1>
          {badge && (
            <span
              style={{
                background: '#ecfdf5',
                color: '#047857',
                border: '1px solid #a7f3d0',
                padding: '3px 10px',
                borderRadius: '9999px',
                fontSize: '0.75rem',
                fontWeight: 700,
              }}
            >
              {badge}
            </span>
          )}
        </div>
        <p className="premium-header-subtitle" style={{ margin: 0 }}>
          {subtitle}
        </p>
      </div>

      {/* Grid of Cards (POS Style) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '20px',
        }}
      >
        {cards.map((card) => (
          <div
            key={card.path}
            onClick={() => navigate(card.path)}
            style={{
              background: '#ffffff',
              borderRadius: '20px',
              border: '1px solid #e2e8f0',
              padding: '24px',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.03)',
              cursor: 'pointer',
              transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              position: 'relative',
              overflow: 'hidden',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-4px)';
              e.currentTarget.style.boxShadow = '0 14px 28px rgba(0, 0, 0, 0.08)';
              e.currentTarget.style.borderColor = '#10b981';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.03)';
              e.currentTarget.style.borderColor = '#e2e8f0';
            }}
          >
            <div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  marginBottom: '16px',
                }}
              >
                <div
                  style={{
                    width: '52px',
                    height: '52px',
                    borderRadius: '16px',
                    background: card.iconBg,
                    color: card.iconColor,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: '0 4px 10px rgba(0, 0, 0, 0.05)',
                  }}
                >
                  {card.icon}
                </div>
                {card.badge && (
                  <span
                    style={{
                      background: '#10b981',
                      color: '#ffffff',
                      padding: '3px 8px',
                      borderRadius: '6px',
                      fontSize: '0.7rem',
                      fontWeight: 800,
                    }}
                  >
                    {card.badge}
                  </span>
                )}
              </div>

              <h3
                style={{
                  fontSize: '1.15rem',
                  fontWeight: 700,
                  color: '#0f172a',
                  margin: '0 0 6px 0',
                }}
              >
                {card.title}
              </h3>
              <p
                style={{
                  fontSize: '0.875rem',
                  color: '#64748b',
                  margin: 0,
                  lineHeight: 1.45,
                }}
              >
                {card.description}
              </p>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                marginTop: '20px',
                fontSize: '0.85rem',
                fontWeight: 600,
                color: '#10b981',
              }}
            >
              <span>Acceder a {card.title}</span>
              <ArrowRight size={15} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
