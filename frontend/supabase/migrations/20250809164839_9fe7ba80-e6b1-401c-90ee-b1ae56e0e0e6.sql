-- Fix security warning: Function Search Path Mutable
-- Update all functions to have secure search_path

-- Fix validate_profile_role function
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
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = 'public';