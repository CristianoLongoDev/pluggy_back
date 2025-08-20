-- Phase 1: Critical Database Security Fixes (Fixed)

-- 1. Enable RLS on jwt_hook_log table (CRITICAL)
ALTER TABLE public.jwt_hook_log ENABLE ROW LEVEL SECURITY;

-- Create policy to only allow admins to view jwt_hook_log
CREATE POLICY "Only admins can view jwt hook logs" 
ON public.jwt_hook_log 
FOR SELECT 
USING (get_current_user_role() = 'admin');

-- Create policy to only allow system to insert jwt_hook_log entries
CREATE POLICY "System can insert jwt hook logs" 
ON public.jwt_hook_log 
FOR INSERT 
WITH CHECK (true);

-- 2. Fix privilege escalation vulnerability (CRITICAL)
-- Drop existing policy that allows users to update their own profile
DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;

-- Create new policy that prevents users from updating their role
CREATE POLICY "Users can update their own profile except role" 
ON public.profiles 
FOR UPDATE 
USING (auth.uid() = id)
WITH CHECK (
  auth.uid() = id AND 
  (COALESCE((SELECT role FROM public.profiles WHERE id = auth.uid()), '') = COALESCE(role, ''))
);

-- Create separate policy for admins to update any profile including roles
CREATE POLICY "Admins can update any profile including roles" 
ON public.profiles 
FOR UPDATE 
USING (get_current_user_role() = 'admin');

-- 3. Add validation function for role field
CREATE OR REPLACE FUNCTION public.validate_profile_role()
RETURNS TRIGGER AS $$
DECLARE
  current_user_role TEXT;
BEGIN
  -- Validate role is one of the allowed values
  IF NEW.role NOT IN ('admin', 'agent', 'manager') THEN
    RAISE EXCEPTION 'Invalid role: %. Allowed values: admin, agent, manager', NEW.role;
  END IF;
  
  -- Get current user's role
  SELECT role INTO current_user_role FROM public.profiles WHERE id = auth.uid();
  
  -- Prevent role escalation (non-admins cannot set admin role)
  IF NEW.role = 'admin' AND (OLD.role IS NULL OR OLD.role != 'admin') THEN
    IF current_user_role != 'admin' THEN
      RAISE EXCEPTION 'Only admins can assign admin role';
    END IF;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger for role validation
DROP TRIGGER IF EXISTS validate_profile_role_trigger ON public.profiles;
CREATE TRIGGER validate_profile_role_trigger
  BEFORE UPDATE OF role ON public.profiles
  FOR EACH ROW
  EXECUTE FUNCTION public.validate_profile_role();