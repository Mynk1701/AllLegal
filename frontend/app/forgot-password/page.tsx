'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Scale, Mail, AlertCircle, Loader2 } from 'lucide-react';
import { requestPasswordReset } from '../auth/actions';

export default function ForgotPasswordPage() {
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(formData: FormData) {
    setIsLoading(true);
    setError('');
    setMessage('');

    const result = await requestPasswordReset(formData);

    if (result?.error) {
      setError(result.error);
    } else if (result?.success) {
      setMessage(result.success);
    }
    setIsLoading(false);
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center items-center gap-2 mb-6">
          <Scale className="w-10 h-10 text-blue-600" />
          <span className="text-3xl font-extrabold text-slate-900 tracking-tight">AllLegal</span>
        </div>
        <h2 className="text-center text-2xl font-bold text-slate-900">Reset your password</h2>
        <p className="mt-2 text-center text-sm text-slate-500">
          Enter your email and we&apos;ll send you a link to reset it.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow-xl shadow-slate-200/50 sm:rounded-xl sm:px-10 border border-slate-100">
          <form action={handleSubmit} className="space-y-6">
            {error && (
              <div className="bg-rose-50 border border-rose-100 text-rose-700 px-4 py-3 rounded-lg flex items-center gap-3 text-sm">
                <AlertCircle className="w-5 h-5 shrink-0" />
                <p>{error}</p>
              </div>
            )}
            {message && (
              <div className="bg-green-50 border border-green-100 text-green-700 px-4 py-3 rounded-lg flex items-center gap-3 text-sm">
                <AlertCircle className="w-5 h-5 shrink-0" />
                <p>{message}</p>
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-700">
                Email address
              </label>
              <div className="mt-1 relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="h-4 w-4 text-slate-400" />
                </div>
                <input
                  name="email"
                  type="email"
                  required
                  className="appearance-none block w-full pl-10 pr-3 py-2.5 border border-slate-200 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 sm:text-sm bg-slate-50/50"
                  placeholder="name@firm.com"
                />
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-lg shadow-blue-500/20 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all"
              >
                {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Send reset link'}
              </button>
            </div>
          </form>

          <div className="mt-6">
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-white text-slate-500">Remembered it?</span>
            </div>
            <div className="mt-6">
              <button
                onClick={() => router.push('/login')}
                className="w-full flex justify-center py-3 px-4 border border-slate-200 rounded-lg text-sm font-semibold text-slate-700 bg-white hover:bg-slate-50 transition-all"
              >
                Back to sign in
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
