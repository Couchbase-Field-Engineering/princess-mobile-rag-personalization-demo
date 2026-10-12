import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, type LoginResponse } from '../api';
import { readSession, writeSession } from './tokenStore';

type Ctx = {
  ready: boolean;
  session: LoginResponse | null;
  signIn: (bookingId: string, lastName: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<Ctx>({ ready: false, session: null, signIn: async () => {}, signOut: async () => {} });

/**
 * Sign-in = booking number + last name (like the real app's "find my cruise").
 * The backend answers with an app token and a Sync Gateway session for this
 * guest; the session is kept in the Keychain so a guest who opens the app at
 * sea, offline, lands straight on their Couchbase Lite data.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<LoginResponse | null>(null);

  useEffect(() => {
    void (async () => {
      const raw = await readSession();
      if (raw) {
        try {
          setSession(JSON.parse(raw));
        } catch {
          /* corrupt - sign in again */
        }
      }
      setReady(true);
    })();
  }, []);

  const signIn = useCallback(async (bookingId: string, lastName: string) => {
    const res = await api<LoginResponse>('/api/auth/login', { body: { booking_id: bookingId.trim(), last_name: lastName.trim() } });
    await writeSession(JSON.stringify(res));
    setSession(res);
  }, []);

  const signOut = useCallback(async () => {
    await writeSession(null);
    setSession(null);
  }, []);

  return <AuthContext.Provider value={{ ready, session, signIn, signOut }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
