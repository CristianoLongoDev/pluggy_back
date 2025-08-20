import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { Bot, useBots } from '@/hooks/useBots';
import { useFunctions } from '@/hooks/useFunctions';
import { useIntegrations } from '@/hooks/useIntegrations';
import { X } from 'lucide-react';
import { botConfigSchema, sanitizeHtml } from '@/lib/validation';

interface BotFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (botData: Omit<Bot, 'id'> | { id: string } & Partial<Bot>) => Promise<{ success: boolean; error?: string }>;
  bot?: Bot | null;
  mode: 'create' | 'edit';
  selectedBotId?: string;
}

export const BotForm: React.FC<BotFormProps> = ({
  open,
  onOpenChange,
  onSubmit,
  bot,
  mode,
  selectedBotId
}) => {
  const { toast } = useToast();
  const { fetchBotFunctions, addFunctionToBot, removeFunctionFromBot } = useBots();
  const { functions, fetchFunctions } = useFunctions();
  const { integrations, fetchIntegrations } = useIntegrations();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    agent_name: '',
    integration_id: '',
    system_prompt: ''
  });
  
  // Function management state
  const [selectedFunctionId, setSelectedFunctionId] = useState<string>('');
  const [currentFunctions, setCurrentFunctions] = useState<Array<{ function_id: string; name: string }>>([]);
  const [originalFunctions, setOriginalFunctions] = useState<Array<{ function_id: string; name: string }>>([]);
  const [functionsToAdd, setFunctionsToAdd] = useState<Set<string>>(new Set());
  const [functionsToRemove, setFunctionsToRemove] = useState<Set<string>>(new Set());

  // Update form data when bot changes
  useEffect(() => {
    if (mode === 'edit' && bot) {
      console.log('BotForm - Edit mode, bot data:', bot);
      console.log('BotForm - Bot integration_id:', (bot as any).integration_id);
      setFormData({
        name: bot.name || '',
        agent_name: (bot as any).agent_name || '',
        integration_id: (bot as any).integration_id || 'none',
        system_prompt: bot.system_prompt || ''
      });
    } else if (mode === 'create') {
      setFormData({
        name: '',
        agent_name: '',
        integration_id: 'none',
        system_prompt: ''
      });
    }
  }, [bot, mode, open]);

  // Load integrations and functions when dialog opens
  useEffect(() => {
    if (open) {
      console.log('BotForm - Dialog opened, fetching integrations...');
      fetchIntegrations();
      
      if (selectedBotId) {
        fetchFunctions(selectedBotId);
        
        if (mode === 'edit' && bot) {
          loadBotFunctions(bot.id);
        } else {
          // Reset for create mode
          setCurrentFunctions([]);
          setOriginalFunctions([]);
          setFunctionsToAdd(new Set());
          setFunctionsToRemove(new Set());
        }
      }
    }
  }, [open, selectedBotId, bot, mode]);

  // Debug log for integrations
  useEffect(() => {
    console.log('BotForm - Integrations state updated:', integrations);
    console.log('BotForm - Current integration_id in form:', formData.integration_id);
  }, [integrations, formData.integration_id]);

  const loadBotFunctions = async (botId: string) => {
    const result = await fetchBotFunctions(botId);
    if (result.success) {
      const botFunctions = result.data.map((func: any) => ({
        function_id: func.function_id,
        name: func.description || func.function_id
      }));
      setCurrentFunctions(botFunctions);
      setOriginalFunctions([...botFunctions]);
      setFunctionsToAdd(new Set());
      setFunctionsToRemove(new Set());
    }
  };

  const addFunction = () => {
    if (!selectedFunctionId) return;
    
    const selectedFunction = functions.find(f => f.function_id === selectedFunctionId);
    if (!selectedFunction) return;
    
    // Don't allow adding functions that are used by prompts or other bots
    if (selectedFunction.used === 'prompt' || selectedFunction.used === 'bot') return;
    
    const isAlreadyAdded = currentFunctions.some(f => f.function_id === selectedFunctionId);
    if (isAlreadyAdded) return;
    
    const newFunction = {
      function_id: selectedFunction.function_id,
      name: selectedFunction.description || selectedFunction.function_id
    };
    
    setCurrentFunctions(prev => [...prev, newFunction]);
    
    // Track changes
    const wasOriginallyPresent = originalFunctions.some(f => f.function_id === selectedFunctionId);
    if (wasOriginallyPresent) {
      // Was removed before, now re-adding
      setFunctionsToRemove(prev => {
        const newSet = new Set(prev);
        newSet.delete(selectedFunctionId);
        return newSet;
      });
    } else {
      // New function to add
      setFunctionsToAdd(prev => new Set(prev).add(selectedFunctionId));
    }
    
    setSelectedFunctionId('');
  };

  const removeFunction = (functionId: string) => {
    setCurrentFunctions(prev => prev.filter(f => f.function_id !== functionId));
    
    // Track changes
    const wasOriginallyPresent = originalFunctions.some(f => f.function_id === functionId);
    if (wasOriginallyPresent) {
      // Original function being removed
      setFunctionsToRemove(prev => new Set(prev).add(functionId));
    } else {
      // Was added in this session, just remove from add list
      setFunctionsToAdd(prev => {
        const newSet = new Set(prev);
        newSet.delete(functionId);
        return newSet;
      });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Validate and sanitize form data
      const validationResult = botConfigSchema.safeParse({
        name: formData.name,
        description: '', // Optional field
        is_active: true,
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

      if (!formData.system_prompt.trim()) {
        toast({
          title: "Erro",
          description: "System Prompt é obrigatório",
          variant: "destructive"
        });
        setLoading(false);
        return;
      }

      const botData: any = {
        name: sanitizeHtml(formData.name),
        system_prompt: sanitizeHtml(formData.system_prompt)
      };

      // Add agent_name if provided
      if (formData.agent_name.trim()) {
        botData.agent_name = sanitizeHtml(formData.agent_name);
      }

      // Only add integration_id if it's not empty and not "none"
      if (formData.integration_id && formData.integration_id !== 'none') {
        botData.integration_id = formData.integration_id;
      }

      // Check if bot data changed
      const currentIntegration = formData.integration_id === 'none' ? null : formData.integration_id;
      const originalIntegration = (bot as any)?.integration_id || null;
      
      const botDataChanged = mode === 'create' || 
        (bot && (
          bot.name !== formData.name || 
          ((bot as any)?.agent_name || '') !== formData.agent_name ||
          originalIntegration !== currentIntegration || 
          bot.system_prompt !== formData.system_prompt
        ));

      // Submit bot data if changed
      let result = { success: true };
      if (botDataChanged) {
        if (mode === 'edit' && bot) {
          result = await onSubmit({ id: bot.id, ...botData });
        } else {
          result = await onSubmit(botData);
        }
      }

      if (!result.success) {
        toast({
          title: "Erro",
          description: (result as any).error || "Erro ao salvar bot",
          variant: "destructive"
        });
        setLoading(false);
        return;
      }

      // Handle function changes only for edit mode
      if (mode === 'edit' && bot) {
        // Remove functions
        for (const functionId of functionsToRemove) {
          const removeResult = await removeFunctionFromBot(bot.id, functionId);
          if (!removeResult.success) {
            toast({
              title: "Erro",
              description: `Erro ao remover função: ${removeResult.error}`,
              variant: "destructive"
            });
          }
        }

        // Add functions
        for (const functionId of functionsToAdd) {
          const addResult = await addFunctionToBot(bot.id, functionId);
          if (!addResult.success) {
            toast({
              title: "Erro",
              description: `Erro ao adicionar função: ${addResult.error}`,
              variant: "destructive"
            });
          }
        }
      }

      toast({
        title: "Sucesso",
        description: mode === 'edit' ? "Bot atualizado com sucesso" : "Bot criado com sucesso"
      });
      onOpenChange(false);
      setFormData({
        name: '',
        agent_name: '',
        integration_id: 'none',
        system_prompt: ''
      });
      setCurrentFunctions([]);
      setOriginalFunctions([]);
      setFunctionsToAdd(new Set());
      setFunctionsToRemove(new Set());
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
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>
            {mode === 'edit' ? 'Editar Bot' : 'Novo Bot'}
          </DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Nome *</Label>
            <Input
              id="name"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Nome do bot"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="agent_name">Nome do Agente</Label>
            <Input
              id="agent_name"
              value={formData.agent_name}
              onChange={(e) => setFormData(prev => ({ ...prev, agent_name: e.target.value }))}
              placeholder="Nome do agente responsável"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="integration">Integração</Label>
            {integrations.length > 0 ? (
              <Select
                value={formData.integration_id}
                onValueChange={(value) => setFormData(prev => ({ ...prev, integration_id: value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Selecione uma integração" />
                </SelectTrigger>
                <SelectContent className="bg-background border z-50">
                  <SelectItem value="none">
                    <div className="flex items-center space-x-2">
                      <span>Nenhuma</span>
                    </div>
                  </SelectItem>
                  {integrations
                    .filter(integration => integration.is_active === 1) // 1 = ativo no banco
                    .map((integration) => (
                      <SelectItem key={integration.id} value={integration.id}>
                        <div className="flex items-center space-x-2">
                          <img src="/lovable-uploads/569333c2-882a-47f0-a979-7cb705164fbd.png" alt="Movidesk" className="w-4 h-4 object-contain" />
                          <span>{integration.name}</span>
                        </div>
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            ) : (
              <div className="h-10 bg-muted animate-pulse rounded-md flex items-center px-3">
                <span className="text-muted-foreground text-sm">Carregando integrações...</span>
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="system_prompt">System Prompt *</Label>
            <Textarea
              id="system_prompt"
              value={formData.system_prompt}
              onChange={(e) => setFormData(prev => ({ ...prev, system_prompt: e.target.value }))}
              placeholder="Defina as instruções e comportamento do bot..."
              className="h-40"
              required
            />
          </div>

          {/* Functions Section */}
          <div className="space-y-2">
            <Label>Funções</Label>
            <div className="space-y-2">
              <div className="flex gap-2">
                <Select
                  value={selectedFunctionId}
                  onValueChange={setSelectedFunctionId}
                >
                  <SelectTrigger className="flex-1">
                    <SelectValue placeholder="Selecione uma função" />
                  </SelectTrigger>
                  <SelectContent>
                    {functions
                      .filter(f => !currentFunctions.some(cf => cf.function_id === f.function_id))
                      .map((func) => {
                        const isDisabled = func.used === 'prompt' || func.used === 'bot';
                        const displayText = func.used === 'prompt' 
                          ? `${func.description || func.function_id} (associado a um prompt)`
                          : func.description || func.function_id;
                        
                        return (
                          <SelectItem 
                            key={func.function_id} 
                            value={func.function_id}
                            disabled={isDisabled}
                          >
                            {displayText}
                          </SelectItem>
                        );
                      })}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  onClick={addFunction}
                  disabled={!selectedFunctionId}
                  variant="outline"
                >
                  Adicionar
                </Button>
              </div>
              
              {currentFunctions.length > 0 && (
                <div className="flex flex-wrap gap-2 p-2 border rounded-md min-h-[60px]">
                  {currentFunctions.map((func) => (
                    <Badge
                      key={func.function_id}
                      variant="secondary"
                      className="flex items-center gap-1"
                    >
                      {func.name}
                      <X
                        className="h-3 w-3 cursor-pointer"
                        onClick={() => removeFunction(func.function_id)}
                      />
                    </Badge>
                  ))}
                </div>
              )}
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
            <Button type="submit" disabled={loading}>
              {loading ? 'Salvando...' : (mode === 'edit' ? 'Atualizar' : 'Criar')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};