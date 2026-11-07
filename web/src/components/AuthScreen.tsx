'use client';

import { useState } from 'react';

type AuthUser = { id: number | string; email: string; name?: string | null };

interface AuthScreenProps {
  onAuthenticated: (token: string, user: AuthUser) => void;
}

export default function AuthScreen({ onAuthenticated }: AuthScreenProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    const apiUrl = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
    if (!apiUrl) {
      setError('The backend URL is not configured. Set NEXT_PUBLIC_API_URL and rebuild the frontend.');
      return;
    }

    setBusy(true);
    try {
      const response = await fetch(`${apiUrl}/api/auth/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password, name: name.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Authentication failed.');
      if (!data.token || !data.user) {
        throw new Error('The server did not return a valid login token. Check JWT_SECRET on the backend.');
      }
      onAuthenticated(data.token, data.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to connect to the authentication service.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-[#050510] px-5 py-10 text-white">
      <section className="w-full max-w-md rounded-2xl border border-white/10 bg-white/[0.04] p-7 shadow-2xl">
        <div className="mb-7">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-neon-blue text-lg font-bold">A</div>
          <p className="text-xs uppercase tracking-[0.22em] text-accent2">Aleena AI</p>
          <h1 className="mt-2 text-2xl font-semibold">{mode === 'login' ? 'Welcome back' : 'Create your account'}</h1>
          <p className="mt-2 text-sm text-white/55">Sign in to securely access your assistant and private chat history.</p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          {mode === 'register' && (
            <label className="block text-sm text-white/75">
              Name
              <input value={name} onChange={(event) => setName(event.target.value)} required maxLength={120} autoComplete="name" className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-white outline-none focus:border-accent" />
            </label>
          )}
          <label className="block text-sm text-white/75">
            Email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-white outline-none focus:border-accent" />
          </label>
          <label className="block text-sm text-white/75">
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={mode === "register" ? 8 : undefined} maxLength={72} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-white outline-none focus:border-accent" />
          </label>

          {error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">{error}</p>}

          <button type="submit" disabled={busy} className="w-full rounded-lg bg-accent px-4 py-3 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60">
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-white/55">
          {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
          <button type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }} className="font-medium text-accent2 hover:underline">
            {mode === 'login' ? 'Create one' : 'Sign in'}
          </button>
        </p>
      </section>
    </main>
  );
}
