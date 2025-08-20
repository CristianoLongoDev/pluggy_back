import { useState } from 'react';
import { supabase } from '@/integrations/supabase/client';

export interface FunctionParameter {
  function_id: string;
  parameter_id: string;
  name?: string;
  description?: string;
  type: 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array';
  permited_values?: string;
  default_value?: string;
  format?: 'email' | 'uri' | 'date' | 'date-time';
  created_at: string;
  updated_at: string;
}

interface CreateParameterData {
  parameter_id: string;
  description?: string;
  type: 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array';
  permited_values?: string;
  default_value?: string;
  format?: 'email' | 'uri' | 'date' | 'date-time';
}

interface UpdateParameterData {
  description?: string;
  type?: 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array';
  permited_values?: string;
  default_value?: string;
  format?: 'email' | 'uri' | 'date' | 'date-time';
}

export const useFunctionParameters = () => {
  const [parameters, setParameters] = useState<FunctionParameter[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getAuthHeaders = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    return {
      'Authorization': `Bearer ${session?.access_token}`,
      'Content-Type': 'application/json',
    };
  };

  const fetchParameters = async (botId: string, functionId: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/functions/${functionId}/parameters`, {
        headers,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setParameters(data.parameters || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar parâmetros');
      setParameters([]);
    } finally {
      setLoading(false);
    }
  };

  const createParameter = async (botId: string, functionId: string, parameterData: CreateParameterData) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/functions/${functionId}/parameters`, {
        method: 'POST',
        headers,
        body: JSON.stringify(parameterData),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return { success: true, data: data.parameter };
    } catch (err) {
      return { 
        success: false, 
        error: err instanceof Error ? err.message : 'Erro ao criar parâmetro' 
      };
    }
  };

  const updateParameter = async (botId: string, functionId: string, parameterId: string, parameterData: UpdateParameterData) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/functions/${functionId}/parameters/${parameterId}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(parameterData),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return { success: true, data: data.parameter };
    } catch (err) {
      return { 
        success: false, 
        error: err instanceof Error ? err.message : 'Erro ao atualizar parâmetro' 
      };
    }
  };

  const deleteParameter = async (botId: string, functionId: string, parameterId: string) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/functions/${functionId}/parameters/${parameterId}`, {
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
        error: err instanceof Error ? err.message : 'Erro ao excluir parâmetro' 
      };
    }
  };

  const createParametersBatch = async (botId: string, functionId: string, parametersData: CreateParameterData[]) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/functions/${functionId}/parameters`, {
        method: 'POST',
        headers,
        body: JSON.stringify(parametersData),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return { success: true, data: data.parameters };
    } catch (err) {
      return { 
        success: false, 
        error: err instanceof Error ? err.message : 'Erro ao criar parâmetros em lote' 
      };
    }
  };

  const deleteParametersBatch = async (botId: string, functionId: string, parameterIds: string[]) => {
    try {
      const headers = await getAuthHeaders();
      const response = await fetch(`https://atendimento.pluggerbi.com/bots/${botId}/functions/${functionId}/parameters`, {
        method: 'DELETE',
        headers,
        body: JSON.stringify({ parameter_ids: parameterIds }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return { success: true };
    } catch (err) {
      return { 
        success: false, 
        error: err instanceof Error ? err.message : 'Erro ao excluir parâmetros em lote' 
      };
    }
  };

  return {
    parameters,
    loading,
    error,
    fetchParameters,
    createParameter,
    updateParameter,
    deleteParameter,
    createParametersBatch,
    deleteParametersBatch,
  };
};