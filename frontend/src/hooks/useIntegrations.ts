import { useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';

export interface Integration {
  id: string;
  name: string;
  integration_type: 'movidesk' | 'whatsapp' | 'instagram' | 'chat_widget';
  is_active: number; // 1 = ativo, 0 = inativo
  phone_number?: string;
  // Campos sensíveis não retornam mais da API por segurança
  // access_token?: string;
  // client_id?: string;
  // client_secret?: string;
  created_at: string;
}

export interface CreateIntegrationData {
  name: string;
  integration_type: string;
  is_active: number; // 1 = ativo, 0 = inativo
  phone_number?: string;
  access_token?: string;
  client_id?: string;
  client_secret?: string;
}

export const useIntegrations = () => {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(false);
  const { session } = useAuth();

  const fetchIntegrations = useCallback(async () => {
    if (!session?.access_token) {
      console.log('No access token available');
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch('https://atendimento.pluggerbi.com/integrations', {
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        console.log('Integrations fetched:', data);
        // A API retorna os dados dentro da propriedade "integrations"
        const integrationsList = data.integrations || [];
        setIntegrations(Array.isArray(integrationsList) ? integrationsList : []);
      } else {
        console.error('Failed to fetch integrations:', response.statusText);
        setIntegrations([]);
      }
    } catch (error) {
      console.error('Error fetching integrations:', error);
      setIntegrations([]);
    } finally {
      setLoading(false);
    }
  }, [session?.access_token]);

  const createIntegration = useCallback(async (integrationData: CreateIntegrationData) => {
    if (!session?.access_token) {
      return { success: false, error: 'Não autenticado' };
    }

    try {
      const response = await fetch('https://atendimento.pluggerbi.com/integrations', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(integrationData),
      });

      if (response.ok) {
        await fetchIntegrations(); // Refresh the list
        return { success: true };
      } else {
        const errorData = await response.json().catch(() => ({}));
        return { success: false, error: errorData.message || 'Erro ao criar integração' };
      }
    } catch (error) {
      console.error('Error creating integration:', error);
      return { success: false, error: 'Erro de conexão' };
    }
  }, [session?.access_token, fetchIntegrations]);

  const updateIntegration = useCallback(async (id: string, integrationData: Partial<CreateIntegrationData>) => {
    if (!session?.access_token) {
      return { success: false, error: 'Não autenticado' };
    }

    try {
      const response = await fetch(`https://atendimento.pluggerbi.com/integrations/${id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(integrationData),
      });

      if (response.ok) {
        await fetchIntegrations(); // Refresh the list
        return { success: true };
      } else {
        const errorData = await response.json().catch(() => ({}));
        return { success: false, error: errorData.message || 'Erro ao atualizar integração' };
      }
    } catch (error) {
      console.error('Error updating integration:', error);
      return { success: false, error: 'Erro de conexão' };
    }
  }, [session?.access_token, fetchIntegrations]);

  const deleteIntegration = useCallback(async (id: string) => {
    if (!session?.access_token) {
      return { success: false, error: 'Não autenticado' };
    }

    try {
      const response = await fetch(`https://atendimento.pluggerbi.com/integrations/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
        },
      });

      if (response.ok) {
        await fetchIntegrations(); // Refresh the list
        return { success: true };
      } else {
        const errorData = await response.json().catch(() => ({}));
        return { success: false, error: errorData.message || 'Erro ao excluir integração' };
      }
    } catch (error) {
      console.error('Error deleting integration:', error);
      return { success: false, error: 'Erro de conexão' };
    }
  }, [session?.access_token, fetchIntegrations]);

  return {
    integrations,
    loading,
    fetchIntegrations,
    createIntegration,
    updateIntegration,
    deleteIntegration,
  };
};