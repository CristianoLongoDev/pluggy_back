import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { useBots } from '@/hooks/useBots';
import { useFunctions, BotFunction } from '@/hooks/useFunctions';
import FunctionForm from '@/components/FunctionForm';
import PageHeader from '@/components/PageHeader';
import { Plus, MoreHorizontal, Edit, Trash2 } from 'lucide-react';

const FunctionsManagement = () => {
  const { toast } = useToast();
  const { bots, fetchBots, loading: botsLoading } = useBots();
  const { functions, loading: functionsLoading, error, fetchFunctions, deleteFunction } = useFunctions();
  
  const [selectedBotId, setSelectedBotId] = useState<string>('');
  const [functionFormOpen, setFunctionFormOpen] = useState(false);
  const [selectedFunction, setSelectedFunction] = useState<BotFunction | null>(null);
  const [functionFormMode, setFunctionFormMode] = useState<'create' | 'edit'>('create');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<BotFunction | null>(null);

  useEffect(() => {
    fetchBots();
  }, []);

  // Auto-select first bot when bots are loaded
  useEffect(() => {
    if (bots.length > 0 && !selectedBotId) {
      setSelectedBotId(bots[0].id);
    }
  }, [bots, selectedBotId]);

  useEffect(() => {
    if (selectedBotId) {
      fetchFunctions(selectedBotId);
    }
  }, [selectedBotId]);

  const handleBotSelect = (botId: string) => {
    setSelectedBotId(botId);
  };

  const handleCreateFunction = () => {
    if (!selectedBotId) {
      toast({
        title: "Erro",
        description: "Selecione um bot primeiro",
        variant: "destructive",
      });
      return;
    }
    setSelectedFunction(null);
    setFunctionFormMode('create');
    setFunctionFormOpen(true);
  };

  const handleEditFunction = (func: BotFunction) => {
    setSelectedFunction(func);
    setFunctionFormMode('edit');
    setFunctionFormOpen(true);
  };

  const handleDeleteClick = (item: BotFunction) => {
    setItemToDelete(item);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!itemToDelete) return;

    const result = await deleteFunction(selectedBotId, itemToDelete.function_id);
    
    if (result.success) {
      toast({
        title: "Sucesso",
        description: "Função excluída com sucesso!",
      });
      fetchFunctions(selectedBotId);
    } else {
      toast({
        title: "Erro",
        description: result.error || "Erro ao excluir função",
        variant: "destructive",
      });
    }
    
    setDeleteDialogOpen(false);
    setItemToDelete(null);
  };

  if (botsLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader 
        title="Gerenciar Funções" 
        description="Configure e gerencie as funções disponíveis para seus bots de atendimento" 
      />

      <Card>
        <CardHeader>
          <CardTitle>Seleção de Bot</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="w-full max-w-sm">
            <Select value={selectedBotId} onValueChange={handleBotSelect}>
              <SelectTrigger>
                <SelectValue placeholder="Selecione um bot" />
              </SelectTrigger>
              <SelectContent>
                {bots.map((bot) => (
                  <SelectItem key={bot.id} value={bot.id}>
                    {bot.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {selectedBotId && (
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <CardTitle>Funções do Bot</CardTitle>
              {functions.length > 0 && (
                <Button onClick={handleCreateFunction} className="flex items-center gap-2">
                  <Plus className="h-4 w-4" />
                  Nova Função
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {functionsLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : error ? (
              <div className="text-center py-8">
                <p className="text-muted-foreground mb-4">Erro ao carregar funções: {error}</p>
                <Button onClick={() => fetchFunctions(selectedBotId)} variant="outline">
                  Tentar novamente
                </Button>
              </div>
            ) : functions.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-muted-foreground mb-4">Nenhuma função encontrada para este bot.</p>
                <Button onClick={handleCreateFunction}>
                  Criar primeira função
                </Button>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="font-medium">ID</TableHead>
                    <TableHead className="font-medium">Descrição</TableHead>
                    <TableHead className="font-medium">Atualizado em</TableHead>
                    <TableHead className="w-[100px] font-medium">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {functions.map((func) => (
                    <TableRow key={func.function_id}>
                      <TableCell className="font-mono text-sm">
                        {func.function_id ? func.function_id.substring(0, 20) + (func.function_id.length > 20 ? '...' : '') : '-'}
                      </TableCell>
                      <TableCell className="font-medium">{func.description || '-'}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {func.updated_at ? new Date(func.updated_at).toLocaleDateString('pt-BR') : '-'}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleEditFunction(func)}>
                              <Edit className="mr-2 h-4 w-4" />
                              Editar
                            </DropdownMenuItem>
                            <DropdownMenuItem 
                              onClick={() => handleDeleteClick(func)}
                              className="text-destructive"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Excluir
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      <FunctionForm
        open={functionFormOpen}
        onOpenChange={setFunctionFormOpen}
        botFunction={selectedFunction}
        mode={functionFormMode}
        botId={selectedBotId}
        onSuccess={() => fetchFunctions(selectedBotId)}
        bot={bots.find(bot => bot.id === selectedBotId)}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar exclusão</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja excluir esta função? 
              Todos os parâmetros da função também serão excluídos.
              Esta ação não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirm}>
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default FunctionsManagement;