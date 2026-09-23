import React from 'react';

export interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  badge?: {
    text: string;
    variant?: 'success' | 'warning' | 'danger' | 'info' | 'purple';
  };
  trend?: 'up' | 'down' | 'neutral';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtext,
  badge,
}) => {
  const getBadgeClass = (variant = 'success') => {
    switch (variant) {
      case 'success':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'warning':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'danger':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'purple':
        return 'bg-violet-50 text-violet-700 border-violet-200';
      case 'info':
      default:
        return 'bg-blue-50 text-blue-700 border-blue-200';
    }
  };

  return (
    <div className="bg-white border border-gray-100 rounded-lg p-3 shadow-xs flex flex-col justify-between">
      <div className="flex items-center justify-between gap-1 mb-1">
        <span className="text-xs font-medium text-gray-500 truncate">{label}</span>
        {badge && (
          <span
            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${getBadgeClass(
              badge.variant
            )}`}
          >
            {badge.text}
          </span>
        )}
      </div>
      <div className="text-lg font-bold text-gray-900 tracking-tight">{value}</div>
      {subtext && <div className="text-[11px] text-gray-400 mt-0.5">{subtext}</div>}
    </div>
  );
};

export interface SparklineMiniProps {
  data: number[];
  color?: string;
  width?: number;
  height?: number;
  strokeWidth?: number;
  fillOpacity?: number;
}

export const SparklineMini: React.FC<SparklineMiniProps> = ({
  data = [30, 32, 28, 35, 31, 29, 31.4],
  color = '#10b981', // Kiwi green default
  width = 160,
  height = 42,
  strokeWidth = 2,
  fillOpacity = 0.15,
}) => {
  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min === 0 ? 1 : max - min;
  const padding = 4;
  const usableHeight = height - padding * 2;
  const usableWidth = width - padding * 2;

  const points = data.map((val, index) => {
    const x = padding + (index / (data.length - 1)) * usableWidth;
    const y = padding + usableHeight - ((val - min) / range) * usableHeight;
    return `${x},${y}`;
  });

  const pathD = `M ${points.join(' L ')}`;
  const areaD = `M ${points[0]} L ${points.join(' L ')} L ${
    padding + usableWidth
  },${height} L ${padding},${height} Z`;

  return (
    <div className="relative inline-block overflow-hidden" style={{ width, height }}>
      <svg width={width} height={height} className="overflow-visible">
        <defs>
          <linearGradient id={`sparkline-gradient-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={fillOpacity} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <path
          d={areaD}
          fill={`url(#sparkline-gradient-${color.replace('#', '')})`}
        />
        <path
          d={pathD}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
};
