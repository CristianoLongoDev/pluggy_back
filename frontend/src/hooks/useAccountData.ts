import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { runAuthDiagnostics, validateCurrentToken } from '@/lib/authValidation';
import { callExternalAPI } from '@/lib/authInterceptor';
import { logSecurityEvent } from '@/lib/security';

interface AccountData {
  id: string;
  name: string;
}

export const useAccountData = () => {
  const { user, profile } = useAuth();
  const [accountData, setAccountData] = useState<AccountData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchAccountData = async () => {
      if (!user || !profile?.account_id) {
        console.log('👤 Usuário ou account_id não disponível');
        return;
      }

      setLoading(true);
      
      try {
        console.log('🔍 === INICIANDO BUSCA DE DADOS DA CONTA ===');
        
        // Executar diagnóstico de autenticação ANTES da requisição
        await runAuthDiagnostics();
        
        // Validar token atual
        const tokenInfo = await validateCurrentToken();
        
        if (!tokenInfo.isValid) {
          console.error('❌ Token inválido detectado');
          setError('Token de autenticação inválido. Faça login novamente.');
          setLoading(false);
          return;
        }

        console.log('✅ Token validado, fazendo requisição para API externa...');
        console.log('🎯 Account ID:', profile.account_id);
        
        // Usar o interceptor para fazer a requisição
        const data = await callExternalAPI(
          `https://atendimento.pluggerbi.com/accounts/${profile.account_id}`
        );
        
        console.log('✅ Dados da conta recebidos:', data);
        setAccountData({
          id: profile.account_id,
          name: data.account?.name || 'Nome da conta não encontrado'
        });
        setError(null);
        
      } catch (err: any) {
        console.error('❌ Erro ao buscar dados da conta:', err);
        
        // Tratamento específico para erro 401
        if (err.status === 401) {
          setError('Sessão expirada. Por favor, faça login novamente.');
          logSecurityEvent('ACCOUNT_API_UNAUTHORIZED', { accountId: profile.account_id });
        } else {
          setError(err.message || 'Erro ao carregar dados da conta');
          logSecurityEvent('ACCOUNT_API_ERROR', { 
            accountId: profile.account_id,
            error: err.message 
          });
        }
        
        setAccountData({
          id: profile.account_id,
          name: 'Erro ao carregar nome da conta'
        });
      } finally {
        setLoading(false);
      }
    };

    fetchAccountData();
  }, [user, profile?.account_id]);

  return { accountData, loading, error };
};