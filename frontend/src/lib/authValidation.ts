import { supabase } from '@/integrations/supabase/client';
import { logSecurityEvent } from './security';

interface TokenInfo {
  isValid: boolean;
  isExpired: boolean;
  hasAccountId: boolean;
  accountId?: string;
  expiresAt?: number;
  currentTime: number;
  payload?: any;
}

// Função para decodificar JWT sem verificar assinatura (apenas para debug)
function decodeJWT(token: string): any {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) {
      throw new Error('Token JWT inválido');
    }

    const payload = parts[1];
    // Adicionar padding se necessário
    const paddedPayload = payload + '='.repeat((4 - payload.length % 4) % 4);
    const decoded = atob(paddedPayload);
    return JSON.parse(decoded);
  } catch (error) {
    console.error('Erro ao decodificar JWT:', error);
    return null;
  }
}

// Verificar informações do token atual
export async function validateCurrentToken(): Promise<TokenInfo> {
  const currentTime = Math.floor(Date.now() / 1000);
  
  try {
    // Obter sessão atual
    const { data: { session }, error } = await supabase.auth.getSession();
    
    if (error) {
      console.error('❌ Erro ao obter sessão:', error.message);
      logSecurityEvent('SESSION_ERROR', { error: error.message });
      return {
        isValid: false,
        isExpired: true,
        hasAccountId: false,
        currentTime
      };
    }

    if (!session?.access_token) {
      console.warn('❌ Nenhum token de acesso encontrado');
      logSecurityEvent('NO_ACCESS_TOKEN');
      return {
        isValid: false,
        isExpired: true,
        hasAccountId: false,
        currentTime
      };
    }

    const token = session.access_token;
    const payload = decodeJWT(token);

    if (!payload) {
      console.error('❌ Não foi possível decodificar o token');
      return {
        isValid: false,
        isExpired: true,
        hasAccountId: false,
        currentTime
      };
    }

    // Verificar expiração
    const expiresAt = payload.exp;
    const isExpired = currentTime >= expiresAt;
    
    // Verificar se tem account_id
    const hasAccountId = !!payload.account_id;
    const accountId = payload.account_id;

    // Log detalhado para debug
    console.log('🔍 === VERIFICAÇÃO DE TOKEN ===');
    console.log('✅ Token encontrado:', !!token);
    console.log('✅ Token decodificado:', !!payload);
    console.log('✅ Tempo atual:', new Date(currentTime * 1000).toISOString());
    console.log('✅ Token expira em:', new Date(expiresAt * 1000).toISOString());
    console.log('✅ Token expirado?', isExpired ? '❌ SIM' : '✅ NÃO');
    console.log('✅ Tem account_id?', hasAccountId ? '✅ SIM' : '❌ NÃO');
    console.log('✅ Account ID:', accountId || 'AUSENTE');
    console.log('✅ User ID (sub):', payload.sub || 'AUSENTE');
    console.log('✅ Email:', payload.email || 'AUSENTE');
    console.log('✅ Role:', payload.role || 'AUSENTE');
    console.log('🔍 === FIM DA VERIFICAÇÃO ===');

    // Log evento de segurança se houver problemas
    if (isExpired || !hasAccountId) {
      logSecurityEvent('TOKEN_VALIDATION_FAILED', {
        isExpired,
        hasAccountId,
        accountId,
        expiresAt: new Date(expiresAt * 1000).toISOString()
      });
    }

    return {
      isValid: !isExpired && hasAccountId,
      isExpired,
      hasAccountId,
      accountId,
      expiresAt,
      currentTime,
      payload
    };

  } catch (error) {
    console.error('❌ Erro ao validar token:', error);
    logSecurityEvent('TOKEN_VALIDATION_ERROR', { error: error.message });
    
    return {
      isValid: false,
      isExpired: true,
      hasAccountId: false,
      currentTime
    };
  }
}

// Função para verificar headers de autorização
export function validateAuthHeaders(token?: string): boolean {
  if (!token) {
    console.error('❌ Token não fornecido para headers');
    return false;
  }

  const authHeader = `Bearer ${token}`;
  
  console.log('🔍 === VERIFICAÇÃO DE HEADERS ===');
  console.log('✅ Authorization Header:', authHeader.substring(0, 20) + '...');
  console.log('✅ Formato correto?', authHeader.startsWith('Bearer ') ? '✅ SIM' : '❌ NÃO');
  console.log('✅ Token length:', token.length);
  console.log('🔍 === FIM DA VERIFICAÇÃO DE HEADERS ===');

  return authHeader.startsWith('Bearer ') && token.length > 0;
}

// Função para forçar refresh do token se necessário
export async function refreshTokenIfNeeded(): Promise<boolean> {
  try {
    console.log('🔄 Verificando se precisa renovar token...');
    
    const { data: { session }, error } = await supabase.auth.refreshSession();
    
    if (error) {
      console.error('❌ Erro ao renovar sessão:', error.message);
      logSecurityEvent('TOKEN_REFRESH_FAILED', { error: error.message });
      return false;
    }

    if (session) {
      console.log('✅ Token renovado com sucesso');
      return true;
    } else {
      console.warn('⚠️ Nenhuma sessão retornada após refresh');
      return false;
    }
    
  } catch (error) {
    console.error('❌ Erro ao tentar renovar token:', error);
    logSecurityEvent('TOKEN_REFRESH_ERROR', { error: error.message });
    return false;
  }
}

// Função principal para executar todas as verificações
export async function runAuthDiagnostics(): Promise<void> {
  console.log('🚀 === INICIANDO DIAGNÓSTICO DE AUTENTICAÇÃO ===');
  
  // 1. Verificar token atual
  const tokenInfo = await validateCurrentToken();
  
  // 2. Verificar headers se token existe
  if (tokenInfo.payload) {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      validateAuthHeaders(session.access_token);
    }
  }
  
  // 3. Tentar refresh se necessário
  if (tokenInfo.isExpired && !tokenInfo.isValid) {
    console.log('🔄 Token expirado, tentando renovar...');
    const refreshed = await refreshTokenIfNeeded();
    
    if (refreshed) {
      console.log('✅ Token renovado, verificando novamente...');
      await validateCurrentToken();
    }
  }
  
  // 4. Resumo final
  console.log('📊 === RESUMO DO DIAGNÓSTICO ===');
  console.log('✅ Token válido:', tokenInfo.isValid ? '✅ SIM' : '❌ NÃO');
  console.log('✅ Token não expirado:', !tokenInfo.isExpired ? '✅ SIM' : '❌ NÃO');
  console.log('✅ Contém account_id:', tokenInfo.hasAccountId ? '✅ SIM' : '❌ NÃO');
  console.log('✅ Headers corretos:', tokenInfo.payload ? '✅ SIM' : '❌ NÃO');
  
  if (!tokenInfo.isValid) {
    console.warn('⚠️ AÇÃO NECESSÁRIA: Token inválido ou expirado');
    console.warn('💡 Sugestão: Fazer logout e login novamente');
  }
  
  console.log('🏁 === FIM DO DIAGNÓSTICO ===');
}