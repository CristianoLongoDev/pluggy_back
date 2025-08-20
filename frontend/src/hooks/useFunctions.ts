import { useState } from 'react';
import { supabase } from '@/integrations/supabase/client';

export interface BotFunction {
  bot_id?: string;
  function_id: string;
  name?: string;
  description?: string;
  action?: string | null;
  used?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface CreateFunctionData {
  function_id: string;
  description?: string;
}

interface UpdateFunctionData {
  description?: string;
}

export const useFunctions = () => {
  const [functions, setFunctions] = useState<BotFunction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cache, setCache] = useState<Map<string, { data: BotFunction[], timestamp: number }>>(new Map());

  const getAuthHeaders = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    return {
      'Authorization': `Bearer ${session?.access_token}`,
      'Content-Type': 'application/json',
    };
  };

  const fetchFunctions = async (botId: string, retryCount = 0) => {
    // Check cache first (valid for 30 seconds)
    const cached = cache.get(botId);
    if (cached && Date.now() - cached.timestamp < 30000) {
      setFunctions(cached.data);
      return;
    }

    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/functions`, {
        headers,
      });

      if (!response.ok) {
        // Retry on 503 errors up to 2 times
        if (response.status === 503 && retryCount < 2) {
          setTimeout(() => fetchFunctions(botId, retryCount + 1), 1000 * (retryCount + 1));
          return;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      const functionsData = data.functions || [];
      
      // Update cache
      setCache(prev => new Map(prev.set(botId, { data: functionsData, timestamp: Date.now() })));
      setFunctions(functionsData);
    } catch (err) {
      // Use cached data if available and error is network related
      if (cached && (err instanceof Error && (err.message.includes('503') || err.message.includes('Failed to fetch')))) {
        setFunctions(cached.data);
        setError('Usando dados em cache devido a instabilidade da API');
      } else {
        setError(err instanceof Error ? err.message : 'Erro ao carregar funções');
        setFunctions([]);
      }
    } finally {
      setLoading(false);
    }
  };

  const createFunction = async (botId: string, functionData: CreateFunctionData) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/functions`, {
        method: 'POST',
        headers,
        body: JSON.stringify(functionData),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return { success: true, data: data.function };
    } catch (err) {
      return { 
        success: false, 
        error: err instanceof Error ? err.message : 'Erro ao criar função' 
      };
    }
  };

  const updateFunction = async (botId: string, functionId: string, functionData: UpdateFunctionData) => {
    try {
      const headers = await getAuthHeaders();
      console.log('updateFunction - Headers:', headers);
      console.log('updateFunction - URL:', `https://atendimento.pluggerbi.com/bots/${botId}/functions/${functionId}`);
      console.log('updateFunction - Body:', JSON.stringify(functionData));
      
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/functions/${functionId}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(functionData),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return { success: true, data: data.function };
    } catch (err) {
      return { 
        success: false, 
        error: err instanceof Error ? err.message : 'Erro ao atualizar função' 
      };
    }
  };

  const deleteFunction = async (botId: string, functionId: string) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/functions/${functionId}`, {
        method: 'DELETE',
        headers,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return { success: true };
    } catch (err) {
      return { 
        success: false, 
        error: err instanceof Error ? err.message : 'Erro ao excluir função' 
      };
    }
  };

  return {
    functions,
    loading,
    error,
    fetchFunctions,
    createFunction,
    updateFunction,
    deleteFunction,
  };
};