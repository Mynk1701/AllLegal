// Shell for every authed screen (search / groups / history). Owns the
// full-height flex container + the persistent NavRail; each page renders into
// the remaining space. The reader (app/reader/*) deliberately sits OUTSIDE this
// group — it opens in its own tab and shouldn't carry the nav rail.
//
// Server component: reads the session once and hands the email to NavRail
// (a client component) for the avatar/tooltip. Route protection itself lives in
// middleware.ts, not here.

import NavRail from '@/components/app/NavRail';
import { createClient } from '@/utils/supabase/server';

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 font-sans overflow-hidden mesh-gradient">
      <NavRail email={user?.email ?? undefined} />
      {children}
    </div>
  );
}
