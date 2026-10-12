/** Document shapes replicated from Couchbase (scope `rccl`) into Couchbase Lite. */

export type Port = {
  day: number;
  date: string;
  port_code: string;
  port: string;
  arrive: string | null;
  depart: string | null;
  type: 'embark' | 'debark' | 'sea' | 'port';
};

export type Stateroom = {
  stateroom_number: string;
  deck: number;
  category_code: string;
  category_name: string;
  neighborhood: string;
  location: string;
};

export type Profile = {
  type: 'profile';
  guest_id: string;
  export_date: string;
  rev: number;
  first_name: string;
  last_name: string;
  email: string | null;
  age_band: string;
  home_city: string;
  loyalty: { program: string; tier: string; points: number; cruises_completed: number; member_since: string };
  reservation: {
    booking_id: string;
    sailing_id: string;
    ship_code: string;
    ship_name: string;
    itinerary_name: string;
    nights: number;
    embark_port: string;
    embark_date: string;
    debark_date: string;
    ports: Port[];
    party_size: number;
    party: { guest_id: string; name: string; age_band: string; relationship: string }[];
    stateroom: Stateroom;
    checkin_status: 'complete' | 'not_started';
    arrival_slot: string | null;
    dining_assignment: string;
  };
  preferences: {
    interests: string[];
    dietary: string[];
    celebration: string | null;
    travels_with_kids: boolean;
  };
  history: { avg_onboard_spend_usd: number; lifetime_value_usd: number; past_sailings: unknown[] };
  purchased_for_sailing: { packages: string[]; excursions: string[]; dining: string[]; spa: string[] };
  ml_scores: Record<string, number | string | null> & { model_version: string; segment: string; next_best_action: string };
};

export type UpgradeOption = {
  category_code: string;
  category_name: string;
  available: number;
  instant_price_ppn: number;
  instant_total_usd: number;
  royalup_min_bid_ppn: number;
  perks: string[];
  recommended: boolean;
  recommended_bid_ppn: number | null;
};

export type Offer = {
  offer_id: string;
  kind: 'upgrade' | 'excursion' | 'dining' | 'package' | 'spa' | 'checkin';
  palette: string;
  title: string;
  subtitle: string;
  reason: string;
  price_label: string;
  score: number;
  rank: number;
  cta: { label: string; screen?: string; tool?: string; args?: Record<string, unknown> };
  options?: UpgradeOption[];
  nights?: number;
  party_size?: number;
};

export type OffersDoc = {
  type: 'offers';
  offers: Offer[];
  model_version: string;
  segment: string;
  export_date: string;
  generated_at: string;
  /** Fully booked dining seatings: {restaurant_id: {date: [times]}}. */
  dining_full?: Record<string, Record<string, string[]>>;
};

export type BookingItem = {
  item_id: string;
  kind: string;
  title: string;
  status: string;
  date?: string;
  time?: string;
  charge_usd?: number;
  booked_at: string;
};

export type RequestStatus = 'pending' | 'processing' | 'awaiting_approval' | 'confirmed' | 'accepted' | 'submitted' | 'failed';

export type ActionRequest = {
  _id: string;
  type: 'request';
  guest_id: string;
  tool: string;
  args: Record<string, unknown>;
  title: string;
  status: RequestStatus;
  created_at: string;
  summary?: string;
  charge_usd?: number;
  governed?: boolean;
  trace_id?: string | null;
  approval_id?: string | null;
  completed_at?: string | null;
  _local?: boolean; // created on this device, not yet acknowledged by the server
};

export type ChatMessage = {
  id: string;
  role: 'guest' | 'concierge';
  text: string;
  at: string;
  intent?: string;
  actions?: SuggestedAction[];
  context?: { status: string; latency_ms: number; kb_mode?: string; build_ms?: number };
  llm?: { status: string; namespace?: string; similarity?: number | null; latency_ms?: number | null; stub?: boolean; composed_locally?: boolean };
  sources?: { title: string; snippet: string; kind: string }[];
  offline?: boolean;
  pending?: boolean;
};

export type SuggestedAction = { label: string; tool?: string; screen?: string; args?: Record<string, unknown> };

export type ChatDoc = { type: 'concierge'; messages: ChatMessage[]; answers: Record<string, { reply: string; intent: string; at: string }> };

export type ContextDoc = {
  type: 'context_cache';
  intent: string;
  personal: boolean;
  export_date: string;
  built_at: string;
  build_ms: number;
  kb_mode: string;
  kb_profile: { title: string; content: string }[];
  kb_playbook: { title: string; content: string; answer?: string }[];
  facts: { tool?: string; data?: any };
};

export type Catalog = {
  type: 'catalog';
  export_date: string;
  cabin_categories: { code: string; name: string; rank: number; base_ppn: number; perks: string[] }[];
  excursions: { id: string; port: string; name: string; price: number; duration_hrs: number; tags: string[] }[];
  dining: { id: string; name: string; cuisine: string; price_pp: number; ships: string[] | '*'; tags: string[] }[];
  dining_times: string[];
  packages: { code: string; name: string; price_per_day: number; per: string; blurb: string }[];
  spa: { id: string; name: string; price: number; minutes: number }[];
  arrival_slots: string[];
  ports: Record<string, string>;
  faq: { q: string; a: string; keywords: string[] }[];
};

export type SyncState = {
  engine: 'couchbase-lite' | 'preview';
  status: 'connecting' | 'connected' | 'idle' | 'busy' | 'offline' | 'paused' | 'error' | 'stopped';
  lastSyncAt: number | null;
  pendingPush: number;
  detail?: string;
  endpoint?: string;
};
