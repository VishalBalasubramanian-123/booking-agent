-- ============================================================
-- booking-agent database schema
-- Reflects the current live Supabase schema (public schema).
-- Compiled from the project's design history for reference —
-- keep this in sync with Supabase if the live schema changes.
-- ============================================================

-- ---------- Custom types ----------

CREATE TYPE by_who AS ENUM ('user', 'assistant');
CREATE TYPE confirmed_declined AS ENUM ('confirmed', 'declined', 'pending', 'cancelled');
CREATE TYPE bucket AS ENUM ('auto', 'verification', 'decision');

-- ---------- Customer & session ----------

CREATE TABLE customer (
  customer_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  phone VARCHAR(20) NOT NULL,
  email VARCHAR(100),
  is_delete_marker BOOLEAN DEFAULT false,
  created_at_timestamp TIMESTAMP DEFAULT now()
);

CREATE TABLE session (
  session_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  customer_id INT REFERENCES customer(customer_id),
  created_at_timestamp TIMESTAMP DEFAULT now()
);

CREATE TABLE conversation (
  conversation_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  session_id INT NOT NULL REFERENCES session(session_id),
  message TEXT NOT NULL,
  by_who by_who NOT NULL,
  created_at_timestamp TIMESTAMP DEFAULT now()
);

-- ---------- Reservations ----------

CREATE TABLE reservation (
  reservation_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  session_id INT NOT NULL REFERENCES session(session_id),
  availability BOOLEAN DEFAULT false,
  confirmed_declined confirmed_declined NOT NULL DEFAULT 'pending',
  reason TEXT,
  party_size INT NOT NULL,
  date DATE NOT NULL,
  time TIME NOT NULL,
  allergy_info TEXT,
  start_time_hold_reserve TIMESTAMP,
  end_time_hold_reserve TIMESTAMP,
  created_at_timestamp TIMESTAMP DEFAULT now(),
  occupancy_end_time TIMESTAMP NOT NULL
);

-- ---------- Restaurant reference data + knowledge base ----------

CREATE TABLE restaurant_info (
  restaurant_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  restaurant_name VARCHAR(150) NOT NULL,
  address VARCHAR(200),
  city VARCHAR(100),
  country VARCHAR(100),
  pincode VARCHAR(20),
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE restaurant_kb (
  restaurant_kb_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  restaurant_id INT NOT NULL REFERENCES restaurant_info(restaurant_id),
  content TEXT NOT NULL,
  embedding VECTOR(1536)  -- Amazon Titan Embeddings G1 - Text (amazon.titan-embed-text-v1)
);

-- ---------- Tables & availability ----------

CREATE TABLE tables_info (
  table_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  restaurant_id INT NOT NULL REFERENCES restaurant_info(restaurant_id),
  table_number INT NOT NULL,
  capacity INT NOT NULL,
  table_type VARCHAR(20)
);

CREATE TABLE reservation_tables_booking (
  reservation_table_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  reservation_id INT NOT NULL REFERENCES reservation(reservation_id),
  table_id INT NOT NULL REFERENCES tables_info(table_id),
  UNIQUE (reservation_id, table_id)
);

CREATE TABLE table_unavailability (
  unavailability_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  table_id INT NOT NULL REFERENCES tables_info(table_id),
  start_time TIMESTAMP NOT NULL,
  end_time TIMESTAMP NOT NULL,
  reason TEXT
);

-- ---------- Escalation (audit trail for bucket 2 / bucket 3 events) ----------

CREATE TABLE escalation (
  escalation_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  reservation_id INT NOT NULL REFERENCES reservation(reservation_id),
  session_id INT NOT NULL REFERENCES session(session_id),
  bucket bucket NOT NULL,
  owners_answer TEXT,
  responded_at TIMESTAMP,
  created_at_timestamp TIMESTAMP DEFAULT now()
);
