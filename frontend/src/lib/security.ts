// Security utilities and middleware

// Rate limiting storage
const rateLimitStore = new Map<string, { count: number; resetTime: number }>();

export class RateLimiter {
  private static instance: RateLimiter;
  
  static getInstance(): RateLimiter {
    if (!RateLimiter.instance) {
      RateLimiter.instance = new RateLimiter();
    }
    return RateLimiter.instance;
  }

  private getKey(identifier: string, action: string): string {
    return `${identifier}:${action}`;
  }

  public isAllowed(
    identifier: string, 
    action: string, 
    limit: number, 
    windowMs: number = 60000 // 1 minute default
  ): boolean {
    const key = this.getKey(identifier, action);
    const now = Date.now();
    
    // Clean up expired entries
    this.cleanup();
    
    const current = rateLimitStore.get(key);
    
    if (!current || now > current.resetTime) {
      // Reset or create new entry
      rateLimitStore.set(key, {
        count: 1,
        resetTime: now + windowMs
      });
      return true;
    }
    
    if (current.count >= limit) {
      return false;
    }
    
    current.count++;
    return true;
  }

  private cleanup(): void {
    const now = Date.now();
    for (const [key, value] of rateLimitStore.entries()) {
      if (now > value.resetTime) {
        rateLimitStore.delete(key);
      }
    }
  }

  public reset(identifier: string, action: string): void {
    const key = this.getKey(identifier, action);
    rateLimitStore.delete(key);
  }
}

// Security headers and CSP
export const securityHeaders = {
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'X-XSS-Protection': '1; mode=block',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'
};

// Content Security Policy
export const contentSecurityPolicy = {
  'default-src': "'self'",
  'script-src': "'self' 'unsafe-inline' 'unsafe-eval'", // Note: unsafe-eval needed for React dev
  'style-src': "'self' 'unsafe-inline'",
  'img-src': "'self' data: https:",
  'font-src': "'self' data:",
  'connect-src': "'self' wss: https:",
  'frame-ancestors': "'none'"
};

// IP address extraction for rate limiting
export function getClientIdentifier(): string {
  // In a browser environment, we use a combination of user agent and session
  // In production, this should be enhanced with proper IP detection
  const userAgent = navigator.userAgent;
  const sessionId = sessionStorage.getItem('session_id') || 'anonymous';
  
  return btoa(`${userAgent.slice(0, 50)}:${sessionId}`);
}

// Message rate limiting
export function canSendMessage(): boolean {
  const rateLimiter = RateLimiter.getInstance();
  const identifier = getClientIdentifier();
  
  return rateLimiter.isAllowed(identifier, 'send_message', 30, 60000); // 30 messages per minute
}

// API call rate limiting
export function canMakeApiCall(endpoint: string): boolean {
  const rateLimiter = RateLimiter.getInstance();
  const identifier = getClientIdentifier();
  
  return rateLimiter.isAllowed(identifier, `api:${endpoint}`, 100, 60000); // 100 API calls per minute
}

// WebSocket connection rate limiting
export function canConnectWebSocket(): boolean {
  const rateLimiter = RateLimiter.getInstance();
  const identifier = getClientIdentifier();
  
  return rateLimiter.isAllowed(identifier, 'websocket_connect', 5, 300000); // 5 connections per 5 minutes
}

// Input sanitization helpers
export function sanitizeFileName(filename: string): string {
  return filename
    .replace(/[^a-zA-Z0-9.-]/g, '_')
    .replace(/\.{2,}/g, '.')
    .slice(0, 255);
}

export function sanitizeUrl(url: string): string {
  try {
    const parsedUrl = new URL(url);
    
    // Only allow https and http protocols
    if (!['https:', 'http:'].includes(parsedUrl.protocol)) {
      throw new Error('Invalid protocol');
    }
    
    return parsedUrl.toString();
  } catch {
    return '';
  }
}

// Error logging without sensitive data
export function logSecurityEvent(event: string, details: Record<string, any> = {}): void {
  // Remove sensitive fields
  const sanitizedDetails = { ...details };
  delete sanitizedDetails.password;
  delete sanitizedDetails.token;
  delete sanitizedDetails.secret;
  delete sanitizedDetails.key;
  
  console.warn(`[SECURITY] ${event}`, sanitizedDetails);
}

// Secure random string generation
export function generateSecureId(length: number = 32): string {
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
}