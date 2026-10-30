import type { ActionRequest, Catalog, ChatDoc, ContextDoc, OffersDoc, Profile, SyncState } from '../types';

/**
 * The app's local database. Two implementations with the same contract:
 *
 * - `couchbase-lite` (cblDb.native.ts): the real thing. An on-device Couchbase
 *   Lite database (scope `pcl`, same collections as the server) kept in sync
 *   by a continuous push/pull replicator against Sync Gateway. Everything
 *   renders from here, so the app works with no connectivity at all.
 * - `preview` (previewDb.ts): a browser/Expo Go stand-in for demos without a
 *   device build - an in-memory store that polls the backend's REST
 *   `/api/sync/pull` and pushes requests with `/api/sync/push`. Same document
 *   ids and shapes.
 */
export const SCOPE = 'pcl';
export const COLLECTIONS = ['profiles', 'offers', 'bookings', 'requests', 'concierge', 'context_cache', 'catalog'] as const;
export type CollectionName = (typeof COLLECTIONS)[number];

export const CONTEXT_KEYS = [
  'upgrade', 'excursion', 'dining', 'package', 'spa', 'checkin', 'itinerary', 'service_recovery', 'general',
].flatMap((i) => [i, `playbook_${i}`]);

export type Snapshot = {
  profile: Profile | null;
  offers: OffersDoc | null;
  bookings: { items: import('../types').BookingItem[] } | null;
  requests: ActionRequest[];
  chat: ChatDoc | null;
  catalog: Catalog | null;
  contexts: Record<string, ContextDoc>;
};

export const EMPTY: Snapshot = { profile: null, offers: null, bookings: null, requests: [], chat: null, catalog: null, contexts: {} };

export type SyncSession = {
  token: string;
  guestId: string;
  sg: { session_id: string; cookie_name: string; url: string | null; db: string } | null;
};

export interface LocalDb {
  readonly engine: SyncState['engine'];
  open(guestId: string): Promise<void>;
  read(): Promise<Snapshot>;
  saveRequest(req: ActionRequest): Promise<void>;
  startSync(session: SyncSession): Promise<void>;
  setPaused(paused: boolean): Promise<void>;
  onChange(cb: () => void): () => void;
  onSyncState(cb: (s: SyncState) => void): () => void;
  location(): string | null;
  close(): Promise<void>;
}

export const ids = {
  profile: (g: string) => `profile::${g}`,
  offers: (g: string) => `offers::${g}`,
  bookings: (g: string) => `bookings::${g}`,
  chat: (g: string) => `chat::${g}`,
  ctx: (g: string, k: string) => `ctx::${g}::${k}`,
  catalog: 'catalog::v1',
};

/** Build a Snapshot from a by-id getter + the guest's requests. */
export async function buildSnapshot(
  guestId: string,
  get: (col: CollectionName, id: string) => Promise<Record<string, unknown> | null>,
  requests: ActionRequest[],
): Promise<Snapshot> {
  const contexts: Record<string, ContextDoc> = {};
  for (const k of CONTEXT_KEYS) {
    const d = await get('context_cache', ids.ctx(guestId, k));
    if (d) contexts[k] = d as unknown as ContextDoc;
  }
  return {
    profile: (await get('profiles', ids.profile(guestId))) as unknown as Profile | null,
    offers: (await get('offers', ids.offers(guestId))) as unknown as OffersDoc | null,
    bookings: (await get('bookings', ids.bookings(guestId))) as unknown as Snapshot['bookings'],
    chat: (await get('concierge', ids.chat(guestId))) as unknown as ChatDoc | null,
    catalog: (await get('catalog', ids.catalog)) as unknown as Catalog | null,
    contexts,
    requests: [...requests].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)),
  };
}

type Listener<T> = (v: T) => void;
export class Emitter<T> {
  private ls = new Set<Listener<T>>();
  on(l: Listener<T>) {
    this.ls.add(l);
    return () => {
      this.ls.delete(l);
    };
  }
  emit(v: T) {
    this.ls.forEach((l) => {
      try {
        l(v);
      } catch {
        /* listener errors never break sync */
      }
    });
  }
}
