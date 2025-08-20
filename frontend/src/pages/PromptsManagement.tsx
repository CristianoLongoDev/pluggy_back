import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { useBots } from '@/hooks/useBots';
import { usePrompts, Prompt } from '@/hooks/usePrompts';
import PromptForm from '@/components/PromptForm';
import PageHeader from '@/components/PageHeader';
import { Plus, MoreHorizontal, Edit, Trash2 } from 'lucide-react';

const PromptsManagement = () => {
  const { toast } = useToast();
  const { bots, fetchBots, loading: botsLoading } = useBots();
  const { prompts, loading: promptsLoading, error, fetchPrompts, deletePrompt } = usePrompts();
  
  const [selectedBotId, setSelectedBotId] = useState<string>('');
  const [formOpen, setFormOpen] = useState(false);
  const [selectedPrompt, setSelectedPrompt] = useState<Prompt | null>(null);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [promptToDelete, setPromptToDelete] = useState<Prompt | null>(null);

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
      fetchPrompts(selectedBotId);
    }
  }, [selectedBotId]);

  const handleBotSelect = (botId: string) => {
    setSelectedBotId(botId);
  };

  const handleCreate = () => {
    if (!selectedBotId) {
      toast({
        title: "Erro",
        description: "Selecione um bot primeiro",
        variant: "destructive",
      });
      return;
    }
    setSelectedPrompt(null);
    setFormMode('create');
    setFormOpen(true);
  };

  const handleEdit = (prompt: Prompt) => {
    setSelectedPrompt(prompt);
    setFormMode('edit');
    setFormOpen(true);
  };

  const handleDeleteClick = (prompt: Prompt) => {
    setPromptToDelete(prompt);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!promptToDelete) return;

    const result = await deletePrompt(promptToDelete.bot_id, promptToDelete.id);
    
    if (result.success) {
      toast({
        title: "Sucesso",
        description: "Prompt excluído com sucesso!",
      });
      // Refresh the list after successful deletion
      fetchPrompts(selectedBotId);
    } else {
      toast({
        title: "Erro",
        description: result.error || "Erro ao excluir prompt",
        variant: "destructive",
      });
    }
    
    setDeleteDialogOpen(false);
    setPromptToDelete(null);
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
        title="Gerenciar Eventos" 
        description="Configure e gerencie os eventos personalizados para seus bots de atendimento"
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
              <CardTitle>Eventos do Bot</CardTitle>
              {prompts.length > 0 && (
                <Button onClick={handleCreate} className="flex items-center gap-2">
                  <Plus className="h-4 w-4" />
                  Novo Evento
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {promptsLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : error ? (
              <div className="text-center py-8">
                <p className="text-muted-foreground mb-4">Erro ao carregar prompts: {error}</p>
                <Button onClick={() => fetchPrompts(selectedBotId)} variant="outline">
                  Tentar novamente
                </Button>
              </div>
            ) : prompts.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-muted-foreground mb-4">Nenhum prompt encontrado para este bot.</p>
                <Button onClick={handleCreate}>
                  + Novo Evento
                </Button>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="font-medium">ID</TableHead>
                    <TableHead className="font-medium">Descrição</TableHead>
                    <TableHead className="font-medium">Regra Exibição</TableHead>
                    <TableHead className="font-medium">Atualizado em</TableHead>
                    <TableHead className="w-[100px] font-medium">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {prompts.map((prompt) => (
                    <TableRow key={prompt.id}>
                      <TableCell className="font-mono text-sm">
                        {prompt.id ? prompt.id.substring(0, 8) + '...' : '-'}
                      </TableCell>
                      <TableCell className="font-medium">{prompt.description || '-'}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{prompt.rule_display || '-'}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {prompt.updated_at ? new Date(prompt.updated_at).toLocaleDateString('pt-BR') : '-'}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleEdit(prompt)}>
                              <Edit className="mr-2 h-4 w-4" />
                              Editar
                            </DropdownMenuItem>
                            <DropdownMenuItem 
                              onClick={() => handleDeleteClick(prompt)}
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

      <PromptForm
        open={formOpen}
        onOpenChange={setFormOpen}
        prompt={selectedPrompt}
        mode={formMode}
        botId={selectedBotId}
        onSuccess={() => fetchPrompts(selectedBotId)}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar exclusão</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja excluir o prompt "{promptToDelete?.id}"? 
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

export default PromptsManagement;