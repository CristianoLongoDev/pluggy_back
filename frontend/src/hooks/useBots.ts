import { useState } from 'react';
import { supabase } from '@/integrations/supabase/client';

export interface Bot {
  id: string;
  name: string;
  type: string;
  system_prompt: string;
  created_at?: string;
  updated_at?: string;
}

export const useBots = () => {
  const [bots, setBots] = useState<Bot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getAuthHeaders = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) {
      throw new Error('Token de acesso não encontrado');
    }
    return {
      'Authorization': `Bearer ${session.access_token}`,
      'Content-Type': 'application/json'
    };
  };

  const fetchBotsInternal = async (retryCount = 0) => {
    console.log('fetchBots - Starting to fetch bots, retry:', retryCount);
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      console.log('fetchBots - Headers obtained successfully');
      
      const response = await fetch('https://atendimento.pluggerbi.com/bots', {
        headers,
        signal: AbortSignal.timeout(10000) // 10 second timeout
      });
      
      console.log('fetchBots - Response status:', response.status);
      
      if (!response.ok) {
        throw new Error(`Erro ao buscar bots. Status: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('fetchBots - Response data:', data);
      setBots(data.bots || []);
      setError(null); // Clear any previous errors
    } catch (err) {
      console.error('Error fetching bots:', err);
      const errorMessage = err instanceof Error ? err.message : 'Erro desconhecido';
      
      // Retry up to 2 times for network errors
      if (retryCount < 2 && (errorMessage.includes('Failed to fetch') || errorMessage.includes('timeout'))) {
        console.log(`Retrying fetchBots in 2 seconds... (attempt ${retryCount + 1}/2)`);
        setTimeout(() => fetchBotsInternal(retryCount + 1), 2000);
        return;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const fetchBots = () => fetchBotsInternal(0);

  const createBot = async (botData: Omit<Bot, 'id'>) => {
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      const response = await fetch('https://atendimento.pluggerbi.com/bots', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          id: crypto.randomUUID(),
          ...botData
        })
      });
      
      if (!response.ok) {
        throw new Error(`Erro ao criar bot. Status: ${response.status}`);
      }
      
      await fetchBots(); // Refresh the list
      return { success: true };
    } catch (err) {
      console.error('Error creating bot:', err);
      setError(err instanceof Error ? err.message : 'Erro desconhecido');
      return { success: false, error: err instanceof Error ? err.message : 'Erro desconhecido' };
    } finally {
      setLoading(false);
    }
  };

  const updateBot = async (id: string, botData: Partial<Bot>) => {
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${id}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(botData)
      });
      
      if (!response.ok) {
        throw new Error(`Erro ao atualizar bot. Status: ${response.status}`);
      }
      
      await fetchBots(); // Refresh the list
      return { success: true };
    } catch (err) {
      console.error('Error updating bot:', err);
      setError(err instanceof Error ? err.message : 'Erro desconhecido');
      return { success: false, error: err instanceof Error ? err.message : 'Erro desconhecido' };
    } finally {
      setLoading(false);
    }
  };

  const deleteBot = async (id: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${id}`, {
        method: 'DELETE',
        headers
      });
      
      if (!response.ok) {
        throw new Error(`Erro ao excluir bot. Status: ${response.status}`);
      }
      
      await fetchBots(); // Refresh the list
      return { success: true };
    } catch (err) {
      console.error('Error deleting bot:', err);
      setError(err instanceof Error ? err.message : 'Erro desconhecido');
      return { success: false, error: err instanceof Error ? err.message : 'Erro desconhecido' };
    } finally {
      setLoading(false);
    }
  };

  const fetchBotFunctions = async (botId: string) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/functions/used`, {
        headers,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      // Filter only functions that are associated with this bot (used: "bot")
      const botFunctions = (data.functions || [])
        .filter((func: any) => func.used === 'bot')
        .map((func: any) => ({
          function_id: func.function_id,
          description: func.description || func.function_id
        }));
      
      return { success: true, data: botFunctions };
    } catch (err) {
      return { 
        success: false, 
        error: err instanceof Error ? err.message : 'Erro ao carregar funções do bot' 
      };
    }
  };

  const addFunctionToBot = async (botId: string, functionId: string) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/linked-functions`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ function_id: functionId }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return { success: true };
    } catch (err) {
      return { 
        success: false, 
        error: err instanceof Error ? err.message : 'Erro ao adicionar função ao bot' 
      };
    }
  };

  const removeFunctionFromBot = async (botId: string, functionId: string) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/linked-functions/${functionId}`, {
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
        error: err instanceof Error ? err.message : 'Erro ao remover função do bot' 
      };
    }
  };

  return {
    bots,
    loading,
    error,
    fetchBots,
    createBot,
    updateBot,
    deleteBot,
    fetchBotFunctions,
    addFunctionToBot,
    removeFunctionFromBot
  };
};