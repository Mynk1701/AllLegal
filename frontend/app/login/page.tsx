'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Scale, Mail, Lock, AlertCircle, Loader2, Zap, ShieldCheck, Eye, EyeOff } from 'lucide-react';
import { login } from '../auth/actions';

export default function LoginPage() {
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const router = useRouter();

  async function handleSubmit(formData: FormData) {
    setIsLoading(true);
    setError('');
    
    const result = await login(formData);

    if (result?.error) {
      setError(result.error);
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2 overflow-hidden bg-white font-sans">
      {/* LEFT: BRAND & VISUALS */}
      <div className="hidden lg:flex flex-col relative bg-[#0F172A] p-12 text-white justify-between overflow-hidden">
        <div className="absolute top-0 right-0 -translate-y-1/2 translate-x-1/2 w-[600px] h-[600px] bg-blue-600/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-0 left-0 translate-y-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-purple-600/10 rounded-full blur-[120px]" />
        
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600 rounded-lg">
              <Scale className="w-8 h-8 text-white" />
            </div>
            <span className="text-2xl font-bold tracking-tight">AllLegal</span>
          </div>
        </div>

        <div className="relative z-10 max-w-lg">
          <h1 className="text-5xl font-extrabold leading-[1.1] mb-6 tracking-tight">
            Justice, accelerated by <span className="text-blue-400">Intelligence.</span>
          </h1>
          <p className="text-slate-400 text-lg leading-relaxed mb-8">
            The next-generation legal research platform for Indian advocates. Search smarter, draft faster, and never miss a precedent.
          </p>

          <div className="grid grid-cols-2 gap-6">
            <div className="flex items-start gap-3">
              <div className="p-1.5 bg-blue-600/20 rounded-md mt-1">
                <Zap className="w-4 h-4 text-blue-400" />
              </div>
              <div>
                <p className="font-bold text-sm">Semantic Search</p>
                <p className="text-xs text-slate-500">Meaning-based retrieval</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="p-1.5 bg-blue-600/20 rounded-md mt-1">
                <ShieldCheck className="w-4 h-4 text-blue-400" />
              </div>
              <div>
                <p className="font-bold text-sm">Verified Data</p>
                <p className="text-xs text-slate-500">Official SC/HC records</p>
              </div>
            </div>
          </div>
        </div>

        <div className="relative z-10">
          <p className="text-slate-500 text-sm">© 2026 AllLegal Intelligence Systems Pvt Ltd.</p>
        </div>
      </div>

      {/* RIGHT: FORM */}
      <div className="flex items-center justify-center p-8 bg-slate-50 lg:bg-white mesh-gradient">
        <div className="w-full max-w-md space-y-8 animate-in fade-in slide-in-from-right-4 duration-700">
          <div className="text-center lg:text-left">
            <div className="lg:hidden flex justify-center mb-6">
              <div className="p-2 bg-blue-600 rounded-lg">
                <Scale className="w-8 h-8 text-white" />
              </div>
            </div>
            <h2 className="text-3xl font-bold text-slate-900 tracking-tight">Welcome Back</h2>
            <p className="mt-2 text-slate-500 font-medium">Enter your credentials to access your dashboard.</p>
          </div>

          <div className="bg-white lg:bg-transparent p-8 lg:p-0 rounded-2xl shadow-xl shadow-slate-200/50 lg:shadow-none border border-slate-100 lg:border-none">
            <form action={handleSubmit} className="space-y-5">
              {error && (
                <div className="bg-rose-50 border border-rose-100 text-rose-700 px-4 py-3 rounded-xl flex items-center gap-3 text-sm animate-in zoom-in-95 duration-200">
                  <AlertCircle className="w-5 h-5 shrink-0" />
                  <p className="font-medium">{error}</p>
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-sm font-bold text-slate-700 ml-1">Work Email</label>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                    <Mail className="h-4 w-4 text-slate-400 group-focus-within:text-blue-500 transition-colors" />
                  </div>
                  <input
                    name="email"
                    type="email"
                    required
                    className="block w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 focus:bg-white transition-all outline-none"
                    placeholder="name@firm.com"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between items-center ml-1">
                  <label className="text-sm font-bold text-slate-700">Password</label>
                  <a href="#" className="text-xs font-bold text-blue-600 hover:text-blue-700">Forgot?</a>
                </div>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                    <Lock className="h-4 w-4 text-slate-400 group-focus-within:text-blue-500 transition-colors" />
                  </div>
                  <input
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    className="block w-full pl-10 pr-12 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 focus:bg-white transition-all outline-none"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 transition-colors"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center pt-1">
                <input
                  id="remember"
                  type="checkbox"
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-slate-300 rounded-md transition-all cursor-pointer"
                />
                <label htmlFor="remember" className="ml-2.5 block text-sm font-medium text-slate-600 cursor-pointer">
                  Keep me logged in
                </label>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex justify-center items-center py-3.5 px-4 border border-transparent rounded-xl shadow-xl shadow-blue-500/20 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-500/20 transition-all disabled:opacity-50 active:scale-[0.98]"
              >
                {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Sign in to AllLegal'}
              </button>
            </form>

            <div className="mt-8">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-100" />
                </div>
                <div className="relative flex justify-center text-sm font-medium">
                  <span className="px-4 bg-white lg:bg-white text-slate-400">Or continue with</span>
                </div>
              </div>

              <button
                onClick={() => router.push('/signup')}
                className="mt-6 w-full flex justify-center py-3.5 px-4 border-2 border-slate-100 rounded-xl text-sm font-bold text-slate-700 bg-white hover:bg-slate-50 hover:border-slate-200 focus:outline-none transition-all active:scale-[0.98]"
              >
                Create a professional account
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
