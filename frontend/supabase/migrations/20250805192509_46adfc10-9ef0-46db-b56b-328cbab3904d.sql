-- Remove ALL versions of jwt_custom_claims
DROP FUNCTION IF EXISTS public.jwt_custom_claims(json);
DROP FUNCTION IF EXISTS public.jwt_custom_claims(jsonb);
DROP FUNCTION IF EXISTS public.jwt_custom_claims(uuid);
DROP FUNCTION IF EXISTS public.jwt_custom_claims(text);

-- Create the definitive version that matches Supabase's requirements
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
  
  -- Debug log to see what we're working with
  RAISE LOG 'JWT custom claims called for user: %', user_id;
  
  -- Get account_id and role from profiles table
  SELECT account_id, role INTO user_account_id, user_role
  FROM public.profiles 
  WHERE id = user_id;
  
  RAISE LOG 'Found account_id: % role: %', user_account_id, user_role;
  
  -- Return custom claims only (not wrapped in claims)
  RETURN jsonb_build_object(
    'account_id', COALESCE(user_account_id, ''),
    'role', COALESCE(user_role, 'user')
  );
END;
$$;

-- Grant execute permission to auth admin
GRANT EXECUTE ON FUNCTION public.jwt_custom_claims(jsonb) TO supabase_auth_admin;