import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useToast } from '@/hooks/use-toast';
import { useIntents, Intent } from '@/hooks/useIntents';
import { useFunctions } from '@/hooks/useFunctions';
import { v4 as uuidv4 } from 'uuid';

interface IntentFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  intent: Intent | null;
  mode: 'create' | 'edit';
  botId: string;
  onSuccess: () => void;
}

const IntentForm: React.FC<IntentFormProps> = ({
  open,
  onOpenChange,
  intent,
  mode,
  botId,
  onSuccess,
}) => {
  const { toast } = useToast();
  const { createIntent, updateIntent, loading } = useIntents();
  const { functions, fetchFunctions } = useFunctions();
  
  const [formData, setFormData] = useState({
    name: '',
    intention: '',
    prompt: '',
    function_id: '',
    active: true,
  });

  useEffect(() => {
    if (intent && mode === 'edit') {
      setFormData({
        name: intent.name || '',
        intention: intent.intention || '',
        prompt: intent.prompt || '',
        function_id: intent.function_id || 'none',
        active: intent.active ?? true,
      });
    } else {
      setFormData({
        name: '',
        intention: '',
        prompt: '',
        function_id: 'none',
        active: true,
      });
    }
  }, [intent, mode, open]);

  useEffect(() => {
    if (open && botId) {
      console.log('Fetching functions for bot:', botId);
      const timeoutId = setTimeout(() => {
        fetchFunctions(botId);
      }, 100);
      
      return () => clearTimeout(timeoutId);
    }
  }, [open, botId]);

  useEffect(() => {
    console.log('Functions updated:', functions);
  }, [functions]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      toast({
        title: "Erro",
        description: "Nome da intenção é obrigatório",
        variant: "destructive",
      });
      return;
    }

    console.log('Iniciando salvamento da intenção:', formData);

    try {
      let result;
      
      if (mode === 'create') {
        console.log('Criando nova intenção...');
        result = await createIntent({
          id: uuidv4(),
          bot_id: botId,
          name: formData.name,
          intention: formData.intention,
          prompt: formData.prompt,
          function_id: formData.function_id === 'none' ? null : formData.function_id || null,
          active: formData.active,
        });
      } else {
        console.log('Atualizando intenção existente...');
        result = await updateIntent(botId, intent!.id, {
          name: formData.name,
          intention: formData.intention,
          prompt: formData.prompt,
          function_id: formData.function_id === 'none' ? null : formData.function_id || null,
          active: formData.active,
        });
      }

      console.log('Resultado do salvamento:', result);

      if (result.success) {
        toast({
          title: "Sucesso",
          description: mode === 'create' ? "Intenção criada com sucesso!" : "Intenção atualizada com sucesso!",
        });
        onSuccess();
        onOpenChange(false);
      } else {
        console.error('Erro no resultado:', result.error);
        toast({
          title: "Erro",
          description: result.error || "Erro ao salvar intenção",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Erro inesperado:', error);
      toast({
        title: "Erro",
        description: "Erro inesperado ao salvar intenção",
        variant: "destructive",
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {mode === 'create' ? 'Nova Intenção' : 'Editar Intenção'}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Informações Básicas</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Nome da Intenção *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Ex: Saudação, Despedida, Informações sobre produto..."
                  maxLength={50}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="intention">Descrição da Intenção</Label>
                <Textarea
                  id="intention"
                  value={formData.intention}
                  onChange={(e) => setFormData({ ...formData, intention: e.target.value })}
                  placeholder="Descreva quando e como esta intenção deve ser reconhecida..."
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="prompt">Prompt da Intenção</Label>
                <Textarea
                  id="prompt"
                  value={formData.prompt}
                  onChange={(e) => setFormData({ ...formData, prompt: e.target.value })}
                  placeholder="Defina como o bot deve responder quando esta intenção for detectada..."
                  rows={4}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="function_id">Função (opcional)</Label>
                <Select
                  value={formData.function_id}
                  onValueChange={(value) => setFormData({ ...formData, function_id: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione uma função disponível" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Nenhuma função</SelectItem>
                    {functions.map((func) => (
                      <SelectItem key={func.function_id} value={func.function_id}>
                        {func.name || func.function_id} {func.description && `- ${func.description}`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="active"
                  checked={formData.active}
                  onCheckedChange={(checked) => setFormData({ ...formData, active: checked })}
                />
                <Label htmlFor="active">Intenção ativa</Label>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end space-x-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Salvando...' : mode === 'create' ? 'Criar Intenção' : 'Salvar Alterações'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default IntentForm;