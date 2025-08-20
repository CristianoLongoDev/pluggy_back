import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { Prompt, usePrompts } from '@/hooks/usePrompts';
import { useFunctions } from '@/hooks/useFunctions';
import { X } from 'lucide-react';

interface PromptFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  prompt?: Prompt | null;
  mode: 'create' | 'edit';
  botId: string;
  onSuccess?: () => void;
}

const PromptForm = ({ open, onOpenChange, prompt, mode, botId, onSuccess }: PromptFormProps) => {
  const { toast } = useToast();
  const { createPrompt, updatePrompt, fetchPromptFunctions, addFunctionToPrompt, removeFunctionFromPrompt } = usePrompts();
  const { functions, fetchFunctions } = useFunctions();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    id: '',
    prompt: '',
    description: '',
    display_rule: 'first_contact'
  });
  const [selectedFunctions, setSelectedFunctions] = useState<string[]>([]);
  const [originalFunctions, setOriginalFunctions] = useState<string[]>([]);
  const [selectedFunctionId, setSelectedFunctionId] = useState('');

  useEffect(() => {
    if (open) {
      // Load available functions
      fetchFunctions(botId);
      
      if (mode === 'edit' && prompt) {
        const ruleDisplay = prompt.rule_display || 'first contact';
        setFormData({
          id: prompt.id || '',
          prompt: prompt.prompt || '',
          description: prompt.description || '',
          display_rule: ruleDisplay.split(' ').join('_')
        });
        
        // Load existing functions for this prompt
        loadPromptFunctions(prompt.id);
      } else if (mode === 'create') {
        setFormData({
          id: crypto.randomUUID(),
          prompt: '',
          description: '',
          display_rule: 'first_contact'
        });
        setSelectedFunctions([]);
        setOriginalFunctions([]);
        setSelectedFunctionId('');
      }
    }
  }, [mode, prompt, open, botId]);

  const loadPromptFunctions = async (promptId: string) => {
    const result = await fetchPromptFunctions(botId, promptId);
    if (result.success) {
      const functionIds = result.functions.map((fn: any) => fn.function_id);
      setSelectedFunctions(functionIds);
      setOriginalFunctions(functionIds);
    }
  };

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleAddFunction = () => {
    if (selectedFunctionId && !selectedFunctions.includes(selectedFunctionId)) {
      setSelectedFunctions([...selectedFunctions, selectedFunctionId]);
      setSelectedFunctionId('');
    }
  };

  const handleRemoveFunction = (functionId: string) => {
    setSelectedFunctions(selectedFunctions.filter(id => id !== functionId));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.id.trim() || !formData.prompt.trim()) {
      toast({
        title: "Erro",
        description: "ID e prompt são obrigatórios",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    
    try {
      let promptResult;
      const currentPromptId = formData.id.trim();
      
      // Check if prompt data changed
      const promptChanged = mode === 'create' || 
        prompt?.prompt !== formData.prompt.trim() ||
        prompt?.description !== formData.description.trim() ||
        prompt?.rule_display !== formData.display_rule.split('_').join(' ');
      
      // Only update prompt if data changed
      if (promptChanged) {
        if (mode === 'create') {
          promptResult = await createPrompt({
            bot_id: botId,
            id: currentPromptId,
            prompt: formData.prompt.trim(),
            description: formData.description.trim() || undefined,
            rule_display: formData.display_rule.split('_').join(' ')
          });
        } else {
          promptResult = await updatePrompt(botId, prompt!.id, {
            prompt: formData.prompt.trim(),
            description: formData.description.trim() || undefined,
            rule_display: formData.display_rule.split('_').join(' ')
          });
        }

        if (!promptResult.success) {
          toast({
            title: "Erro",
            description: promptResult.error || "Erro ao processar prompt",
            variant: "destructive",
          });
          setLoading(false);
          return;
        }
      }

      // Manage functions
      const functionsToAdd = selectedFunctions.filter(fn => !originalFunctions.includes(fn));
      const functionsToRemove = originalFunctions.filter(fn => !selectedFunctions.includes(fn));

      // Remove functions that were deleted
      for (const functionId of functionsToRemove) {
        const removeResult = await removeFunctionFromPrompt(botId, currentPromptId, functionId);
        if (!removeResult.success) {
          console.error('Error removing function:', removeResult.error);
        }
      }

      // Add new functions
      for (const functionId of functionsToAdd) {
        const addResult = await addFunctionToPrompt(botId, currentPromptId, functionId);
        if (!addResult.success) {
          console.error('Error adding function:', addResult.error);
        }
      }

      toast({
        title: "Sucesso",
        description: mode === 'create' ? "Prompt criado com sucesso!" : "Prompt atualizado com sucesso!",
      });
      
      onOpenChange(false);
      setFormData({
        id: '',
        prompt: '',
        description: '',
        display_rule: 'first_contact'
      });
      setSelectedFunctions([]);
      setOriginalFunctions([]);
      setSelectedFunctionId('');
      
      // Call onSuccess callback to refresh the list
      onSuccess?.();
    } catch (error) {
      console.error('Error submitting form:', error);
      toast({
        title: "Erro",
        description: "Erro inesperado",
        variant: "destructive",
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
            {mode === 'create' ? 'Criar Novo Prompt' : 'Editar Prompt'}
          </DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="id">ID do Prompt</Label>
            <Input
              id="id"
              value={formData.id}
              onChange={(e) => handleInputChange('id', e.target.value)}
              placeholder="ID gerado automaticamente"
              disabled={true}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Descrição</Label>
            <Input
              id="description"
              value={formData.description}
              onChange={(e) => handleInputChange('description', e.target.value)}
              placeholder="Descrição opcional do prompt"
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="display_rule">Regra Exibição</Label>
            <Select value={formData.display_rule} onValueChange={(value) => handleInputChange('display_rule', value)}>
              <SelectTrigger>
                <SelectValue placeholder="Selecione a regra de exibição" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="first_contact">Primeiro Contato</SelectItem>
                <SelectItem value="every_time">Sempre</SelectItem>
                <SelectItem value="email_not_informed">Email não informado</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="functions">Funções</Label>
            <div className="flex gap-2">
              <Select value={selectedFunctionId} onValueChange={setSelectedFunctionId}>
                <SelectTrigger className="flex-1">
                  <SelectValue placeholder="Selecione uma função" />
                </SelectTrigger>
                <SelectContent>
                  {functions
                    .filter(fn => !selectedFunctions.includes(fn.function_id))
                    .map((fn) => {
                      const isDisabled = fn.used === 'bot';
                      const displayText = fn.used === 'bot' 
                        ? `${fn.description || fn.function_id} (associado ao agente)`
                        : fn.description || fn.function_id;
                      
                      return (
                        <SelectItem 
                          key={fn.function_id} 
                          value={fn.function_id}
                          disabled={isDisabled}
                        >
                          {displayText}
                        </SelectItem>
                      );
                    })
                  }
                </SelectContent>
              </Select>
              <Button
                type="button"
                onClick={handleAddFunction}
                disabled={!selectedFunctionId}
                variant="outline"
              >
                Adicionar
              </Button>
            </div>
            
             {selectedFunctions.length > 0 && (
               <div className="flex flex-wrap gap-2 mt-2">
                 {selectedFunctions.map((functionId) => {
                   const functionObj = functions.find(fn => fn.function_id === functionId);
                   return (
                     <Badge key={functionId} variant="secondary" className="flex items-center gap-1">
                       {functionObj?.description || functionId}
                       <button
                         type="button"
                         onClick={() => handleRemoveFunction(functionId)}
                         className="ml-1 hover:bg-destructive/20 rounded-sm p-0.5"
                       >
                         <X size={12} />
                       </button>
                     </Badge>
                   );
                 })}
               </div>
             )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="prompt">Prompt</Label>
            <Textarea
              id="prompt"
              value={formData.prompt}
              onChange={(e) => handleInputChange('prompt', e.target.value)}
              placeholder="Digite o conteúdo do prompt"
              className="min-h-[200px]"
              required
            />
          </div>

          <div className="flex justify-end space-x-2 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Salvando...' : mode === 'create' ? 'Criar Prompt' : 'Atualizar Prompt'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default PromptForm;