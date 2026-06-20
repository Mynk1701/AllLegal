import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Link2,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Citation Treatment Badge
 * Communicates how a cited authority has been treated by later courts.
 * The four treatments map to the system's semantic color tokens.
 */
export type Treatment = 'followed' | 'cautionary' | 'overruled' | 'neutral';

const config: Record<
  Treatment,
  { label: string; icon: LucideIcon; dot: string }
> = {
  followed: { label: 'Followed', icon: CheckCircle2, dot: 'bg-followed' },
  cautionary: {
    label: 'Distinguished',
    icon: AlertTriangle,
    dot: 'bg-cautionary',
  },
  overruled: { label: 'Overruled', icon: XCircle, dot: 'bg-overruled' },
  neutral: { label: 'Cited', icon: Link2, dot: 'bg-neutralcite' },
};

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-md border font-medium [&_svg]:size-3.5 [&_svg]:shrink-0',
  {
    variants: {
      treatment: {
        followed:
          'bg-followed-surface text-followed-foreground border-followed-border',
        cautionary:
          'bg-cautionary-surface text-cautionary-foreground border-cautionary-border',
        overruled:
          'bg-overruled-surface text-overruled-foreground border-overruled-border',
        neutral:
          'bg-neutralcite-surface text-neutralcite-foreground border-neutralcite-border',
      },
      size: {
        sm: 'h-6 px-2 text-caption tracking-wide uppercase',
        md: 'h-7 px-2.5 text-meta',
      },
    },
    defaultVariants: { treatment: 'neutral', size: 'md' },
  },
);

export interface CitationTreatmentBadgeProps
  extends Omit<React.HTMLAttributes<HTMLSpanElement>, 'children'>,
    VariantProps<typeof badgeVariants> {
  treatment: Treatment;
  /** Override the default treatment label, e.g. "Overruled in part". */
  label?: string;
  /** Use a status dot instead of the icon glyph. */
  variant?: 'icon' | 'dot';
  /** Show a count, e.g. number of citing authorities. */
  count?: number;
}

export function CitationTreatmentBadge({
  className,
  treatment,
  size,
  label,
  variant = 'icon',
  count,
  ...props
}: CitationTreatmentBadgeProps) {
  const { label: defaultLabel, icon: Icon, dot } = config[treatment];
  return (
    <span
      className={cn(badgeVariants({ treatment, size }), className)}
      role="status"
      {...props}
    >
      {variant === 'dot' ? (
        <span className={cn('size-2 rounded-full', dot)} aria-hidden />
      ) : (
        <Icon aria-hidden />
      )}
      <span>{label ?? defaultLabel}</span>
      {typeof count === 'number' ? (
        <span className="nums tabular-nums font-semibold opacity-70">{count}</span>
      ) : null}
    </span>
  );
}
