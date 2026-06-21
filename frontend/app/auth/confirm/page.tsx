// Deliberately NOT a route handler that auto-verifies on GET: email security
// scanners prefetch links in the background, and an auto-verifying GET would
// let the scanner burn the one-time token before the real user ever clicks
// it (surfaces as "Email link is invalid or has expired"). Rendering an
// inert page with a real button — only submitted by an actual click — means
// the scanner's GET has no side effects.
import { Scale, AlertCircle } from 'lucide-react';
import { confirmEmail } from '../actions';

export default async function ConfirmPage({
  searchParams,
}: {
  searchParams: Promise<{ token_hash?: string; type?: string; next?: string }>;
}) {
  const { token_hash, type, next } = await searchParams;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center px-4">
      <div className="flex justify-center items-center gap-2 mb-6">
        <Scale className="w-10 h-10 text-blue-600" />
        <span className="text-3xl font-extrabold text-slate-900 tracking-tight">AllLegal</span>
      </div>

      <div className="bg-white py-8 px-6 shadow-xl shadow-slate-200/50 rounded-xl border border-slate-100 max-w-sm w-full text-center space-y-5">
        {token_hash && type ? (
          <>
            <h2 className="text-xl font-bold text-slate-900">Confirm it&apos;s you</h2>
            <p className="text-sm text-slate-500">
              Click below to finish verifying your email.
            </p>
            <form action={confirmEmail}>
              <input type="hidden" name="token_hash" value={token_hash} />
              <input type="hidden" name="type" value={type} />
              <input type="hidden" name="next" value={next ?? ''} />
              <button
                type="submit"
                className="w-full flex justify-center py-3 px-4 rounded-lg shadow-lg shadow-blue-500/20 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 transition-all"
              >
                Confirm
              </button>
            </form>
          </>
        ) : (
          <>
            <AlertCircle className="w-8 h-8 text-rose-500 mx-auto" />
            <h2 className="text-xl font-bold text-slate-900">Link invalid</h2>
            <p className="text-sm text-slate-500">
              This confirmation link is missing required information. Please request a new one.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
