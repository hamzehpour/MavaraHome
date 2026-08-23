-- Mavara Home · production schema (PostgreSQL)
create extension if not exists pgcrypto;

create table users (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  phone text not null unique,
  telegram_id text unique,
  created_at timestamptz not null default now()
);
create table events (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  title_en text,
  description text,
  image text,
  price numeric(12,2) not null default 0,
  capacity integer not null default 20 check (capacity > 0),
  status text not null default 'active' check (status in ('active','inactive','deleted')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table sessions (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references events(id),
  date text not null,            -- jalali date, e.g. 1405-05-15
  gregorian_date date,
  time time not null,
  capacity integer not null default 20 check (capacity > 0),
  available_capacity integer not null,
  price numeric(12,2) not null default 0,
  status text not null default 'active' check (status in ('active','sold_out','cancelled','deleted')),
  unique (event_id, date, time), -- no duplicate sessions
  check (available_capacity <= capacity)
);
create table reservations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  session_id uuid not null references sessions(id),
  count integer not null check (count > 0),
  total_price numeric(12,2) not null check (total_price >= 0),
  status text not null default 'pending_payment' check (status in ('pending_payment','receipt_uploaded','waiting_admin_confirmation','approved','rejected','cancelled','waiting')),
  reservation_code varchar(10) unique not null check (reservation_code ~ '^MAV-[A-Z0-9]{6}$'),
  receipt_image text,
  admin_note text,
  created_at timestamptz not null default now()
);
create table audit_logs (
  id uuid primary key default gen_random_uuid(),
  actor text not null,
  action text not null,
  reservation_id uuid references reservations(id),
  at timestamptz not null default now()
);
create index idx_sessions_date on sessions(date);
create index idx_reservations_session on reservations(session_id, status);
-- Capacity rule: reserved seats = sum(count) over active statuses; never trust the client.
