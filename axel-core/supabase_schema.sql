-- Pegar en Supabase → SQL Editor cuando pases de SQLite a Postgres.
-- Free tier de Supabase alcanza para el piloto.

create table if not exists customers (
  customer_id text primary key,
  business_id text not null default 'biz_default',
  name text,
  phone text,
  email text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists identities (
  identity_id bigserial primary key,
  customer_id text not null references customers(customer_id),
  channel text not null,
  channel_user_id text not null,
  unique (channel, channel_user_id)
);

create table if not exists conversation_summaries (
  summary_id bigserial primary key,
  customer_id text,
  event_id text,
  channel text,
  intent text,
  summary text,
  result text,
  created_at timestamptz default now()
);

create table if not exists messages (
  message_id bigserial primary key,
  customer_id text,
  event_id text,
  channel text,
  direction text,
  text text,
  created_at timestamptz default now()
);

create table if not exists session_state (
  customer_id text primary key,
  open_task text,
  updated_at timestamptz default now()
);

create table if not exists audit_events (
  event_id text primary key,
  received_at timestamptz,
  finished_at timestamptz,
  channel text,
  customer_id text,
  agent text,
  model text,
  supervision_level int,
  approval_status text,
  input_summary text,
  output_summary text,
  result text,
  error text
);

create index if not exists idx_customers_phone on customers(business_id, phone);
create index if not exists idx_customers_email on customers(business_id, email);
create index if not exists idx_summaries_customer on conversation_summaries(customer_id);
