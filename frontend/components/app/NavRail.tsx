'use client';

// The app's primary navigation, shared across every authed screen via
// app/(app)/layout.tsx. Search is a link; History and Groups expand IN PLACE
// into trees (recent searches / groups → cases) instead of navigating to a
// separate page — quick access without leaving the current screen. Labeled by
// default, collapsible to a slim icon rail (preference persisted).

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
  Scale, Search, FolderClosed, Clock, LogOut, Plus, ChevronLeft, ChevronRight, ChevronDown,
} from 'lucide-react';
import { clsx } from 'clsx';
import { logout } from '@/app/auth/actions';
import HistoryTree from './HistoryTree';
import GroupsTree from './GroupsTree';

const STORAGE_KEY = 'alllegal:nav-collapsed';
type Section = 'history' | 'groups' | null;

export default function NavRail({ email }: { email?: string }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [section, setSection] = useState<Section>(null);

  useEffect(() => {
    setCollapsed(localStorage.getItem(STORAGE_KEY) === '1');
  }, []);

  const setCollapsedPersisted = (next: boolean) => {
    setCollapsed(next);
    localStorage.setItem(STORAGE_KEY, next ? '1' : '0');
  };

  // Expanding a tree needs the rail open — if collapsed, open it first.
  const openSection = (s: Exclude<Section, null>) => {
    if (collapsed) {
      setCollapsedPersisted(false);
      setSection(s);
    } else {
      setSection((cur) => (cur === s ? null : s));
    }
  };

  const initial = (email?.[0] ?? 'U').toUpperCase();
  const searchActive = pathname === '/search' || pathname.startsWith('/search/');

  return (
    <aside
      className={clsx(
        'shrink-0 bg-[#0f172a] text-white flex flex-col py-5 z-30 transition-[width] duration-200',
        collapsed ? 'w-[76px] px-2' : 'w-60 px-3',
      )}
    >
      {/* Brand + collapse toggle */}
      <div className={clsx('flex items-center mb-6', collapsed ? 'justify-center' : 'justify-between px-1')}>
        <Link href="/search" aria-label="AllLegal home" className="flex items-center gap-2.5 min-w-0">
          <span className="p-2 bg-blue-600 rounded-xl shadow-lg shadow-blue-500/20 shrink-0">
            <Scale className="w-5 h-5 text-white" />
          </span>
          {!collapsed && <span className="font-extrabold text-lg tracking-tight truncate">AllLegal</span>}
        </Link>
        {!collapsed && (
          <button
            onClick={() => setCollapsedPersisted(true)}
            aria-label="Collapse sidebar"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        )}
      </div>

      {collapsed && (
        <button
          onClick={() => setCollapsedPersisted(false)}
          aria-label="Expand sidebar"
          className="mb-3 mx-auto p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      )}

      {/* New search CTA */}
      <Link
        href="/search"
        title="New search"
        className={clsx(
          'flex items-center gap-2 rounded-xl bg-white/10 hover:bg-white/15 font-bold text-sm transition-all active:scale-[0.98] mb-5',
          collapsed ? 'justify-center w-11 h-11 mx-auto' : 'px-3.5 py-2.5',
        )}
      >
        <Plus className="w-4 h-4 shrink-0" />
        {!collapsed && <span>New search</span>}
      </Link>

      {/* Nav + trees (scrolls if long) */}
      <div className="flex-1 min-h-0 overflow-y-auto -mx-1 px-1">
        <nav className={clsx('flex flex-col gap-1', collapsed && 'items-center')}>
          {/* SEARCH */}
          <Link
            href="/search"
            title={collapsed ? 'Search' : undefined}
            aria-current={searchActive ? 'page' : undefined}
            className={clsx(
              'flex items-center rounded-xl transition-all font-bold text-sm',
              collapsed ? 'flex-col gap-1 w-full py-2.5' : 'gap-3 px-3.5 py-2.5',
              searchActive
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                : 'text-slate-400 hover:text-white hover:bg-white/5',
            )}
          >
            <Search className="w-5 h-5 shrink-0" />
            <span className={collapsed ? 'text-[10px]' : ''}>Search</span>
          </Link>

          {/* HISTORY */}
          <SectionButton
            Icon={Clock}
            label="History"
            collapsed={collapsed}
            open={!collapsed && section === 'history'}
            onClick={() => openSection('history')}
          />
          {!collapsed && section === 'history' && (
            <div className="mb-1">
              <HistoryTree />
            </div>
          )}

          {/* GROUPS */}
          <SectionButton
            Icon={FolderClosed}
            label="Groups"
            collapsed={collapsed}
            open={!collapsed && section === 'groups'}
            onClick={() => openSection('groups')}
          />
          {!collapsed && section === 'groups' && (
            <div className="mb-1">
              <GroupsTree />
            </div>
          )}
        </nav>
      </div>

      {/* User + logout */}
      <div className={clsx('border-t border-white/10 pt-4 mt-2', collapsed && 'flex flex-col items-center gap-2')}>
        {collapsed ? (
          <>
            <div
              title={email}
              className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-sm font-bold shadow-lg shadow-blue-500/20"
            >
              {initial}
            </div>
            <button
              onClick={() => logout()}
              aria-label="Sign out"
              className="p-2 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </>
        ) : (
          <>
            <div className="flex items-center gap-2.5 px-1 mb-2 min-w-0">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-sm font-bold shadow-lg shadow-blue-500/20 shrink-0">
                {initial}
              </div>
              <p className="text-xs font-semibold text-slate-300 truncate">{email}</p>
            </div>
            <button
              onClick={() => logout()}
              className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-bold text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
            >
              <LogOut className="w-4 h-4 shrink-0" /> Sign out
            </button>
          </>
        )}
      </div>
    </aside>
  );
}

function SectionButton({
  Icon,
  label,
  collapsed,
  open,
  onClick,
}: {
  Icon: typeof Clock;
  label: string;
  collapsed: boolean;
  open: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={collapsed ? label : undefined}
      aria-expanded={open}
      className={clsx(
        'flex items-center rounded-xl transition-all font-bold text-sm',
        collapsed ? 'flex-col gap-1 w-full py-2.5' : 'gap-3 px-3.5 py-2.5',
        open ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white hover:bg-white/5',
      )}
    >
      <Icon className="w-5 h-5 shrink-0" />
      <span className={collapsed ? 'text-[10px]' : 'flex-1 text-left'}>{label}</span>
      {!collapsed && (
        <ChevronDown className={clsx('w-4 h-4 transition-transform', open && 'rotate-180')} />
      )}
    </button>
  );
}
