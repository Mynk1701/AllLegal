import * as React from 'react';
import { cn } from '@/lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, icon, type = 'text', ...props }, ref) => {
    return (
      <div className="relative flex items-center">
        {icon ? (
          <span className="pointer-events-none absolute left-3 flex items-center text-muted-foreground [&_svg]:size-4">
            {icon}
          </span>
        ) : null}
        <input
          ref={ref}
          type={type}
          className={cn(
            'h-10 w-full rounded-md border border-input bg-card text-body text-foreground shadow-hairline transition-colors',
            'placeholder:text-muted-foreground',
            'focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:outline-none',
            'disabled:cursor-not-allowed disabled:opacity-50',
            icon ? 'pl-9 pr-3' : 'px-3',
            className,
          )}
          {...props}
        />
      </div>
    );
  },
);
Input.displayName = 'Input';
