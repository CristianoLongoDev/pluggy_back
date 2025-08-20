import { useState } from 'react';
import { supabase } from '@/integrations/supabase/client';

export interface Intent {
  id: string;
  bot_id: string;
  name?: string;
  intention?: string;
  active?: boolean;
  prompt?: string;
  function_id?: string;
}

export const useIntents = () => {
  const [intents, setIntents] = useState<Intent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getAuthHeaders = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) {
      throw new Error('Usuário não autenticado');
    }
    return {
      'Authorization': `Bearer ${session.access_token}`,
      'Content-Type': 'application/json',
    };
  };

  const fetchIntents = async (botId: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/intents`, {
        method: 'GET',
        headers,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: 'Erro desconhecido' }));
        throw new Error(errorData.message || `Erro HTTP: ${response.status}`);
      }

      const data = await response.json();
      setIntents(data.intents || []);
      return { success: true, data: data.intents };
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao buscar intenções';
      setError(errorMessage);
      console.error('Erro ao buscar intenções:', err);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  const createIntent = async (intentData: Omit<Intent, 'created_at' | 'updated_at'>, retryCount = 0) => {
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      
      // Remove campos null do payload
      const cleanedData = Object.fromEntries(
        Object.entries(intentData).filter(([_, value]) => value !== null && value !== undefined)
      );
      
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${intentData.bot_id}/intents`, {
        method: 'POST',
        headers,
        body: JSON.stringify(cleanedData),
      });

      if (!response.ok) {
        // Retry on 503 errors up to 2 times
        if (response.status === 503 && retryCount < 2) {
          setLoading(false);
          await new Promise(resolve => setTimeout(resolve, 1000 * (retryCount + 1)));
          return createIntent(intentData, retryCount + 1);
        }
        
        const errorData = await response.json().catch(() => ({ message: 'Erro desconhecido' }));
        throw new Error(errorData.message || `Erro HTTP: ${response.status}`);
      }

      const data = await response.json();
      return { success: true, data: data.intent };
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao criar intenção';
      setError(errorMessage);
      console.error('Erro ao criar intenção:', err);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  const updateIntent = async (botId: string, intentId: string, intentData: Partial<Intent>) => {
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      
      // Remove campos null do payload
      const cleanedData = Object.fromEntries(
        Object.entries(intentData).filter(([_, value]) => value !== null && value !== undefined)
      );
      
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/intents/${intentId}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(cleanedData),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: 'Erro desconhecido' }));
        throw new Error(errorData.message || `Erro HTTP: ${response.status}`);
      }

      const data = await response.json();
      return { success: true, data: data.intent };
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao atualizar intenção';
      setError(errorMessage);
      console.error('Erro ao atualizar intenção:', err);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  const deleteIntent = async (botId: string, intentId: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/intents/${intentId}`, {
        method: 'DELETE',
        headers,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: 'Erro desconhecido' }));
        throw new Error(errorData.message || `Erro HTTP: ${response.status}`);
      }

      return { success: true };
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao excluir intenção';
      setError(errorMessage);
      console.error('Erro ao excluir intenção:', err);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  return {
    intents,
    loading,
    error,
    fetchIntents,
    createIntent,
    updateIntent,
    deleteIntent,
  };
};