-- Fix the jwt_custom_claims function to return claims in the correct format
CREATE OR REPLACE FUNCTION public.jwt_custom_claims(user_id UUID)
RETURNS JSONB 
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  user_account_id UUID;
  user_role TEXT;
BEGIN
  -- Get account_id and role from profiles table
  SELECT account_id, role INTO user_account_id, user_role
  FROM public.profiles 
  WHERE id = user_id;
  
  -- Return the claims in the correct format with "claims" field
  RETURN jsonb_build_object(
    'claims', jsonb_build_object(
      'account_id', COALESCE(user_account_id::text, ''),
      'role', COALESCE(user_role, 'user')
    )
  );
END;
$$;