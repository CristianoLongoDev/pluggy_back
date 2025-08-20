import { useState } from 'react';
import { supabase } from '@/integrations/supabase/client';

export interface Prompt {
  bot_id: string;
  id: string;
  prompt: string;
  description?: string;
  rule_display?: string;
  created_at?: string;
  updated_at?: string;
}

export const usePrompts = () => {
  const [prompts, setPrompts] = useState<Prompt[]>([]);
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

  const fetchPrompts = async (botId: string) => {
    console.log('fetchPrompts - Starting to fetch prompts for bot:', botId);
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/prompts`, {
        headers
      });
      
      console.log('fetchPrompts - Response status:', response.status);
      
      if (!response.ok) {
        throw new Error(`Erro ao buscar prompts. Status: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('fetchPrompts - Response data:', data);
      setPrompts(data.prompts || []);
    } catch (err) {
      console.error('Error fetching prompts:', err);
      setError(err instanceof Error ? err.message : 'Erro desconhecido');
    } finally {
      setLoading(false);
    }
  };

  const createPrompt = async (promptData: Omit<Prompt, 'created_at' | 'updated_at'>) => {
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      console.log('=== CREATE PROMPT DEBUG ===');
      console.log('URL:', `https://atendimento.pluggerbi.com/bots/${promptData.bot_id}/prompts`);
      console.log('Headers:', headers);
      console.log('Body:', JSON.stringify(promptData, null, 2));
      
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${promptData.bot_id}/prompts`, {
        method: 'POST',
        headers,
        body: JSON.stringify(promptData)
      });
      
      console.log('Response Status:', response.status);
      console.log('Response Headers:', Object.fromEntries(response.headers.entries()));
      
      const responseText = await response.text();
      console.log('Response Body:', responseText);
      
      if (!response.ok) {
        throw new Error(`Erro ao criar prompt. Status: ${response.status}`);
      }
      
      await fetchPrompts(promptData.bot_id); // Refresh the list
      return { success: true };
    } catch (err) {
      console.error('Error creating prompt:', err);
      setError(err instanceof Error ? err.message : 'Erro desconhecido');
      return { success: false, error: err instanceof Error ? err.message : 'Erro desconhecido' };
    } finally {
      setLoading(false);
    }
  };

  const updatePrompt = async (botId: string, promptId: string, promptData: Partial<Prompt>) => {
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      console.log('=== UPDATE PROMPT DEBUG ===');
      console.log('URL:', `https://atendimento.pluggerbi.com/bots/${botId}/prompts/${promptId}`);
      console.log('Headers:', headers);
      console.log('Body:', JSON.stringify(promptData, null, 2));
      
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/prompts/${promptId}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(promptData)
      });
      
      console.log('Response Status:', response.status);
      console.log('Response Headers:', Object.fromEntries(response.headers.entries()));
      
      const responseText = await response.text();
      console.log('Response Body:', responseText);
      
      if (!response.ok) {
        throw new Error(`Erro ao atualizar prompt. Status: ${response.status}`);
      }
      
      await fetchPrompts(botId); // Refresh the list
      return { success: true };
    } catch (err) {
      console.error('Error updating prompt:', err);
      setError(err instanceof Error ? err.message : 'Erro desconhecido');
      return { success: false, error: err instanceof Error ? err.message : 'Erro desconhecido' };
    } finally {
      setLoading(false);
    }
  };

  const deletePrompt = async (botId: string, promptId: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/prompts/${promptId}`, {
        method: 'DELETE',
        headers
      });
      
      if (!response.ok) {
        throw new Error(`Erro ao excluir prompt. Status: ${response.status}`);
      }
      
      await fetchPrompts(botId); // Refresh the list
      return { success: true };
    } catch (err) {
      console.error('Error deleting prompt:', err);
      setError(err instanceof Error ? err.message : 'Erro desconhecido');
      return { success: false, error: err instanceof Error ? err.message : 'Erro desconhecido' };
    } finally {
      setLoading(false);
    }
  };


  const fetchPromptFunctions = async (botId: string, promptId: string) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/prompts/${promptId}/functions`, {
        headers
      });
      
      if (!response.ok) {
        throw new Error(`Erro ao buscar funções do prompt. Status: ${response.status}`);
      }
      
      const data = await response.json();
      return { success: true, functions: data.functions || [] };
    } catch (err) {
      console.error('Error fetching prompt functions:', err);
      return { success: false, error: err instanceof Error ? err.message : 'Erro desconhecido' };
    }
  };

  const addFunctionToPrompt = async (botId: string, promptId: string, functionId: string) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/prompts/${promptId}/functions`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ function_id: functionId })
      });
      
      if (!response.ok) {
        throw new Error(`Erro ao adicionar função ao prompt. Status: ${response.status}`);
      }
      
      return { success: true };
    } catch (err) {
      console.error('Error adding function to prompt:', err);
      return { success: false, error: err instanceof Error ? err.message : 'Erro desconhecido' };
    }
  };

  const removeFunctionFromPrompt = async (botId: string, promptId: string, functionId: string) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/prompts/${promptId}/functions/${functionId}`, {
        method: 'DELETE',
        headers
      });
      
      if (!response.ok) {
        throw new Error(`Erro ao remover função do prompt. Status: ${response.status}`);
      }
      
      return { success: true };
    } catch (err) {
      console.error('Error removing function from prompt:', err);
      return { success: false, error: err instanceof Error ? err.message : 'Erro desconhecido' };
    }
  };

  return {
    prompts,
    loading,
    error,
    fetchPrompts,
    createPrompt,
    updatePrompt,
    deletePrompt,
    fetchPromptFunctions,
    addFunctionToPrompt,
    removeFunctionFromPrompt
  };
};