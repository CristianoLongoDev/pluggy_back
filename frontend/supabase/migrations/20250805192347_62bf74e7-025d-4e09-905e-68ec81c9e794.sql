-- Fix the jwt_custom_claims function to return the correct format
CREATE OR REPLACE FUNCTION public.jwt_custom_claims(event jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'public'
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
  
  -- Return claims in the correct JSONB format
  RETURN jsonb_build_object(
    'claims', jsonb_build_object(
      'account_id', COALESCE(user_account_id, ''),
      'role', COALESCE(user_role, 'user')
    )
  );
END;
$$;

-- Grant proper permissions
GRANT EXECUTE ON FUNCTION public.jwt_custom_claims(jsonb) TO supabase_auth_admin;