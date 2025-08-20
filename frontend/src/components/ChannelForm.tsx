import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { Channel } from '@/hooks/useChannels';
import { useBots } from '@/hooks/useBots';
import { channelConfigSchema, sanitizeHtml, isValidUUID } from '@/lib/validation';

interface ChannelFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (channelData: Omit<Channel, 'id'> | { id: string } & Partial<Channel>) => Promise<{ success: boolean; error?: string }>;
  channel?: Channel | null;
  mode: 'create' | 'edit';
}

export const ChannelForm: React.FC<ChannelFormProps> = ({
  open,
  onOpenChange,
  onSubmit,
  channel,
  mode
}) => {
  const { toast } = useToast();
  const { bots, fetchBots } = useBots();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    type: 'whatsapp',
    name: '',
    botAgent: '',
    active: true,
    phone_number: '',
    client_id: '',
    client_secret: '',
    access_token: ''
  });

  // Fetch bots when component opens
  useEffect(() => {
    if (open) {
      fetchBots();
    }
  }, [open, fetchBots]);

  // Update form data when channel changes
  useEffect(() => {
    if (mode === 'edit' && channel) {
      console.log('ChannelForm - Loading channel for edit:', channel);
      setFormData({
        type: channel.type || 'whatsapp',
        name: channel.name || '',
        botAgent: channel.bot_id || '',
        active: channel.active || false,
        phone_number: (channel as any).phone_number || '',
        client_id: '',
        client_secret: '',
        access_token: ''
      });
    } else if (mode === 'create') {
      setFormData({
        type: 'whatsapp',
        name: '',
        botAgent: '',
        active: true,
        phone_number: '',
        client_id: '',
        client_secret: '',
        access_token: ''
      });
    }
  }, [channel, mode, open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Validate and sanitize form data
      const validationResult = channelConfigSchema.safeParse({
        name: formData.name,
        type: formData.type,
        is_active: formData.active,
        settings: {}
      });

      if (!validationResult.success) {
        toast({
          title: "Erro de Validação",
          description: validationResult.error.errors.map(e => e.message).join(', '),
          variant: "destructive"
        });
        setLoading(false);
        return;
      }

      // Validate bot agent is required and is valid UUID
      if (!formData.botAgent || !isValidUUID(formData.botAgent)) {
        toast({
          title: "Erro",
          description: "Agente Bot válido é obrigatório",
          variant: "destructive"
        });
        setLoading(false);
        return;
      }

      // Validate required fields based on type
      if (formData.type === 'whatsapp' && !formData.phone_number) {
        toast({
          title: "Erro",
          description: "Número de telefone é obrigatório para WhatsApp",
          variant: "destructive"
        });
        setLoading(false);
        return;
      }

      if (formData.type === 'instagram' && (!formData.client_id || !formData.client_secret)) {
        toast({
          title: "Erro",
          description: "Client ID e Client Secret são obrigatórios para Instagram",
          variant: "destructive"
        });
        setLoading(false);
        return;
      }

      if (formData.type === 'chat_widget' && !formData.access_token) {
        toast({
          title: "Erro",
          description: "Access Token é obrigatório para Chat Widget",
          variant: "destructive"
        });
        setLoading(false);
        return;
      }

      const channelData: any = {
        type: formData.type,
        name: sanitizeHtml(formData.name),
        bot_id: formData.botAgent,
        active: formData.active
      };

      // Add type-specific fields only if they have values (sanitized)
      if (formData.type === 'whatsapp' && formData.phone_number) {
        // Validate phone number format (basic validation)
        const phoneRegex = /^[0-9+\-\s()]+$/;
        if (!phoneRegex.test(formData.phone_number)) {
          toast({
            title: "Erro",
            description: "Formato de telefone inválido",
            variant: "destructive"
          });
          setLoading(false);
          return;
        }
        channelData.phone_number = sanitizeHtml(formData.phone_number);
      }
      if (formData.type === 'instagram') {
        if (formData.client_id) channelData.client_id = formData.client_id;
        if (formData.client_secret) channelData.client_secret = formData.client_secret;
      }
      if (formData.type === 'chat_widget' && formData.access_token) {
        channelData.access_token = formData.access_token;
      }

      let result;
      if (mode === 'edit' && channel) {
        result = await onSubmit({ id: channel.id, ...channelData });
      } else {
        result = await onSubmit(channelData);
      }

      if (result.success) {
        toast({
          title: "Sucesso",
          description: mode === 'edit' ? "Canal atualizado com sucesso" : "Canal criado com sucesso"
        });
        onOpenChange(false);
        setFormData({
          type: 'whatsapp',
          name: '',
          botAgent: '',
          active: true,
          phone_number: '',
          client_id: '',
          client_secret: '',
          access_token: ''
        });
      } else {
        toast({
          title: "Erro",
          description: result.error || "Erro ao salvar canal",
          variant: "destructive"
        });
      }
    } catch (err) {
      toast({
        title: "Erro",
        description: "Erro inesperado",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {mode === 'edit' ? 'Editar Canal' : 'Novo Canal'}
          </DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="type">Tipo</Label>
            <Select
              value={formData.type}
              onValueChange={(value) => setFormData(prev => ({ ...prev, type: value }))}
              disabled={mode === 'edit'}
            >
              <SelectTrigger className={mode === 'edit' ? 'opacity-50 cursor-not-allowed' : ''}>
                <SelectValue placeholder="Selecione o tipo" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="whatsapp">WhatsApp</SelectItem>
                <SelectItem value="instagram">Instagram</SelectItem>
                <SelectItem value="chat_widget">Chat Widget</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="name">Nome</Label>
            <Input
              id="name"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Nome do canal"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="botAgent">Agente Bot *</Label>
            <Select
              value={formData.botAgent}
              onValueChange={(value) => setFormData(prev => ({ ...prev, botAgent: value }))}
              disabled={loading || mode === 'edit'}
            >
              <SelectTrigger className={mode === 'edit' ? 'opacity-50 cursor-not-allowed' : ''}>
                <SelectValue placeholder={
                  bots.length === 0 
                    ? "Carregando bots..." 
                    : "Selecione o agente bot"
                } />
              </SelectTrigger>
              <SelectContent className="bg-background border z-50">
                {bots.map((bot) => (
                  <SelectItem key={bot.id} value={bot.id}>
                    {bot.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="status">Status</Label>
            <Select
              value={formData.active ? "true" : "false"}
              onValueChange={(value) => setFormData(prev => ({ ...prev, active: value === "true" }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Selecione o status" />
              </SelectTrigger>
              <SelectContent className="bg-background border z-50">
                <SelectItem value="true">Ativo</SelectItem>
                <SelectItem value="false">Desabilitado</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {formData.type === 'whatsapp' && (
            <div className="space-y-2">
              <Label htmlFor="phone_number">Número de Telefone *</Label>
              <Input
                id="phone_number"
                value={formData.phone_number}
                onChange={(e) => setFormData(prev => ({ ...prev, phone_number: e.target.value }))}
                placeholder="5511999999999"
                required
              />
            </div>
          )}

          {formData.type === 'instagram' && (
            <>
              <div className="space-y-2">
                <Label htmlFor="client_id">Client ID *</Label>
                <Input
                  id="client_id"
                  value={formData.client_id}
                  onChange={(e) => setFormData(prev => ({ ...prev, client_id: e.target.value }))}
                  placeholder={mode === 'edit' ? "Informe o novo Client ID caso deseje alterar" : "Client ID do Instagram"}
                  required={mode === 'create'}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="client_secret">Client Secret *</Label>
                <Input
                  id="client_secret"
                  type="password"
                  value={formData.client_secret}
                  onChange={(e) => setFormData(prev => ({ ...prev, client_secret: e.target.value }))}
                  placeholder={mode === 'edit' ? "Informe o novo Client Secret caso deseje alterar" : "Client Secret do Instagram"}
                  required={mode === 'create'}
                />
              </div>
            </>
          )}

          {formData.type === 'chat_widget' && (
            <div className="space-y-2">
              <Label htmlFor="access_token">Access Token *</Label>
              <Input
                id="access_token"
                type="password"
                value={formData.access_token}
                onChange={(e) => setFormData(prev => ({ ...prev, access_token: e.target.value }))}
                placeholder={mode === 'edit' ? "Informe o novo Access Token caso deseje alterar" : "Access Token do Chat Widget"}
                required={mode === 'create'}
              />
            </div>
          )}

          <div className="flex justify-end space-x-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Salvando...' : (mode === 'edit' ? 'Atualizar' : 'Criar')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};