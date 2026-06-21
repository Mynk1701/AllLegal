'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { type EmailOtpType } from '@supabase/supabase-js'
import { createClient } from '@/utils/supabase/server'

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000'

// `next` rides along as a hidden form field from the confirm page, ultimately
// sourced from the email link's query string — attacker-controllable, so it
// must stay a relative, same-app path (else this becomes an open redirect).
function safeNext(value: FormDataEntryValue | null): string {
  if (typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')) {
    return value
  }
  return '/search'
}

export async function login(formData: FormData) {
  const supabase = await createClient()

  const data = {
    email: formData.get('email') as string,
    password: formData.get('password') as string,
  }

  const { error } = await supabase.auth.signInWithPassword(data)

  if (error) {
    return { error: error.message }
  }

  revalidatePath('/', 'layout')
  redirect('/search')
}

export async function signup(formData: FormData) {
  const supabase = await createClient()

  const data = {
    email: formData.get('email') as string,
    password: formData.get('password') as string,
  }

  const { error } = await supabase.auth.signUp({
    ...data,
    options: { emailRedirectTo: `${SITE_URL}/auth/confirm` },
  })

  if (error) {
    return { error: error.message }
  }

  revalidatePath('/', 'layout')
  return { success: 'Check your email to continue the sign up process.' }
}

// Called only when the human actually clicks "Confirm" on the intermediate
// page (see app/auth/confirm/page.tsx) — never on the bare GET to that page,
// so an email-scanner prefetch of the link can't burn the one-time token.
export async function confirmEmail(formData: FormData) {
  const token_hash = formData.get('token_hash') as string
  const type = formData.get('type') as EmailOtpType
  const next = safeNext(formData.get('next'))

  const supabase = await createClient()
  const { error } = await supabase.auth.verifyOtp({ type, token_hash })

  if (error) {
    redirect('/login?error=Link expired or invalid. Please try again.')
  }

  redirect(next)
}

export async function logout() {
  const supabase = await createClient()
  await supabase.auth.signOut()
  revalidatePath('/', 'layout')
  redirect('/login')
}

export async function requestPasswordReset(formData: FormData) {
  const supabase = await createClient()
  const email = formData.get('email') as string

  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${SITE_URL}/auth/confirm?next=/update-password`,
  })

  if (error) {
    return { error: error.message }
  }

  return { success: 'Check your email for a password reset link.' }
}

export async function updatePassword(formData: FormData) {
  const supabase = await createClient()
  const password = formData.get('password') as string

  const { error } = await supabase.auth.updateUser({ password })

  if (error) {
    return { error: error.message }
  }

  redirect('/search')
}
