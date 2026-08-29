import React from 'react';
import './Select.css';

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  icon?: React.ReactNode;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className = '', icon, children, ...props }, ref) => {
    return (
      <div className={`ui-select-wrapper ${className}`}>
        {icon && <span className="ui-select-icon">{icon}</span>}
        <select
          ref={ref}
          className={`ui-select ${icon ? 'ui-select--with-icon' : ''}`}
          {...props}
        >
          {children}
        </select>
      </div>
    );
  }
);

Select.displayName = 'Select';
