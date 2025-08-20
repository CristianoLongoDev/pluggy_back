import { supabase } from '@/integrations/supabase/client';
import { runAuthDiagnostics, validateCurrentToken } from './authValidation';
import { logSecurityEvent } from './security';

// Interceptor para requests HTTP com tratamento de 401
export class AuthInterceptor {
  private static instance: AuthInterceptor;
  private retryCount = new Map<string, number>();
  
  static getInstance(): AuthInterceptor {
    if (!AuthInterceptor.instance) {
      AuthInterceptor.instance = new AuthInterceptor();
    }
    return AuthInterceptor.instance;
  }

  async makeAuthenticatedRequest(
    url: string,
    options: RequestInit = {},
    maxRetries: number = 1
  ): Promise<Response> {
    const requestId = `${url}-${Date.now()}`;
    
    try {
      // Obter token atual
      const { data: { session }, error: sessionError } = await supabase.auth.getSession();
      
      if (sessionError || !session?.access_token) {
        console.error('❌ Erro ao obter sessão para request:', sessionError?.message);
        throw new Error('Não autenticado');
      }

      // Validar token antes de fazer a requisição
      const tokenInfo = await validateCurrentToken();
      
      if (!tokenInfo.isValid) {
        console.error('❌ Token inválido detectado antes da requisição');
        logSecurityEvent('INVALID_TOKEN_BEFORE_REQUEST', { url });
        
        // Tentar refresh automático
        const { data: { session: newSession }, error: refreshError } = await supabase.auth.refreshSession();
        
        if (refreshError || !newSession?.access_token) {
          console.error('❌ Falha ao renovar token:', refreshError?.message);
          throw new Error('Falha na autenticação');
        }
        
        console.log('✅ Token renovado automaticamente');
      }

      // Preparar headers com token válido
      const currentSession = await supabase.auth.getSession();
      const token = currentSession.data.session?.access_token;
      
      const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        ...options.headers,
      };

      console.log('🌐 Fazendo requisição autenticada para:', url);
      console.log('🔑 Token presente:', !!token);
      console.log('📋 Headers:', Object.keys(headers));

      // Fazer a requisição
      const response = await fetch(url, {
        ...options,
        headers,
      });

      // Tratar erro 401
      if (response.status === 401) {
        console.error('❌ Recebido erro 401 - Token rejeitado pelo servidor');
        
        const retries = this.retryCount.get(requestId) || 0;
        
        if (retries < maxRetries) {
          console.log(`🔄 Tentativa ${retries + 1}/${maxRetries} - Renovando token...`);
          this.retryCount.set(requestId, retries + 1);
          
          // Executar diagnóstico completo
          await runAuthDiagnostics();
          
          // Tentar refresh forçado
          const { data: { session: refreshedSession }, error: refreshError } = await supabase.auth.refreshSession();
          
          if (!refreshError && refreshedSession?.access_token) {
            console.log('✅ Token renovado, tentando requisição novamente...');
            // Recursive call com token novo
            return this.makeAuthenticatedRequest(url, options, maxRetries);
          } else {
            console.error('❌ Falha ao renovar token após 401:', refreshError?.message);
            logSecurityEvent('TOKEN_REFRESH_FAILED_AFTER_401', { 
              url, 
              error: refreshError?.message 
            });
          }
        } else {
          console.error('❌ Máximo de tentativas excedido para:', url);
          logSecurityEvent('MAX_RETRIES_EXCEEDED', { url, retries });
        }
        
        // Limpar contador de tentativas
        this.retryCount.delete(requestId);
        
        // Lançar erro específico para 401
        const error = new Error('Não autorizado - Token inválido ou expirado');
        (error as any).status = 401;
        throw error;
      }

      // Limpar contador se sucesso
      this.retryCount.delete(requestId);
      
      console.log(`✅ Requisição bem-sucedida: ${response.status} ${response.statusText}`);
      return response;

    } catch (error) {
      this.retryCount.delete(requestId);
      
      if (error instanceof Error && (error as any).status === 401) {
        throw error; // Re-throw 401 errors
      }
      
      console.error('❌ Erro na requisição autenticada:', error);
      logSecurityEvent('AUTHENTICATED_REQUEST_ERROR', {
        url,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      
      throw error;
    }
  }

  // Método específico para APIs externas
  async callExternalAPI(url: string, data?: any): Promise<any> {
    try {
      const response = await this.makeAuthenticatedRequest(url, {
        method: data ? 'POST' : 'GET',
        body: data ? JSON.stringify(data) : undefined,
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`❌ API Error ${response.status}:`, errorText);
        
        logSecurityEvent('EXTERNAL_API_ERROR', {
          url,
          status: response.status,
          error: errorText
        });
        
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }

      const responseData = await response.json();
      console.log('✅ API Response recebida:', Object.keys(responseData));
      
      return responseData;
      
    } catch (error) {
      console.error('❌ Erro ao chamar API externa:', error);
      throw error;
    }
  }
}

// Helper function para usar o interceptor
export const makeAuthenticatedRequest = (url: string, options?: RequestInit) => {
  return AuthInterceptor.getInstance().makeAuthenticatedRequest(url, options);
};

export const callExternalAPI = (url: string, data?: any) => {
  return AuthInterceptor.getInstance().callExternalAPI(url, data);
};