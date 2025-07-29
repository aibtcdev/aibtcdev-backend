

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE EXTENSION IF NOT EXISTS "pg_cron" WITH SCHEMA "pg_catalog";






CREATE EXTENSION IF NOT EXISTS "pg_net" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgsodium";






COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE SCHEMA IF NOT EXISTS "vecs";


ALTER SCHEMA "vecs" OWNER TO "postgres";


CREATE EXTENSION IF NOT EXISTS "hypopg" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "index_advisor" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "moddatetime" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgjwt" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "vector" WITH SCHEMA "extensions";






CREATE OR REPLACE FUNCTION "public"."create_wallet_for_new_agent"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$BEGIN
  INSERT INTO wallets (agent_id, profile_id)
  VALUES (
    NEW.id,
    NEW.profile_id
  );
  RETURN NEW;
END;$$;


ALTER FUNCTION "public"."create_wallet_for_new_agent"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."handle_new_user"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
  -- Insert a new profile
  INSERT INTO public.profiles (id, username, email)
  VALUES (NEW.id, NEW.raw_user_meta_data->>'user_name', NEW.email);

  -- Insert a new agent and capture the agent ID
  DECLARE
    agent_id uuid;
  BEGIN
    INSERT INTO public.agents (profile_id)  -- Assuming agents table has a profile_id foreign key
    VALUES (NEW.id)  -- Use NEW.id for the profile_id
    RETURNING id INTO agent_id;  -- Capture the new agent ID

    -- Insert a new wallet using the profile ID and agent ID
    INSERT INTO public.wallets (profile_id, agent_id)  -- Include agent_id in the insert
    VALUES (NEW.id, agent_id);  -- Use NEW.id for the profile_id and agent_id
  END;

  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."handle_new_user"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."sync_users"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$BEGIN
    -- Insert or update user in public.users based on auth.users changes
    INSERT INTO public.users (uuid, username, email, github_id, created_at)
    VALUES (NEW.id, NEW.user_name, NEW.email, NEW.github_id, NEW.created_at)
    ON CONFLICT (uuid) 
    DO UPDATE SET 
        username = EXCLUDED.username,
        email = EXCLUDED.email,
        github_id = EXCLUDED.github_id,
        created_at = EXCLUDED.created_at;
    
    RETURN NEW;
END;$$;


ALTER FUNCTION "public"."sync_users"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."agents" (
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "profile_id" "uuid",
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "is_archived" boolean DEFAULT false,
    "account_contract" "text",
    "approved_contracts" "text"[]
);


ALTER TABLE "public"."agents" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."chain_states" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone,
    "network" "text",
    "block_hash" "text",
    "block_height" "text",
    "bitcoin_block_height" "text"
);


ALTER TABLE "public"."chain_states" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."daos" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "name" "text" NOT NULL,
    "mission" "text",
    "description" "text",
    "is_deployed" boolean DEFAULT false,
    "is_broadcasted" boolean DEFAULT false
);


ALTER TABLE "public"."daos" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."extensions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "type" "text" NOT NULL,
    "contract_principal" "text",
    "tx_id" "text",
    "status" "text" DEFAULT 'DRAFT'::"text",
    "dao_id" "uuid",
    "subtype" "text"
);


ALTER TABLE "public"."extensions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."holders" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp without time zone DEFAULT "now"(),
    "dao_id" "uuid",
    "token_id" "uuid",
    "wallet_id" "uuid",
    "amount" "text",
    "address" "text",
    "agent_id" "uuid"
);


ALTER TABLE "public"."holders" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."keys" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "profile_id" "uuid",
    "is_enabled" boolean DEFAULT true
);


ALTER TABLE "public"."keys" OWNER TO "postgres";


COMMENT ON TABLE "public"."keys" IS 'api keys';



CREATE TABLE IF NOT EXISTS "public"."profiles" (
    "id" "uuid" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "email" "text",
    "has_completed_guide" boolean DEFAULT false NOT NULL,
    "username" "text",
    "testnet_address" "text",
    "mainnet_address" "text",
    "user_type" "text" DEFAULT 'FREE'::"text" NOT NULL,
    "profile_image" "text"
);


ALTER TABLE "public"."profiles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."prompts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "dao_id" "uuid",
    "agent_id" "uuid",
    "prompt_text" "text",
    "is_active" boolean DEFAULT true,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone,
    "profile_id" "uuid",
    "model" "text" DEFAULT ''::"text",
    "temperature" double precision
);


ALTER TABLE "public"."prompts" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."proposals" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "title" "text",
    "status" "text" DEFAULT 'DRAFT'::"text",
    "contract_principal" "text",
    "tx_id" "text",
    "dao_id" "uuid",
    "proposal_id" bigint,
    "action" "text",
    "caller" "text",
    "creator" "text",
    "liquid_tokens" "text",
    "content" "text",
    "concluded_by" "text",
    "executed" boolean,
    "met_quorum" boolean,
    "met_threshold" boolean,
    "passed" boolean,
    "votes_against" "text",
    "votes_for" "text",
    "bond" "text",
    "type" "text",
    "contract_caller" "text",
    "created_btc" bigint,
    "created_stx" bigint,
    "creator_user_id" bigint,
    "exec_end" bigint,
    "exec_start" bigint,
    "memo" "text",
    "tx_sender" "text",
    "vote_end" bigint,
    "vote_start" bigint,
    "voting_delay" bigint,
    "voting_period" bigint,
    "voting_quorum" bigint,
    "voting_reward" "text",
    "voting_threshold" bigint,
    "summary" "text",
    "tags" "text"[],
    "has_embedding" boolean DEFAULT false,
    "x_url" "text",
    "tweet_id" "uuid"
);


ALTER TABLE "public"."proposals" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."queue" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "type" "text",
    "message" "json",
    "is_processed" boolean DEFAULT false,
    "dao_id" "uuid",
    "wallet_id" "uuid",
    "result" "jsonb"
);


ALTER TABLE "public"."queue" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."telegram_users" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "telegram_user_id" "text",
    "username" "text",
    "first_name" "text",
    "last_name" "text",
    "registered" boolean DEFAULT false NOT NULL,
    "profile_id" "uuid",
    "is_registered" boolean DEFAULT false NOT NULL
);


ALTER TABLE "public"."telegram_users" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."tokens" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "contract_principal" "text",
    "tx_id" "text",
    "name" "text",
    "description" "text",
    "symbol" "text",
    "decimals" bigint,
    "max_supply" "text",
    "uri" "text",
    "image_url" "text",
    "x_url" "text",
    "telegram_url" "text",
    "website_url" "text",
    "dao_id" "uuid",
    "status" "text" DEFAULT 'DRAFT'::"text"
);


ALTER TABLE "public"."tokens" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."votes" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "wallet_id" "uuid",
    "dao_id" "uuid",
    "answer" boolean,
    "proposal_id" "uuid",
    "reasoning" "text",
    "tx_id" "text",
    "address" "text",
    "amount" "text",
    "confidence" double precision,
    "prompt" "text",
    "voted" boolean DEFAULT false,
    "profile_id" "uuid",
    "agent_id" "uuid" DEFAULT "gen_random_uuid"(),
    "cost" double precision,
    "model" "text",
    "evaluation_score" "jsonb",
    "flags" "text"[],
    "evaluation" "jsonb"
);


ALTER TABLE "public"."votes" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."wallets" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "agent_id" "uuid",
    "profile_id" "uuid",
    "mainnet_address" "text",
    "testnet_address" "text",
    "secret_id" "uuid",
    "stx_balance" "text",
    "balance_updated_at" timestamp with time zone
);


ALTER TABLE "public"."wallets" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."x_creds" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "consumer_key" "text",
    "consumer_secret" "text",
    "access_token" "text",
    "access_secret" "text",
    "client_id" "text",
    "client_secret" "text",
    "username" "text",
    "dao_id" "uuid",
    "bearer_token" "text"
);


ALTER TABLE "public"."x_creds" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."x_tweets" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "message" "text",
    "author_id" "uuid",
    "conversation_id" "text",
    "tweet_id" "text",
    "is_worthy" boolean,
    "tweet_type" "text",
    "confidence_score" double precision,
    "reason" "text",
    "images" "text"[],
    "author_name" "text",
    "author_username" "text",
    "created_at_twitter" "text",
    "public_metrics" "jsonb",
    "entities" "jsonb",
    "attachments" "jsonb",
    "tweet_images_analysis" "jsonb"
);


ALTER TABLE "public"."x_tweets" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."x_users" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "name" "text",
    "username" "text",
    "user_id" "text",
    "description" "text",
    "location" "text",
    "profile_image_url" "text",
    "profile_banner_url" "text",
    "protected" boolean DEFAULT false,
    "url" "text",
    "verified" boolean,
    "verified_type" "text",
    "subscription_type" "text",
    "bitcoin_face_score" double precision
);


ALTER TABLE "public"."x_users" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "vecs"."dao_collection" (
    "id" character varying NOT NULL,
    "vec" "extensions"."vector"(1536) NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL
);


ALTER TABLE "vecs"."dao_collection" OWNER TO "postgres";


COMMENT ON TABLE "vecs"."dao_collection" IS 'This is a duplicate of example_collection';



CREATE TABLE IF NOT EXISTS "vecs"."dao_proposals" (
    "id" character varying NOT NULL,
    "vec" "extensions"."vector"(1536) NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL
);


ALTER TABLE "vecs"."dao_proposals" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "vecs"."knowledge_collection" (
    "id" character varying NOT NULL,
    "vec" "extensions"."vector"(1536) NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL
);


ALTER TABLE "vecs"."knowledge_collection" OWNER TO "postgres";


COMMENT ON TABLE "vecs"."knowledge_collection" IS 'This is a duplicate of dao_collection';



CREATE TABLE IF NOT EXISTS "vecs"."proposals" (
    "id" character varying NOT NULL,
    "vec" "extensions"."vector"(1536) NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL
);


ALTER TABLE "vecs"."proposals" OWNER TO "postgres";


ALTER TABLE ONLY "public"."prompts"
    ADD CONSTRAINT "agent_prompts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."agents"
    ADD CONSTRAINT "agents_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."chain_states"
    ADD CONSTRAINT "chain_states_network_key" UNIQUE ("network");



ALTER TABLE ONLY "public"."chain_states"
    ADD CONSTRAINT "chain_states_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."daos"
    ADD CONSTRAINT "daos_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."extensions"
    ADD CONSTRAINT "extensions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."keys"
    ADD CONSTRAINT "keys_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."profiles"
    ADD CONSTRAINT "profiles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."proposals"
    ADD CONSTRAINT "proposals_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."queue"
    ADD CONSTRAINT "queue_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."telegram_users"
    ADD CONSTRAINT "telegram_users_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."tokens"
    ADD CONSTRAINT "tokens_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."x_tweets"
    ADD CONSTRAINT "twitter_tweets_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."x_users"
    ADD CONSTRAINT "twitter_users_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."votes"
    ADD CONSTRAINT "votes_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."holders"
    ADD CONSTRAINT "wallet_tokens_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."wallets"
    ADD CONSTRAINT "wallets_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."x_creds"
    ADD CONSTRAINT "x_creds_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "vecs"."dao_collection"
    ADD CONSTRAINT "dao_collection_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "vecs"."dao_proposals"
    ADD CONSTRAINT "dao_proposals_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "vecs"."knowledge_collection"
    ADD CONSTRAINT "knowledge_collection_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "vecs"."proposals"
    ADD CONSTRAINT "proposals_pkey" PRIMARY KEY ("id");



CREATE INDEX "agents_profile_id_index" ON "public"."agents" USING "btree" ("profile_id");



CREATE INDEX "extensions_dao_id_index" ON "public"."extensions" USING "btree" ("dao_id");



CREATE INDEX "idx_agent_prompts_agent_id" ON "public"."prompts" USING "btree" ("agent_id");



CREATE INDEX "idx_agent_prompts_dao_id" ON "public"."prompts" USING "btree" ("dao_id");



CREATE INDEX "idx_proposals_dao_id" ON "public"."proposals" USING "btree" ("dao_id");



CREATE INDEX "idx_tokens_dao_id" ON "public"."tokens" USING "btree" ("dao_id");



CREATE INDEX "idx_votes_dao_id" ON "public"."votes" USING "btree" ("dao_id");



CREATE INDEX "idx_wallet_tokens_wallet_id" ON "public"."holders" USING "btree" ("wallet_id");



CREATE INDEX "votes_proposal_id_index" ON "public"."votes" USING "btree" ("proposal_id");



CREATE INDEX "votes_wallet_id_index" ON "public"."votes" USING "btree" ("wallet_id");



CREATE INDEX "dao_collection_vec_idx" ON "vecs"."dao_collection" USING "hnsw" ("vec" "extensions"."vector_cosine_ops") WITH ("m"='16', "ef_construction"='64');



CREATE INDEX "ix_vector_cosine_ops_hnsw_m16_efc64_00d9f91" ON "vecs"."dao_proposals" USING "hnsw" ("vec" "extensions"."vector_cosine_ops") WITH ("m"='16', "ef_construction"='64');



CREATE INDEX "ix_vector_cosine_ops_hnsw_m16_efc64_5e0144f" ON "vecs"."knowledge_collection" USING "hnsw" ("vec" "extensions"."vector_cosine_ops") WITH ("m"='16', "ef_construction"='64');



CREATE INDEX "ix_vector_cosine_ops_hnsw_m16_efc64_6c41c52" ON "vecs"."dao_collection" USING "hnsw" ("vec" "extensions"."vector_cosine_ops") WITH ("m"='16', "ef_construction"='64');



CREATE INDEX "ix_vector_cosine_ops_hnsw_m16_efc64_fe63acf" ON "vecs"."proposals" USING "hnsw" ("vec" "extensions"."vector_cosine_ops") WITH ("m"='16', "ef_construction"='64');



CREATE INDEX "knowledge_collection_vec_idx" ON "vecs"."knowledge_collection" USING "hnsw" ("vec" "extensions"."vector_cosine_ops") WITH ("m"='16', "ef_construction"='64');



CREATE INDEX "knowledge_collection_vec_idx1" ON "vecs"."knowledge_collection" USING "hnsw" ("vec" "extensions"."vector_cosine_ops") WITH ("m"='16', "ef_construction"='64');



CREATE OR REPLACE TRIGGER "generate_wallet" AFTER INSERT ON "public"."wallets" FOR EACH ROW EXECUTE FUNCTION "supabase_functions"."http_request"('https://mkkhfmcrbwyuutcvtier.supabase.co/functions/v1/wallets', 'POST', '{"Content-type":"application/json","Authorization":"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1ra2hmbWNyYnd5dXV0Y3Z0aWVyIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNjg3NzQ2NywiZXhwIjoyMDUyNDUzNDY3fQ.bfzM3IAFuvwoxtjVociLIUSbuG09oojBUNCVUmxsAqE"}', '{}', '5000');



ALTER TABLE ONLY "public"."prompts"
    ADD CONSTRAINT "agent_prompts_agent_id_fkey" FOREIGN KEY ("agent_id") REFERENCES "public"."agents"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."prompts"
    ADD CONSTRAINT "agent_prompts_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "public"."profiles"("id");



ALTER TABLE ONLY "public"."agents"
    ADD CONSTRAINT "agents_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "public"."profiles"("id");



ALTER TABLE ONLY "public"."extensions"
    ADD CONSTRAINT "extensions_dao_id_fkey" FOREIGN KEY ("dao_id") REFERENCES "public"."daos"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."holders"
    ADD CONSTRAINT "holders_agent_id_fkey" FOREIGN KEY ("agent_id") REFERENCES "public"."agents"("id");



ALTER TABLE ONLY "public"."holders"
    ADD CONSTRAINT "holders_dao_id_fkey" FOREIGN KEY ("dao_id") REFERENCES "public"."daos"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."keys"
    ADD CONSTRAINT "keys_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "public"."profiles"("id");



ALTER TABLE ONLY "public"."prompts"
    ADD CONSTRAINT "prompts_dao_id_fkey" FOREIGN KEY ("dao_id") REFERENCES "public"."daos"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."proposals"
    ADD CONSTRAINT "proposals_dao_id_fkey" FOREIGN KEY ("dao_id") REFERENCES "public"."daos"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."proposals"
    ADD CONSTRAINT "proposals_tweet_id_fkey" FOREIGN KEY ("tweet_id") REFERENCES "public"."x_tweets"("id");



ALTER TABLE ONLY "public"."queue"
    ADD CONSTRAINT "queue_dao_id_fkey" FOREIGN KEY ("dao_id") REFERENCES "public"."daos"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."queue"
    ADD CONSTRAINT "queue_wallet_id_fkey" FOREIGN KEY ("wallet_id") REFERENCES "public"."wallets"("id");



ALTER TABLE ONLY "public"."telegram_users"
    ADD CONSTRAINT "telegram_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "public"."profiles"("id");



ALTER TABLE ONLY "public"."tokens"
    ADD CONSTRAINT "tokens_dao_id_fkey" FOREIGN KEY ("dao_id") REFERENCES "public"."daos"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."votes"
    ADD CONSTRAINT "votes_agent_id_fkey" FOREIGN KEY ("agent_id") REFERENCES "public"."agents"("id");



ALTER TABLE ONLY "public"."votes"
    ADD CONSTRAINT "votes_dao_id_fkey" FOREIGN KEY ("dao_id") REFERENCES "public"."daos"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."votes"
    ADD CONSTRAINT "votes_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "public"."profiles"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."votes"
    ADD CONSTRAINT "votes_proposal_id_fkey" FOREIGN KEY ("proposal_id") REFERENCES "public"."proposals"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."votes"
    ADD CONSTRAINT "votes_wallet_id_fkey" FOREIGN KEY ("wallet_id") REFERENCES "public"."wallets"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."holders"
    ADD CONSTRAINT "wallet_tokens_token_id_fkey" FOREIGN KEY ("token_id") REFERENCES "public"."tokens"("id");



ALTER TABLE ONLY "public"."holders"
    ADD CONSTRAINT "wallet_tokens_wallet_id_fkey" FOREIGN KEY ("wallet_id") REFERENCES "public"."wallets"("id");



ALTER TABLE ONLY "public"."wallets"
    ADD CONSTRAINT "wallets_agent_id_fkey" FOREIGN KEY ("agent_id") REFERENCES "public"."agents"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."wallets"
    ADD CONSTRAINT "wallets_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "public"."profiles"("id");



ALTER TABLE ONLY "public"."wallets"
    ADD CONSTRAINT "wallets_secret_id_fkey" FOREIGN KEY ("secret_id") REFERENCES "vault"."secrets"("id");



ALTER TABLE ONLY "public"."x_creds"
    ADD CONSTRAINT "x_creds_dao_id_fkey" FOREIGN KEY ("dao_id") REFERENCES "public"."daos"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."x_tweets"
    ADD CONSTRAINT "x_tweets_author_id_fkey" FOREIGN KEY ("author_id") REFERENCES "public"."x_users"("id") ON DELETE SET NULL;



CREATE POLICY "Allow all users to insert" ON "public"."prompts" FOR INSERT TO "authenticated" WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "profile_id"));



CREATE POLICY "Allow all users to update" ON "public"."prompts" FOR UPDATE TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "profile_id")) WITH CHECK (true);



CREATE POLICY "Allow delete on telegram_users for authenticated users" ON "public"."telegram_users" FOR DELETE TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "profile_id"));



CREATE POLICY "Allow insert on agents for authenticated users" ON "public"."agents" FOR INSERT TO "authenticated" WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "profile_id"));



CREATE POLICY "Allow insert on telegram_users for authenticated users" ON "public"."telegram_users" FOR INSERT TO "authenticated" WITH CHECK (true);



CREATE POLICY "Allow select on profiles for authenticated users" ON "public"."profiles" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "id"));



CREATE POLICY "Allow select on telegram_users for authenticated users" ON "public"."telegram_users" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "profile_id"));



CREATE POLICY "Allow update on agents for authenticated users" ON "public"."agents" FOR UPDATE TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "profile_id")) WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "profile_id"));



CREATE POLICY "Allow update on telegram_users for authenticated users" ON "public"."telegram_users" FOR UPDATE TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "profile_id")) WITH CHECK (true);



CREATE POLICY "Enable delete for users based on user_id" ON "public"."prompts" FOR DELETE TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "profile_id"));



CREATE POLICY "Enable read access for all users" ON "public"."chain_states" FOR SELECT USING (true);



CREATE POLICY "Enable read access for all users" ON "public"."daos" FOR SELECT USING (true);



CREATE POLICY "Enable read access for all users" ON "public"."extensions" FOR SELECT USING (true);



CREATE POLICY "Enable read access for all users" ON "public"."holders" FOR SELECT USING (true);



CREATE POLICY "Enable read access for all users" ON "public"."prompts" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "profile_id"));



CREATE POLICY "Enable read access for all users" ON "public"."proposals" FOR SELECT USING (true);



CREATE POLICY "Enable read access for all users" ON "public"."tokens" FOR SELECT USING (true);



CREATE POLICY "Enable read access for all users" ON "public"."votes" FOR SELECT USING (true);



CREATE POLICY "Enable read access for authenticated users" ON "public"."agents" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "profile_id"));



CREATE POLICY "Users can insert their own profile" ON "public"."profiles" FOR INSERT WITH CHECK (("auth"."uid"() = "id"));



CREATE POLICY "Viewing of your own" ON "public"."wallets" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "profile_id"));



ALTER TABLE "public"."agents" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "allow update for your own data" ON "public"."profiles" FOR UPDATE TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "id")) WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "id"));



ALTER TABLE "public"."chain_states" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."daos" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."extensions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."holders" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "insert based on profileid" ON "public"."wallets" FOR INSERT TO "authenticated" WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "profile_id"));



ALTER TABLE "public"."keys" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."profiles" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."prompts" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."proposals" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."queue" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."telegram_users" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."tokens" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."votes" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."wallets" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."x_creds" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."x_tweets" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."x_users" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "vecs"."dao_collection" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "vecs"."knowledge_collection" ENABLE ROW LEVEL SECURITY;




ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";






ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."chain_states";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."daos";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."proposals";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."tokens";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."votes";









GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";






































































































































































































































































































































































































































































































































































































GRANT ALL ON FUNCTION "public"."create_wallet_for_new_agent"() TO "anon";
GRANT ALL ON FUNCTION "public"."create_wallet_for_new_agent"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."create_wallet_for_new_agent"() TO "service_role";



GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "anon";
GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "service_role";



GRANT ALL ON FUNCTION "public"."sync_users"() TO "anon";
GRANT ALL ON FUNCTION "public"."sync_users"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."sync_users"() TO "service_role";










































GRANT ALL ON TABLE "public"."agents" TO "anon";
GRANT ALL ON TABLE "public"."agents" TO "authenticated";
GRANT ALL ON TABLE "public"."agents" TO "service_role";



GRANT ALL ON TABLE "public"."chain_states" TO "anon";
GRANT ALL ON TABLE "public"."chain_states" TO "authenticated";
GRANT ALL ON TABLE "public"."chain_states" TO "service_role";



GRANT ALL ON TABLE "public"."daos" TO "anon";
GRANT ALL ON TABLE "public"."daos" TO "authenticated";
GRANT ALL ON TABLE "public"."daos" TO "service_role";



GRANT ALL ON TABLE "public"."extensions" TO "anon";
GRANT ALL ON TABLE "public"."extensions" TO "authenticated";
GRANT ALL ON TABLE "public"."extensions" TO "service_role";



GRANT ALL ON TABLE "public"."holders" TO "anon";
GRANT ALL ON TABLE "public"."holders" TO "authenticated";
GRANT ALL ON TABLE "public"."holders" TO "service_role";



GRANT ALL ON TABLE "public"."keys" TO "anon";
GRANT ALL ON TABLE "public"."keys" TO "authenticated";
GRANT ALL ON TABLE "public"."keys" TO "service_role";



GRANT ALL ON TABLE "public"."profiles" TO "anon";
GRANT ALL ON TABLE "public"."profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."profiles" TO "service_role";



GRANT ALL ON TABLE "public"."prompts" TO "anon";
GRANT ALL ON TABLE "public"."prompts" TO "authenticated";
GRANT ALL ON TABLE "public"."prompts" TO "service_role";



GRANT ALL ON TABLE "public"."proposals" TO "anon";
GRANT ALL ON TABLE "public"."proposals" TO "authenticated";
GRANT ALL ON TABLE "public"."proposals" TO "service_role";



GRANT ALL ON TABLE "public"."queue" TO "anon";
GRANT ALL ON TABLE "public"."queue" TO "authenticated";
GRANT ALL ON TABLE "public"."queue" TO "service_role";



GRANT ALL ON TABLE "public"."telegram_users" TO "anon";
GRANT ALL ON TABLE "public"."telegram_users" TO "authenticated";
GRANT ALL ON TABLE "public"."telegram_users" TO "service_role";



GRANT ALL ON TABLE "public"."tokens" TO "anon";
GRANT ALL ON TABLE "public"."tokens" TO "authenticated";
GRANT ALL ON TABLE "public"."tokens" TO "service_role";



GRANT ALL ON TABLE "public"."votes" TO "anon";
GRANT ALL ON TABLE "public"."votes" TO "authenticated";
GRANT ALL ON TABLE "public"."votes" TO "service_role";



GRANT ALL ON TABLE "public"."wallets" TO "anon";
GRANT ALL ON TABLE "public"."wallets" TO "authenticated";
GRANT ALL ON TABLE "public"."wallets" TO "service_role";



GRANT ALL ON TABLE "public"."x_creds" TO "anon";
GRANT ALL ON TABLE "public"."x_creds" TO "authenticated";
GRANT ALL ON TABLE "public"."x_creds" TO "service_role";



GRANT ALL ON TABLE "public"."x_tweets" TO "anon";
GRANT ALL ON TABLE "public"."x_tweets" TO "authenticated";
GRANT ALL ON TABLE "public"."x_tweets" TO "service_role";



GRANT ALL ON TABLE "public"."x_users" TO "anon";
GRANT ALL ON TABLE "public"."x_users" TO "authenticated";
GRANT ALL ON TABLE "public"."x_users" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "service_role";






























RESET ALL;
