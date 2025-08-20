-- Drop the overly permissive policy that allows all authenticated users to view all profiles
DROP POLICY IF EXISTS "Profiles are viewable by authenticated users" ON public.profiles;

-- Create a more restrictive policy that only allows users to see their own profile
-- and admins to see all profiles
CREATE POLICY "Users can view own profile, admins can view all" 
ON public.profiles 
FOR SELECT 
USING (
  -- User can see their own profile
  auth.uid() = id 
  OR 
  -- Admins can see all profiles
  get_current_user_role() = 'admin'
);