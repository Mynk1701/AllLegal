import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

const chipVariants = cva(
  'inline-flex items-center gap-1.5 rounded-md border text-meta font-medium transition-colors [&_svg]:size-3.5 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        solid: 'border-transparent bg-muted text-foreground',
        outline: 'border-border bg-card text-muted-foreground',
        accent: 'border-transparent bg-accent text-accent-foreground',
      },
      size: {
        sm: 'h-6 px-2',
        md: 'h-7 px-2.5',
      },
    },
    defaultVariants: { variant: 'outline', size: 'md' },
  },
);

export interface ChipProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof chipVariants> {
  onRemove?: () => void;
}

export function Chip({
  className,
  variant,
  size,
  children,
  onRemove,
  ...props
}: ChipProps) {
  return (
    <span className={cn(chipVariants({ variant, size }), className)} {...props}>
      {children}
      {onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove"
          className="-mr-0.5 ml-0.5 grid place-items-center rounded-sm text-current/70 transition-colors hover:text-current focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X />
        </button>
      ) : null}
    </span>
  );
}
