-- Remove all existing jwt_custom_claims functions
DROP FUNCTION IF EXISTS public.jwt_custom_claims(UUID);
DROP FUNCTION IF EXISTS public.jwt_custom_claims(json);

-- Create the correct function that accepts the event object from Supabase auth
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
  
  -- Return claims in the correct JSON format
  RETURN json_build_object(
    'claims', json_build_object(
      'account_id', COALESCE(user_account_id, ''),
      'role', COALESCE(user_role, 'user')
    )
  );
END;
$$;

-- Grant proper permissions
GRANT EXECUTE ON FUNCTION public.jwt_custom_claims(json) TO supabase_auth_admin;