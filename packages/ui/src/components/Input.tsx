import React from 'react';
import './Input.css';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className = '', icon, ...props }, ref) => {
    return (
      <div className={`ui-input-wrapper ${className}`}>
        {icon && <span className="ui-input-icon">{icon}</span>}
        <input ref={ref} className={`ui-input ${icon ? 'ui-input--with-icon' : ''}`} {...props} />
      </div>
    );
  }
);
Input.displayName = 'Input';
