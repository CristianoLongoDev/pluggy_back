import { useState, useCallback } from 'react';
import { supabase } from '@/integrations/supabase/client';

export interface Action {
  id: number;
  action: string;
  name: string;
  integration_type: string | null;
}

interface ActionsResponse {
  status: string;
  actions: Action[];
  total: number;
  filter: {
    integration_type: string | null;
  };
}

export const useActions = () => {
  const [actions, setActions] = useState<Action[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getAuthHeaders = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    return {
      'Authorization': `Bearer ${session?.access_token}`,
      'Content-Type': 'application/json',
    };
  };

  const fetchActions = useCallback(async (integrationType?: string | null) => {
    setLoading(true);
    setError(null);
    
    try {
      const headers = await getAuthHeaders();
      let url = 'https://atendimento.pluggerbi.com/bots/functions/actions';
      
      // Add filter for integration_type if provided
      if (integrationType) {
        url += `?integration_type=${integrationType}`;
      }
      
      const response = await fetch(url, {
        headers,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: ActionsResponse = await response.json();
      
      // Filter actions based on integration_type
      let filteredActions = data.actions;
      if (integrationType) {
        filteredActions = data.actions.filter(action => 
          action.integration_type === null || action.integration_type === integrationType
        );
      } else {
        // If no integration type specified, show only actions with null integration_type
        filteredActions = data.actions.filter(action => action.integration_type === null);
      }
      
      setActions(filteredActions);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar ações');
      setActions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    actions,
    loading,
    error,
    fetchActions,
  };
};