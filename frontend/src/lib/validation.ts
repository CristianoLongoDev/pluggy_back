import { z } from 'zod';

// Chat and Message Validation
export const messageSchema = z.object({
  content: z.string()
    .min(1, 'Message cannot be empty')
    .max(4000, 'Message too long')
    .refine(
      (content) => {
        // Basic XSS prevention - no script tags
        const scriptRegex = /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi;
        return !scriptRegex.test(content);
      },
      'Invalid message content'
    ),
  type: z.enum(['text', 'image', 'file']).optional().default('text')
});

export const chatIdSchema = z.string().uuid('Invalid chat ID');
export const conversationIdSchema = z.union([z.number().int().positive(), z.string().regex(/^\d+$/)]).transform(val => String(val));

// WebSocket Message Validation
export const webSocketMessageSchema = z.object({
  type: z.enum([
    'new_message',
    'subscription_updated', 
    'messages_response',
    'get_messages',
    'send_message',
    'transfer_to_human',
    'subscribe_conversations'
  ]),
  data: z.any().optional()
});

// Bot Configuration Validation
export const botConfigSchema = z.object({
  name: z.string()
    .min(2, 'Bot name must be at least 2 characters')
    .max(100, 'Bot name too long')
    .regex(/^[a-zA-Z0-9\s\-_]+$/, 'Bot name contains invalid characters'),
  description: z.string()
    .max(500, 'Description too long')
    .optional(),
  is_active: z.boolean(),
  settings: z.record(z.string(), z.any()).optional()
});

// Channel Configuration Validation
export const channelConfigSchema = z.object({
  name: z.string()
    .min(2, 'Channel name must be at least 2 characters')
    .max(100, 'Channel name too long')
    .regex(/^[a-zA-Z0-9\s\-_]+$/, 'Channel name contains invalid characters'),
  type: z.enum(['whatsapp', 'telegram', 'webchat', 'email']),
  is_active: z.boolean(),
  settings: z.record(z.string(), z.any()).optional()
});

// Integration Configuration Validation
export const integrationConfigSchema = z.object({
  name: z.string()
    .min(2, 'Integration name must be at least 2 characters')
    .max(100, 'Integration name too long')
    .regex(/^[a-zA-Z0-9\s\-_]+$/, 'Integration name contains invalid characters'),
  type: z.enum(['api', 'webhook', 'database', 'external_service']),
  is_active: z.boolean(),
  config: z.record(z.string(), z.any()).optional()
});

// Prompt Validation
export const promptSchema = z.object({
  title: z.string()
    .min(2, 'Title must be at least 2 characters')
    .max(200, 'Title too long'),
  content: z.string()
    .min(10, 'Prompt content must be at least 10 characters')
    .max(10000, 'Prompt content too long'),
  is_active: z.boolean().optional().default(true),
  tags: z.array(z.string()).optional()
});

// Function Parameter Validation
export const functionParameterSchema = z.object({
  name: z.string()
    .min(1, 'Parameter name required')
    .max(100, 'Parameter name too long')
    .regex(/^[a-zA-Z_][a-zA-Z0-9_]*$/, 'Invalid parameter name'),
  type: z.enum(['string', 'number', 'boolean', 'object', 'array']),
  description: z.string().max(500, 'Description too long').optional(),
  required: z.boolean().optional().default(false),
  default_value: z.any().optional()
});

// User Profile Validation (excluding role for security)
export const userProfileUpdateSchema = z.object({
  full_name: z.string()
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name too long')
    .regex(/^[a-zA-Z\s\-']+$/, 'Name contains invalid characters')
    .optional(),
  email: z.string().email('Invalid email format').optional(),
  department: z.string()
    .max(100, 'Department name too long')
    .regex(/^[a-zA-Z0-9\s\-_]+$/, 'Department contains invalid characters')
    .optional(),
  avatar_url: z.string().url('Invalid avatar URL').optional()
});

// Rate limiting configuration
export const RATE_LIMITS = {
  MESSAGES_PER_MINUTE: 30,
  API_CALLS_PER_MINUTE: 100,
  WEBSOCKET_CONNECTIONS_PER_IP: 5
} as const;

// Validation helper functions
export function sanitizeHtml(input: string): string {
  return input
    .replace(/[<>]/g, '') // Remove basic HTML tags
    .replace(/javascript:/gi, '') // Remove javascript: protocols
    .replace(/on\w+=/gi, '') // Remove event handlers
    .trim();
}

export function validateAndSanitizeMessage(content: string): string {
  const result = messageSchema.parse({ content });
  return sanitizeHtml(result.content);
}

export function isValidUUID(uuid: string): boolean {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(uuid);
}