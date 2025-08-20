// Secure API client with input validation and error handling

import { canMakeApiCall, logSecurityEvent } from './security';

interface ApiResponse<T = any> {
  data?: T;
  error?: string;
  success: boolean;
}

export class SecureApiClient {
  private baseURL: string;
  private timeout: number;

  constructor(baseURL: string = '/api', timeout: number = 10000) {
    this.baseURL = baseURL;
    this.timeout = timeout;
  }

  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    // Rate limiting check
    if (!canMakeApiCall(endpoint)) {
      logSecurityEvent('RATE_LIMIT_EXCEEDED', { endpoint });
      return {
        success: false,
        error: 'Rate limit exceeded. Please try again later.'
      };
    }

    try {
      // Create abort controller for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);

      // Make request with security headers
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          ...options.headers,
        },
      });

      clearTimeout(timeoutId);

      // Check if response is OK
      if (!response.ok) {
        const errorText = await response.text();
        logSecurityEvent('API_ERROR', {
          endpoint,
          status: response.status,
          statusText: response.statusText
        });

        return {
          success: false,
          error: `HTTP ${response.status}: ${response.statusText}`
        };
      }

      // Parse JSON response
      const data = await response.json();
      
      // Validate response structure
      if (typeof data !== 'object' || data === null) {
        logSecurityEvent('INVALID_API_RESPONSE', { endpoint });
        return {
          success: false,
          error: 'Invalid response format'
        };
      }

      return {
        success: true,
        data
      };

    } catch (error) {
      if (error instanceof Error) {
        logSecurityEvent('API_REQUEST_FAILED', {
          endpoint,
          error: error.name,
          message: error.message
        });

        // Handle specific error types
        if (error.name === 'AbortError') {
          return {
            success: false,
            error: 'Request timeout'
          };
        }

        if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
          return {
            success: false,
            error: 'Network error. Please check your connection.'
          };
        }
      }

      return {
        success: false,
        error: 'An unexpected error occurred'
      };
    }
  }

  async get<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data: any): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async put<T>(endpoint: string, data: any): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, { method: 'DELETE' });
  }
}

// Export singleton instance
export const secureApiClient = new SecureApiClient();