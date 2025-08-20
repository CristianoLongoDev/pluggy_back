import React, { useEffect } from 'react';
import { useToast } from '@/hooks/use-toast';
import { logSecurityEvent, generateSecureId } from '@/lib/security';

interface SecurityWrapperProps {
  children: React.ReactNode;
}

export const SecurityWrapper: React.FC<SecurityWrapperProps> = ({ children }) => {
  const { toast } = useToast();

  useEffect(() => {
    // Set up session ID for rate limiting if not exists
    if (!sessionStorage.getItem('session_id')) {
      sessionStorage.setItem('session_id', generateSecureId(16));
    }

    // Set up security event listeners
    const handleSecurityViolation = (event: SecurityPolicyViolationEvent) => {
      logSecurityEvent('CSP_VIOLATION', {
        blockedURI: event.blockedURI,
        violatedDirective: event.violatedDirective,
        originalPolicy: event.originalPolicy
      });
    };

    const handleError = (event: ErrorEvent) => {
      // Log security-relevant errors without sensitive data
      if (event.error && typeof event.error === 'object') {
        logSecurityEvent('RUNTIME_ERROR', {
          message: event.message,
          filename: event.filename,
          lineno: event.lineno
        });
      }
    };

    // Add event listeners
    document.addEventListener('securitypolicyviolation', handleSecurityViolation);
    window.addEventListener('error', handleError);

    // Security-related initialization
    const initSecurity = () => {
      // Disable right-click context menu in production
      if (process.env.NODE_ENV === 'production') {
        document.addEventListener('contextmenu', (e) => {
          e.preventDefault();
        });
      }

      // Disable common keyboard shortcuts that could be used for inspection
      document.addEventListener('keydown', (e) => {
        // Disable F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+U
        if (
          e.key === 'F12' ||
          (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'J')) ||
          (e.ctrlKey && e.key === 'u')
        ) {
          if (process.env.NODE_ENV === 'production') {
            e.preventDefault();
            logSecurityEvent('DEVTOOLS_ACCESS_ATTEMPT');
            toast({
              title: "Acesso Negado",
              description: "Ferramentas de desenvolvimento não são permitidas.",
              variant: "destructive"
            });
          }
        }
      });

      // Monitor for devtools detection
      let devtools = { open: false, orientation: null };
      const threshold = 160;

      setInterval(() => {
        if (window.outerHeight - window.innerHeight > threshold || 
            window.outerWidth - window.innerWidth > threshold) {
          if (!devtools.open) {
            devtools.open = true;
            logSecurityEvent('DEVTOOLS_OPENED');
            if (process.env.NODE_ENV === 'production') {
              toast({
                title: "Aviso de Segurança",
                description: "Ferramentas de desenvolvimento detectadas.",
                variant: "destructive"
              });
            }
          }
        } else {
          devtools.open = false;
        }
      }, 500);
    };

    initSecurity();

    // Cleanup
    return () => {
      document.removeEventListener('securitypolicyviolation', handleSecurityViolation);
      window.removeEventListener('error', handleError);
    };
  }, [toast]);

  return <>{children}</>;
};