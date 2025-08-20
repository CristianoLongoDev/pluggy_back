import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';
import type { Integration, CreateIntegrationData } from '@/hooks/useIntegrations';

interface IntegrationFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: CreateIntegrationData) => Promise<{ success: boolean; error?: string }>;
  integration?: Integration | null;
  mode: 'create' | 'edit';
}

const integrationOptions = [
  { value: 'movidesk', label: 'Movidesk', icon: '/lovable-uploads/569333c2-882a-47f0-a979-7cb705164fbd.png' },
];

export const IntegrationForm: React.FC<IntegrationFormProps> = ({
  open,
  onOpenChange,
  onSubmit,
  integration,
  mode,
}) => {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<CreateIntegrationData>({
    name: '',
    integration_type: '',
    is_active: 1, // 1 = ativo
    phone_number: '',
    access_token: '',
    client_id: '',
    client_secret: '',
  });

  useEffect(() => {
    if (integration && mode === 'edit') {
      setFormData({
        name: integration.name || '',
        integration_type: integration.integration_type || '',
        is_active: integration.is_active ?? 1, // Usar padrão do banco
        phone_number: integration.phone_number || '',
        // Campos sensíveis não são preenchidos em modo de edição
        access_token: '',
        client_id: '',
        client_secret: '',
      });
    } else {
      setFormData({
        name: '',
        integration_type: 'movidesk',
        is_active: 1, // 1 = ativo no banco
        phone_number: '',
        access_token: '',
        client_id: '',
        client_secret: '',
      });
    }
  }, [integration, mode, open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Prepare data to send - remove empty fields
      const dataToSend = { ...formData };
      Object.keys(dataToSend).forEach(key => {
        if (dataToSend[key as keyof CreateIntegrationData] === '') {
          delete dataToSend[key as keyof CreateIntegrationData];
        }
      });

      const result = await onSubmit(dataToSend);
      
      if (result.success) {
        toast({
          title: "Sucesso",
          description: mode === 'edit' ? "Integração atualizada com sucesso" : "Integração criada com sucesso"
        });
        onOpenChange(false);
      } else {
        toast({
          title: "Erro",
          description: result.error || "Erro ao salvar integração",
          variant: "destructive"
        });
      }
    } catch (error) {
      toast({
        title: "Erro",
        description: "Erro inesperado ao salvar integração",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const renderFieldsByType = () => {
    const isEditMode = mode === 'edit';
    
    if (formData.integration_type === 'movidesk') {
      return (
        <div className="space-y-4">
          <div>
            <Label htmlFor="access_token">Token de Acesso</Label>
            <Input
              id="access_token"
              value={formData.access_token || ''}
              onChange={(e) => setFormData({ ...formData, access_token: e.target.value })}
              placeholder={isEditMode ? "Insira o novo token de acesso" : "Digite o token de acesso"}
              required={!isEditMode}
            />
            {isEditMode && (
              <p className="text-sm text-muted-foreground mt-1">
                Deixe em branco para manter o token atual
              </p>
            )}
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {mode === 'edit' ? 'Editar Integração' : 'Nova Integração'}
          </DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-4">
            <div>
              <Label htmlFor="integration_type">Tipo de Integração</Label>
              <Select 
                value={formData.integration_type} 
                onValueChange={(value) => setFormData({ ...formData, integration_type: value })}
                disabled={mode === 'edit'}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Selecione o tipo de integração" />
                </SelectTrigger>
                <SelectContent>
                  {integrationOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      <div className="flex items-center space-x-2">
                        <img src={option.icon} alt={option.label} className="w-6 h-6 object-contain" />
                        <span>{option.label}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="name">Nome</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Digite um nome para esta integração"
                maxLength={100}
                required
              />
            </div>

            {renderFieldsByType()}

            <div className="flex items-center space-x-2">
              <Switch
                id="is_active"
                checked={formData.is_active === 1} // Converter para boolean para o Switch
                onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked ? 1 : 0 })} // Converter de volta para número
              />
              <Label htmlFor="is_active">Ativo</Label>
            </div>
          </div>

          <div className="flex justify-end space-x-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Cancelar
            </Button>
            <Button 
              type="submit" 
              disabled={loading || !formData.integration_type || !formData.name}
            >
              {loading ? 'Salvando...' : mode === 'edit' ? 'Atualizar' : 'Criar'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};