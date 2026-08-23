-- Maavara Home · Backend-ready reservation schema
-- PostgreSQL target. Frontend localStorage remains demo fallback only.
create extension if not exists pgcrypto;

create type user_role as enum ('super_admin','content_manager','event_manager','support');
create type event_status as enum ('draft','active','archived','deleted');
create type session_status as enum ('scheduled','sold_out','cancelled','completed');
create type reservation_status as enum ('pending_payment','pending_review','approved','awaiting_buyer_confirmation','rejected','waiting','expired','cancelled','used');
create type payment_status as enum ('pending','submitted','verified','rejected','refunded');

create table users (
  id uuid primary key default gen_random_uuid(), first_name text not null, last_name text not null,
  phone text not null, telegram_id text unique, email text, role user_role not null default 'support',
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table events (
  id uuid primary key default gen_random_uuid(), title jsonb not null, slug text unique not null,
  description jsonb, poster text, gallery jsonb not null default '[]', status event_status not null default 'draft',
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(), deleted_at timestamptz
);
create table event_dates (
  id uuid primary key default gen_random_uuid(), event_id uuid not null references events(id),
  jalali_date date not null, gregorian_date date not null, active boolean not null default true,
  unique(event_id, jalali_date)
);
create table sessions (
  id uuid primary key default gen_random_uuid(), event_date_id uuid not null references event_dates(id),
  start_time time not null, end_time time, capacity integer not null check (capacity > 0),
  reserved_count integer not null default 0 check (reserved_count >= 0), waiting_count integer not null default 0 check (waiting_count >= 0),
  price numeric(12,2) not null default 0 check (price >= 0), status session_status not null default 'scheduled'
);
create table reservations (
  id uuid primary key default gen_random_uuid(), reservation_code varchar(10) unique not null,
  user_id uuid not null references users(id), session_id uuid not null references sessions(id),
  ticket_count integer not null check (ticket_count > 0), total_price numeric(12,2) not null check (total_price >= 0),
  status reservation_status not null default 'pending_payment', created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  constraint reservation_code_format check (reservation_code ~ '^MAV-[A-Z0-9]{6}$')
);
create table payments (
  id uuid primary key default gen_random_uuid(), reservation_id uuid not null references reservations(id),
  receipt_image text, amount numeric(12,2) not null check (amount >= 0), payment_method text not null default 'card_transfer',
  status payment_status not null default 'pending', verified_at timestamptz, created_at timestamptz not null default now()
);
create table audit_logs (
  id uuid primary key default gen_random_uuid(), actor_user_id uuid references users(id), action text not null,
  entity_type text not null, entity_id uuid, before_data jsonb, after_data jsonb, created_at timestamptz not null default now()
);

-- Atomic capacity rule: reserve inside a transaction with SELECT ... FOR UPDATE on sessions.
-- If capacity - reserved_count < requested tickets, insert a waiting-list reservation instead;
-- never trust client capacity, price, status, or total_price.
create index idx_event_dates_event on event_dates(event_id, jalali_date);
create index idx_sessions_date on sessions(event_date_id, start_time);
create index idx_reservations_session on reservations(session_id, status);
create index idx_audit_entity on audit_logs(entity_type, entity_id, created_at desc);
