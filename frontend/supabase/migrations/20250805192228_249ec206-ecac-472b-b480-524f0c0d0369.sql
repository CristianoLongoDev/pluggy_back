-- Fix jwt_custom_claims to return only custom claims, not a complete JWT
CREATE OR REPLACE FUNCTION public.jwt_custom_claims(event json)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  user_id uuid;
  user_account_id text;
  user_role text;
BEGIN
  -- Extract user id from the event
  user_id := (event->>'user_id')::uuid;
  
  -- Get account_id and role from profiles table
  SELECT account_id, role INTO user_account_id, user_role
  FROM public.profiles 
  WHERE id = user_id;
  
  -- Return only the custom claims (not a complete JWT)
  -- Supabase will merge these with the standard JWT claims
  RETURN json_build_object(
    'account_id', COALESCE(user_account_id, ''),
    'role', COALESCE(user_role, 'user')
  );
END;
$$;