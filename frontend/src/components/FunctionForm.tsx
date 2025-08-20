import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import { useFunctions, BotFunction } from '@/hooks/useFunctions';
import { useFunctionParameters, FunctionParameter } from '@/hooks/useFunctionParameters';
import { useIntegrations } from '@/hooks/useIntegrations';
import { useActions } from '@/hooks/useActions';
import { Plus, Edit, Trash2, X, Star, StarOff, Loader2 } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';

interface FunctionFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  botFunction?: BotFunction | null;
  mode: 'create' | 'edit';
  botId: string;
  onSuccess: () => void;
  bot?: any; // Bot info to check integration_type
}

const FunctionForm: React.FC<FunctionFormProps> = ({
  open,
  onOpenChange,
  botFunction,
  mode,
  botId,
  onSuccess,
  bot,
}) => {
  const { toast } = useToast();
  const { createFunction, updateFunction } = useFunctions();
  const { fetchParameters, createParameter, updateParameter, deleteParameter, parameters, createParametersBatch, deleteParametersBatch } = useFunctionParameters();
  const { integrations, fetchIntegrations } = useIntegrations();
  const { actions, fetchActions, loading: actionsLoading } = useActions();
  
  const [formData, setFormData] = useState({
    id: '',
    description: '',
    action: null,
  });
  const [loading, setLoading] = useState(false);
  const [parametersLoading, setParametersLoading] = useState(false);
  const [localParameters, setLocalParameters] = useState<FunctionParameter[]>([]);
  const [deletedParameterIds, setDeletedParameterIds] = useState<string[]>([]);
  const [originalParameters, setOriginalParameters] = useState<FunctionParameter[]>([]);
  const [modifiedParameters, setModifiedParameters] = useState<Set<string>>(new Set()); // Track modified parameters
  const [showParameterForm, setShowParameterForm] = useState(false);
  const [editingParameterId, setEditingParameterId] = useState<string | null>(null);
  const [parameterForm, setParameterForm] = useState({
    parameter_id: '',
    description: '',
    type: 'string' as 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array',
    permited_values: '',
    default_value: '',
    format: '' as '' | 'email' | 'uri' | 'date' | 'date-time',
  });

  // Estados para o sistema de tags
  const [enablePermittedValues, setEnablePermittedValues] = useState(false);
  const [permittedTags, setPermittedTags] = useState<Array<{value: string, isDefault: boolean}>>([]);
  const [tagInput, setTagInput] = useState('');

  // Buscar integrações quando o componente for montado
  useEffect(() => {
    fetchIntegrations();
  }, []);

  // Determinar o tipo de integração do bot
  const botIntegrationType = React.useMemo(() => {
    if (!bot?.integration_id || !integrations.length) return null;
    const integration = integrations.find(i => i.id === bot.integration_id);
    return integration?.integration_type || null;
  }, [bot?.integration_id, integrations]);

  // Buscar ações quando o tipo de integração do bot for determinado
  useEffect(() => {
    if (open) {
      fetchActions(botIntegrationType);
    }
  }, [open, botIntegrationType, fetchActions]);

  useEffect(() => {
    if (mode === 'edit' && botFunction) {
      setFormData({
        id: botFunction.function_id,
        description: botFunction.description || '',
        action: botFunction.action || null,
      });
      // Load parameters for existing function
      loadParameters(botFunction.function_id);
    } else {
      setFormData({
        id: '',
        description: '',
        action: null,
      });
      setLocalParameters([]);
      setOriginalParameters([]);
      setModifiedParameters(new Set());
      setDeletedParameterIds([]);
    }
    setShowParameterForm(false);
    setEditingParameterId(null);
    resetParameterForm();
  }, [mode, botFunction, open]);


  // Update local parameters when parameters from hook change
  useEffect(() => {
    if (mode === 'edit' && parameters.length > 0) {
      setLocalParameters(parameters);
      setOriginalParameters(parameters);
    }
  }, [parameters, mode]);

  const loadParameters = async (functionId: string) => {
    try {
      setParametersLoading(true);
      await fetchParameters(botId, functionId);
    } catch (error) {
      console.error('Error loading parameters:', error);
    } finally {
      setParametersLoading(false);
    }
  };

  const resetParameterForm = () => {
    setParameterForm({
      parameter_id: '',
      description: '',
      type: 'string',
      permited_values: '',
      default_value: '',
      format: '',
    });
    setEnablePermittedValues(false);
    setPermittedTags([]);
    setTagInput('');
  };

  // Funções para gerenciar tags
  const addTag = () => {
    const value = tagInput.trim();
    if (value && !permittedTags.some(tag => tag.value === value)) {
      const isFirst = permittedTags.length === 0;
      setPermittedTags(prev => [...prev, { value, isDefault: isFirst }]);
      setTagInput('');
    }
  };

  const removeTag = (valueToRemove: string) => {
    setPermittedTags(prev => {
      const filtered = prev.filter(tag => tag.value !== valueToRemove);
      // Se o valor removido era o default e ainda há outros valores, define o primeiro como default
      const removedWasDefault = prev.find(tag => tag.value === valueToRemove)?.isDefault;
      if (removedWasDefault && filtered.length > 0) {
        filtered[0].isDefault = true;
      }
      return filtered;
    });
  };

  const setTagAsDefault = (value: string) => {
    setPermittedTags(prev => prev.map(tag => ({
      ...tag,
      isDefault: tag.value === value
    })));
  };

  const handleTagInputKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addTag();
    }
  };


  const handleAddParameter = () => {
    setEditingParameterId(null);
    resetParameterForm();
    setShowParameterForm(true);
  };

  const handleEditParameter = (parameter: FunctionParameter) => {
    setParameterForm({
      parameter_id: parameter.parameter_id,
      description: parameter.description || '',
      type: parameter.type,
      permited_values: parameter.permited_values || '',
      default_value: parameter.default_value || '',
      format: parameter.format || '',
    });

    // Carregar tags dos valores permitidos se existirem
    if (parameter.permited_values) {
      try {
        const parsedValues = JSON.parse(parameter.permited_values);
        if (Array.isArray(parsedValues)) {
          const tags = parsedValues.map((value: string) => ({
            value,
            isDefault: value === parameter.default_value
          }));
          setPermittedTags(tags);
          setEnablePermittedValues(true);
        }
      } catch (error) {
        console.log('Valores permitidos não são um JSON válido');
      }
    }

    setEditingParameterId(parameter.parameter_id);
    setShowParameterForm(true);
  };

  const handleCancelParameter = () => {
    setShowParameterForm(false);
    setEditingParameterId(null);
    resetParameterForm();
  };

  const handleSaveParameter = async () => {
    // Validar se valores permitidos foram configurados corretamente
    if (enablePermittedValues && permittedTags.length === 0) {
      toast({
        title: "Erro",
        description: "Quando usar valores permitidos, deve informar ao menos 1 valor",
        variant: "destructive",
      });
      return;
    }
    
    // Converter tags para JSON e encontrar valor padrão
    let permittedValuesJson = undefined;
    let defaultValue = undefined;
    
    if (enablePermittedValues && permittedTags.length > 0) {
      const tagValues = permittedTags.map(tag => tag.value);
      permittedValuesJson = JSON.stringify(tagValues);
      const defaultTag = permittedTags.find(tag => tag.isDefault);
      defaultValue = defaultTag?.value;
    }

    // Sempre trabalhar apenas com estado local durante edição
    const newParameter: FunctionParameter = {
      function_id: formData.id,
      parameter_id: parameterForm.parameter_id,
      description: parameterForm.description,
      type: parameterForm.type,
      permited_values: permittedValuesJson,
      default_value: defaultValue,
      format: parameterForm.format || undefined,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    if (editingParameterId) {
      // Atualizar parâmetro existente no estado local
      setLocalParameters(prev => prev.map(p => 
        p.parameter_id === editingParameterId ? newParameter : p
      ));
      
      // Verificar se este parâmetro existia originalmente (por qualquer parameter_id original)
      const originalParam = originalParameters.find(p => p.parameter_id === editingParameterId);
      if (originalParam) {
        // Se o parameter_id mudou, precisamos:
        // 1. Marcar o parameter_id antigo para deletar
        // 2. Marcar o novo parameter como modificado (que será tratado como novo)
        if (originalParam.parameter_id !== newParameter.parameter_id) {
          setDeletedParameterIds(prev => [...prev, editingParameterId]);
          // Não marcar como modificado - deixar ser tratado como novo
        } else {
          // Se apenas outros campos mudaram, marcar como modificado
          setModifiedParameters(prev => new Set([...prev, editingParameterId]));
        }
      }
    } else {
      // Adicionar novo parâmetro ao estado local
      setLocalParameters(prev => [...prev, newParameter]);
    }

    toast({
      title: "Sucesso", 
      description: editingParameterId ? "Parâmetro atualizado localmente!" : "Parâmetro adicionado localmente!",
    });
    
    setShowParameterForm(false);
    setEditingParameterId(null);
    resetParameterForm();
  };

  const handleDeleteParameter = async (parameterId: string) => {
    // Sempre trabalhar apenas com estado local durante edição
    const isExistingParameter = originalParameters.some(p => p.parameter_id === parameterId);
    
    if (isExistingParameter) {
      // Se é um parâmetro que existia originalmente, adicionar à lista de deletados
      setDeletedParameterIds(prev => [...prev, parameterId]);
    }
    
    // Remover do estado local
    setLocalParameters(prev => prev.filter(p => p.parameter_id !== parameterId));
    
    // Remover da lista de modificados se estava lá
    setModifiedParameters(prev => {
      const newSet = new Set(prev);
      newSet.delete(parameterId);
      return newSet;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Validar se há pelo menos 1 parâmetro
      if (localParameters.length === 0) {
        toast({
          title: "Erro",
          description: "É necessário informar pelo menos 1 parâmetro para a função.",
          variant: "destructive",
        });
        return;
      }

      let result;
      
      if (mode === 'create') {
        // 1. Primeiro criar a função
        const createData: any = {
          function_id: formData.id,
          description: formData.description || undefined,
        };
        
        // Add action field if there's an action selected
        if (formData.action && formData.action !== 'none') {
          createData.action = formData.action;
        }
        
        result = await createFunction(botId, createData);
        
        if (!result.success) {
          toast({
            title: "Erro",
            description: result.error,
            variant: "destructive",
          });
          return;
        }

        // 2. Se a função foi criada com sucesso e temos parâmetros locais, criar todos em batch
        if (localParameters.length > 0) {
          console.log('Creating parameters for function:', formData.id);
          console.log('Local parameters:', localParameters);
          
          const parametersData = localParameters.map(param => ({
            parameter_id: param.parameter_id,
            description: param.description,
            type: param.type,
            permited_values: param.permited_values,
            default_value: param.default_value,
            format: param.format,
          }));

          console.log('Parameters data to send:', parametersData);
          const parametersResult = await createParametersBatch(botId, formData.id, parametersData);
          
          if (!parametersResult.success) {
            toast({
              title: "Aviso",
              description: "Função criada mas houve erro ao salvar parâmetros: " + parametersResult.error,
              variant: "destructive",
            });
          }
        }
      } else {
        // Modo de edição - 2 operações separadas
        
        // 1. Atualizar função (apenas description) - só se realmente mudou
        console.log('Edit mode - checking if function needs update');
        console.log('Original function:', botFunction);
        console.log('Current form data:', formData);
        
        const cleanDescription = formData.description?.trim();
        const originalDescription = botFunction?.description?.trim();
        
        console.log('Clean description:', cleanDescription);
        console.log('Original description:', originalDescription);
        
        const originalAction = botFunction?.action || '';
        const actionChanged = formData.action !== originalAction;
        
        if (cleanDescription !== originalDescription || actionChanged) {
          console.log('Function data changed, updating...');
          const updateData: any = {
            description: cleanDescription || undefined,
          };
          
          // Add action field if there are actions available
          if (actions.length > 0) {
            updateData.action = formData.action === 'none' ? null : formData.action;
          }
          
          result = await updateFunction(botId, formData.id, updateData);
          
          console.log('Update function result:', result);

          if (!result.success) {
            toast({
              title: "Erro",
              description: result.error,
              variant: "destructive",
            });
            return;
          }
        } else {
          console.log('Function data unchanged, skipping update');
          result = { success: true }; // Simulate success since no update needed
        }

        // 2. Excluir parâmetros removidos (apenas os que realmente existem no servidor)
        const existingDeletedIds = deletedParameterIds.filter(id => 
          originalParameters.some(p => p.parameter_id === id)
        );
        
        console.log('Deleted parameter IDs:', deletedParameterIds);
        console.log('Existing deleted IDs to send:', existingDeletedIds);
        
        if (existingDeletedIds.length > 0) {
          console.log('Deleting parameters:', existingDeletedIds);
          const deleteResult = await deleteParametersBatch(botId, formData.id, existingDeletedIds);
          console.log('Delete parameters result:', deleteResult);
          if (!deleteResult.success) {
            toast({
              title: "Aviso",
              description: "Função atualizada mas houve erro ao excluir parâmetros: " + deleteResult.error,
              variant: "destructive",
            });
          }
        }

        // 3. Atualizar parâmetros modificados
        const modifiedParametersData = localParameters.filter(param => 
          modifiedParameters.has(param.parameter_id)
        );
        
        console.log('Modified parameters:', modifiedParametersData);
        for (const param of modifiedParametersData) {
          // Remover campos null/undefined do payload
          const updatePayload: any = {
            description: param.description,
            type: param.type,
          };
          
          if (param.permited_values !== null && param.permited_values !== undefined) {
            updatePayload.permited_values = param.permited_values;
          }
          if (param.default_value !== null && param.default_value !== undefined) {
            updatePayload.default_value = param.default_value;
          }
          if (param.format !== null && param.format !== undefined) {
            updatePayload.format = param.format;
          }
          
          console.log('Update payload for parameter:', param.parameter_id, updatePayload);
          
          const updateResult = await updateParameter(botId, formData.id, param.parameter_id, updatePayload);
          
          if (!updateResult.success) {
            toast({
              title: "Aviso",
              description: `Erro ao atualizar parâmetro ${param.parameter_id}: ${updateResult.error}`,
              variant: "destructive",
            });
          }
        }

        // 4. Criar novos parâmetros em batch (apenas os que realmente são novos)
        const newParameters = localParameters.filter(param => {
          // Um parâmetro é considerado novo se:
          // 1. Não estava na lista original de parâmetros
          // 2. E não foi marcado como modificado (que significa que era uma alteração de um existente)
          const wasOriginal = originalParameters.some(orig => orig.parameter_id === param.parameter_id);
          const wasModified = modifiedParameters.has(param.parameter_id);
          return !wasOriginal && !wasModified;
        });
        
        console.log('New parameters:', newParameters);
        if (newParameters.length > 0) {
          const parametersData = newParameters.map(param => ({
            parameter_id: param.parameter_id,
            description: param.description,
            type: param.type,
            permited_values: param.permited_values,
            default_value: param.default_value,
            format: param.format,
          }));

          const createResult = await createParametersBatch(botId, formData.id, parametersData);
          if (!createResult.success) {
            toast({
              title: "Aviso", 
              description: "Função atualizada mas houve erro ao criar novos parâmetros: " + createResult.error,
              variant: "destructive",
            });
          }
        }
      }

      if (result.success) {
        // Limpar estados após sucesso
        setDeletedParameterIds([]);
        setModifiedParameters(new Set());
        
        toast({
          title: "Sucesso",
          description: mode === 'create' ? "Função criada com sucesso!" : "Função atualizada com sucesso!",
        });
        onOpenChange(false);
        onSuccess();
      } else {
        toast({
          title: "Erro",
          description: result.error,
          variant: "destructive",
        });
      }
    } catch (error) {
      toast({
        title: "Erro",
        description: "Erro inesperado ao salvar função",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const displayParameters = mode === 'edit' ? localParameters : localParameters;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>
            {mode === 'create' ? 'Nova Função' : 'Editar Função'}
          </DialogTitle>
        </DialogHeader>
        
        <div className="flex-1 overflow-y-auto">
          <form onSubmit={handleSubmit} className="space-y-6 p-1">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="id">ID da Função</Label>
              <Input
                id="id"
                value={formData.id}
                onChange={(e) => setFormData(prev => ({ ...prev, id: e.target.value }))}
                disabled={mode === 'edit'}
                required
                placeholder="ex: buscar_produto"
              />
            </div>


            <div className="space-y-2">
              <Label htmlFor="description">Descrição</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Descreva o objetivo desta função..."
                rows={3}
              />
            </div>

            {/* Ação da Função - mostrar se há ações disponíveis */}
            {actions.length > 0 && (
              <div className="space-y-2">
                <Label htmlFor="action">Ação da Função</Label>
                <Select 
                  value={formData.action || "none"} 
                  onValueChange={(value) => setFormData(prev => ({ ...prev, action: value === "none" ? null : value }))}
                  disabled={actionsLoading}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={actionsLoading ? "Carregando..." : "Selecione uma ação"} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">
                      Nenhuma
                    </SelectItem>
                    {actions.map((action) => (
                      <SelectItem key={action.id} value={action.action}>
                        {action.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

          </div>

          <Separator />

          {/* Parameters Section */}
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Parâmetros da Função</CardTitle>
                <Button type="button" onClick={handleAddParameter} className="flex items-center gap-2">
                  <Plus className="h-4 w-4" />
                  Incluir Parâmetro
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Parameter Form */}
              {showParameterForm && (
                <Card className="border-primary/20 bg-primary/5">
                  <CardHeader>
                    <div className="flex justify-between items-center">
                      <CardTitle className="text-sm">
                        {editingParameterId ? 'Editar Parâmetro' : 'Novo Parâmetro'}
                      </CardTitle>
                      <Button type="button" variant="ghost" size="sm" onClick={handleCancelParameter}>
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label>ID do Parâmetro</Label>
                      <Input
                        value={parameterForm.parameter_id}
                        onChange={(e) => setParameterForm(prev => ({ ...prev, parameter_id: e.target.value }))}
                        required
                        placeholder="ex: categoria"
                        autoFocus
                      />
                    </div>

                     <div className="space-y-2">
                       <Label>Descrição</Label>
                       <Textarea
                         value={parameterForm.description}
                         onChange={(e) => setParameterForm(prev => ({ ...prev, description: e.target.value }))}
                         placeholder="Descreva o objetivo deste parâmetro..."
                         rows={2}
                       />
                     </div>

                     <div className="grid grid-cols-2 gap-4">
                       <div className="space-y-2">
                         <Label>Tipo</Label>
                         <Select 
                           value={parameterForm.type} 
                           onValueChange={(value) => setParameterForm(prev => ({ ...prev, type: value as any }))}
                         >
                           <SelectTrigger>
                             <SelectValue />
                           </SelectTrigger>
                           <SelectContent>
                             <SelectItem value="string">String</SelectItem>
                             <SelectItem value="number">Number</SelectItem>
                             <SelectItem value="integer">Integer</SelectItem>
                             <SelectItem value="boolean">Boolean</SelectItem>
                             <SelectItem value="object">Object</SelectItem>
                             <SelectItem value="array">Array</SelectItem>
                           </SelectContent>
                         </Select>
                       </div>
                       <div className="space-y-2">
                         <Label>Formato</Label>
                         <Select 
                           value={parameterForm.format || "none"} 
                           onValueChange={(value) => setParameterForm(prev => ({ 
                             ...prev, 
                             format: value === "none" ? "" : value as any 
                           }))}
                         >
                           <SelectTrigger>
                             <SelectValue placeholder="Nenhum" />
                           </SelectTrigger>
                           <SelectContent>
                             <SelectItem value="none">Nenhum</SelectItem>
                             <SelectItem value="email">Email</SelectItem>
                             <SelectItem value="uri">URI</SelectItem>
                             <SelectItem value="date">Date</SelectItem>
                             <SelectItem value="date-time">Date-Time</SelectItem>
                           </SelectContent>
                         </Select>
                       </div>
                     </div>

                    {/* Sistema de Tags para Valores Permitidos */}
                    <div className="space-y-4">
                      <div className="flex items-center space-x-2">
                        <Checkbox 
                          id="enablePermittedValues"
                          checked={enablePermittedValues}
                          onCheckedChange={(checked) => {
                            setEnablePermittedValues(!!checked);
                            if (!checked) {
                              setPermittedTags([]);
                            }
                          }}
                        />
                        <Label htmlFor="enablePermittedValues">
                          Configurar valores de retorno permitidos
                        </Label>
                      </div>

                      {enablePermittedValues && (
                        <div className="space-y-3">
                          <div className="flex gap-2">
                            <Input
                              value={tagInput}
                              onChange={(e) => setTagInput(e.target.value)}
                              onKeyDown={handleTagInputKeyPress}
                              placeholder="Digite um valor e pressione Enter"
                              className="flex-1"
                            />
                            <Button 
                              type="button" 
                              variant="outline" 
                              onClick={addTag}
                              disabled={!tagInput.trim()}
                            >
                              Adicionar
                            </Button>
                          </div>

                          {permittedTags.length > 0 && (
                            <div className="space-y-2">
                              <Label className="text-sm font-medium">Valores configurados:</Label>
                              <div className="flex flex-wrap gap-2">
                                {permittedTags.map((tag) => (
                                  <div 
                                    key={tag.value} 
                                    className="flex items-center gap-1 bg-secondary text-secondary-foreground px-2 py-1 rounded-md text-sm"
                                  >
                                    <span>{tag.value}</span>
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="sm"
                                      className="h-4 w-4 p-0 hover:bg-secondary-foreground/10"
                                      onClick={() => setTagAsDefault(tag.value)}
                                      title={tag.isDefault ? "Valor padrão atual" : "Definir como padrão"}
                                    >
                                      {tag.isDefault ? (
                                        <Star className="h-3 w-3 fill-current text-yellow-500" />
                                      ) : (
                                        <StarOff className="h-3 w-3" />
                                      )}
                                    </Button>
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="sm"
                                      className="h-4 w-4 p-0 hover:bg-destructive/10 text-destructive"
                                      onClick={() => removeTag(tag.value)}
                                      title="Remover valor"
                                    >
                                      <X className="h-3 w-3" />
                                    </Button>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="flex gap-2">
                      <Button type="button" variant="outline" onClick={handleCancelParameter}>
                        Cancelar
                      </Button>
                      <Button type="button" onClick={handleSaveParameter}>
                        Salvar Parâmetro
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Parameters List */}
              {parametersLoading ? (
                <div className="flex items-center justify-center py-8 space-x-2">
                  <Loader2 className="w-5 h-5 animate-spin text-primary" />
                  <span className="text-sm text-muted-foreground">Carregando parâmetros...</span>
                </div>
              ) : displayParameters.length > 0 ? (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">Parâmetros Cadastrados</h4>
                  {displayParameters.map((param) => (
                    <div key={param.parameter_id} className="p-3 border rounded-lg bg-muted/30 animate-fade-in">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                           <div className="flex items-center gap-2">
                             <h5 className="font-medium">{param.parameter_id}</h5>
                             <Badge variant="secondary">{param.type}</Badge>
                             {param.format && (
                               <Badge variant="outline">{param.format}</Badge>
                             )}
                           </div>
                           {param.description && (
                             <p className="text-sm text-muted-foreground mt-1">
                               {param.description}
                             </p>
                           )}
                           {param.default_value && (
                             <p className="text-sm text-muted-foreground mt-1">
                               Padrão: {param.default_value}
                             </p>
                           )}
                           {param.permited_values && (
                             <p className="text-xs text-muted-foreground mt-1">
                               Valores: {param.permited_values}
                             </p>
                           )}
                        </div>
                        <div className="flex gap-1">
                          <Button 
                            type="button" 
                            variant="ghost" 
                            size="sm"
                            onClick={() => handleEditParameter(param)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button 
                            type="button" 
                            variant="ghost" 
                            size="sm"
                            onClick={() => handleDeleteParameter(param.parameter_id)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : !showParameterForm ? (
                <div className="text-center py-8 text-muted-foreground">
                  <p>Nenhum parâmetro cadastrado</p>
                  <p className="text-sm">Clique em "Incluir Parâmetro" para adicionar</p>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <div className="flex gap-2 pt-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Salvando...' : mode === 'create' ? 'Criar' : 'Salvar'}
            </Button>
          </div>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default FunctionForm;