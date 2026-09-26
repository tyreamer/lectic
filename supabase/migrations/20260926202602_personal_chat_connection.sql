-- Dedicated Lectic project only. OAuth tokens are for /mcp, not the browser API.
BEGIN;

CREATE TABLE public.pilot_oauth_config (
  id text PRIMARY KEY CHECK (id = 'mcp'),
  resource text NOT NULL CHECK (resource ~ '^https://[^/?#]+/mcp$')
);
ALTER TABLE public.pilot_oauth_config ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pilot_oauth_config FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.pilot_oauth_config TO supabase_auth_admin;
CREATE POLICY auth_reads_mcp_resource ON public.pilot_oauth_config
  FOR SELECT TO supabase_auth_admin USING (true);

-- Enable this function as the project's Custom Access Token hook after the
-- operator configures the canonical resource with `cloud.admin configure-chat`.
-- No row means OAuth token issuance fails closed; ordinary sign-in still works.
CREATE FUNCTION public.lectic_access_token_hook(event jsonb)
RETURNS jsonb LANGUAGE plpgsql STABLE SET search_path = '' AS $$
DECLARE
  claims jsonb := event->'claims';
  client text := coalesce(nullif(event->>'client_id', ''), nullif(event->'claims'->>'client_id', ''));
  target text;
BEGIN
  IF client IS NOT NULL THEN
    SELECT resource INTO target FROM public.pilot_oauth_config WHERE id = 'mcp';
    IF target IS NULL THEN RAISE EXCEPTION 'Lectic chat resource is not configured'; END IF;
    claims := jsonb_set(claims, '{aud}', to_jsonb(target));
    claims := jsonb_set(claims, '{client_id}', to_jsonb(client));
  END IF;
  RETURN jsonb_set(event, '{claims}', claims);
END;
$$;
REVOKE EXECUTE ON FUNCTION public.lectic_access_token_hook(jsonb) FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA public TO supabase_auth_admin;
GRANT EXECUTE ON FUNCTION public.lectic_access_token_hook(jsonb) TO supabase_auth_admin;

-- OAuth clients must go through the API's active-session and invitation checks.
-- Restrictive policies also protect against any later browser SELECT grants.
DO $$
DECLARE item record;
BEGIN
  FOR item IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
    AND left(tablename, 6) = 'pilot_' AND tablename <> 'pilot_oauth_config'
  LOOP
    EXECUTE format('CREATE POLICY browser_sessions_only ON public.%I AS RESTRICTIVE FOR ALL TO authenticated USING ((SELECT auth.jwt()->>''client_id'') IS NULL) WITH CHECK ((SELECT auth.jwt()->>''client_id'') IS NULL)', item.tablename);
  END LOOP;
END;
$$;
ALTER POLICY lectic_owner_download ON storage.objects
  USING (bucket_id = 'lectic-private' AND (storage.foldername(name))[1] = (SELECT auth.uid())::text
         AND (SELECT auth.jwt()->>'client_id') IS NULL);

COMMIT;
