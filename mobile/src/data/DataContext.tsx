import * as Crypto from 'expo-crypto';
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { api, ApiError, type LoginResponse } from '../api';
import { createLocalDb } from '../db/engine';
import { EMPTY, type LocalDb, type Snapshot } from '../db/localDb';
import { answerOffline } from '../features/concierge/offline';
import { useAuth } from '../session/AuthContext';
import type { ActionRequest, ChatMessage, SyncState } from '../types';

type Ctx = {
  snap: Snapshot;
  sync: SyncState;
  offline: boolean;
  setOffline: (v: boolean) => void;
  dbLocation: string | null;
  /** Queue an action (offline-first): a `requests` doc in the local DB, pushed by the replicator. */
  request: (tool: string, args: Record<string, unknown>, title: string) => Promise<ActionRequest>;
  ask: (message: string) => Promise<void>;
  thinking: boolean;
  liveChat: ChatMessage[];
  refresh: () => Promise<void>;
};

const DataContext = createContext<Ctx | null>(null);
const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');

export function DataProvider({ children }: { children: React.ReactNode }) {
  const { session } = useAuth();
  const dbRef = useRef<LocalDb | null>(null);
  const [snap, setSnap] = useState<Snapshot>(EMPTY);
  const [sync, setSync] = useState<SyncState>({ engine: 'preview', status: 'stopped', lastSyncAt: null, pendingPush: 0 });
  const [offline, setOfflineState] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [liveChat, setLiveChat] = useState<ChatMessage[]>([]);
  const [dbLocation, setDbLocation] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (dbRef.current) setSnap(await dbRef.current.read());
  }, []);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    const db = createLocalDb();
    dbRef.current = db;
    const offs: (() => void)[] = [];
    void (async () => {
      await db.open(session.guest_id);
      if (cancelled) return;
      setDbLocation(db.location());
      offs.push(db.onChange(() => void reload()));
      offs.push(db.onSyncState(setSync));
      await reload(); // whatever is already on the device renders immediately
      let sg = session.sync_gateway;
      try {
        // Fresh Sync Gateway session when there is connectivity; offline, the stored one is used.
        const r = await api<Pick<LoginResponse, 'token' | 'sync_gateway'>>('/api/auth/refresh', { token: session.token, method: 'POST', timeoutMs: 6000 });
        sg = r.sync_gateway ?? sg;
      } catch {
        /* offline at launch - fine */
      }
      if (cancelled) return;
      await db.startSync({ token: session.token, guestId: session.guest_id, sg });
    })();
    return () => {
      cancelled = true;
      offs.forEach((f) => f());
      void db.close();
      dbRef.current = null;
      setSnap(EMPTY);
      setLiveChat([]);
    };
  }, [session, reload]);

  const setOffline = useCallback((v: boolean) => {
    setOfflineState(v);
    void dbRef.current?.setPaused(v);
  }, []);

  const request = useCallback(
    async (tool: string, args: Record<string, unknown>, title: string) => {
      if (!session || !dbRef.current) throw new Error('Not signed in');
      const req: ActionRequest = {
        _id: `req::${session.guest_id}::${Crypto.randomUUID().replace(/-/g, '').slice(0, 16)}`,
        type: 'request',
        guest_id: session.guest_id,
        tool,
        args,
        title,
        status: 'pending',
        created_at: nowIso(),
      };
      await dbRef.current.saveRequest(req);
      await reload();
      return req;
    },
    [session, reload],
  );

  const ask = useCallback(
    async (message: string) => {
      if (!session) return;
      const guestMsg: ChatMessage = { id: `l${Date.now()}`, role: 'guest', text: message, at: nowIso() };
      setLiveChat((c) => [...c, guestMsg]);
      setThinking(true);
      try {
        if (offline) throw new ApiError('offline', 0);
        const r = await api<any>('/api/concierge', { token: session.token, body: { message, session_id: `app-${session.guest_id}` }, timeoutMs: 45000 });
        setLiveChat((c) => [
          ...c,
          { id: `r${Date.now()}`, role: 'concierge', text: r.reply, at: nowIso(), intent: r.intent, actions: r.actions,
            context: r.context, llm: r.llm, sources: r.sources },
        ]);
      } catch (e) {
        // No connectivity: answer from Couchbase Lite (context cache, FAQ, earlier answers).
        const local = answerOffline(message, snap);
        setLiveChat((c) => [...c, { id: `o${Date.now()}`, role: 'concierge', at: nowIso(), ...local }]);
        void e;
      } finally {
        setThinking(false);
      }
    },
    [session, offline, snap],
  );

  return (
    <DataContext.Provider value={{ snap, sync, offline, setOffline, dbLocation, request, ask, thinking, liveChat, refresh: reload }}>
      {children}
    </DataContext.Provider>
  );
}

export function useData(): Ctx {
  const c = useContext(DataContext);
  if (!c) throw new Error('useData outside DataProvider');
  return c;
}
