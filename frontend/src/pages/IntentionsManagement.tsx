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
import { useIntents, Intent } from '@/hooks/useIntents';
import IntentForm from '@/components/IntentForm';
import PageHeader from '@/components/PageHeader';
import { Plus, MoreHorizontal, Edit, Trash2 } from 'lucide-react';

const IntentionsManagement = () => {
  const { toast } = useToast();
  const { bots, fetchBots, loading: botsLoading } = useBots();
  const { intents, loading: intentsLoading, error, fetchIntents, deleteIntent } = useIntents();
  
  const [selectedBotId, setSelectedBotId] = useState<string>('');
  const [formOpen, setFormOpen] = useState(false);
  const [selectedIntent, setSelectedIntent] = useState<Intent | null>(null);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [intentToDelete, setIntentToDelete] = useState<Intent | null>(null);

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
      fetchIntents(selectedBotId);
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
    setSelectedIntent(null);
    setFormMode('create');
    setFormOpen(true);
  };

  const handleEdit = (intent: Intent) => {
    setSelectedIntent(intent);
    setFormMode('edit');
    setFormOpen(true);
  };

  const handleDeleteClick = (intent: Intent) => {
    setIntentToDelete(intent);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!intentToDelete) return;

    const result = await deleteIntent(intentToDelete.bot_id, intentToDelete.id);
    
    if (result.success) {
      toast({
        title: "Sucesso",
        description: "Intenção excluída com sucesso!",
      });
      // Refresh the list after successful deletion
      fetchIntents(selectedBotId);
    } else {
      toast({
        title: "Erro",
        description: result.error || "Erro ao excluir intenção",
        variant: "destructive",
      });
    }
    
    setDeleteDialogOpen(false);
    setIntentToDelete(null);
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
        title="Gerenciar Intenções" 
        description="Configure e gerencie as intenções personalizadas para seus bots de atendimento"
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
              <CardTitle>Intenções do Bot</CardTitle>
              {intents.length > 0 && (
                <Button onClick={handleCreate} className="flex items-center gap-2">
                  <Plus className="h-4 w-4" />
                  Nova Intenção
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {intentsLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : error ? (
              <div className="text-center py-8">
                <p className="text-muted-foreground mb-4">Erro ao carregar intenções: {error}</p>
                <Button onClick={() => fetchIntents(selectedBotId)} variant="outline">
                  Tentar novamente
                </Button>
              </div>
            ) : intents.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-muted-foreground mb-4">Nenhuma intenção encontrada para este bot.</p>
                <Button onClick={handleCreate}>
                  + Nova Intenção
                </Button>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="font-medium">ID</TableHead>
                    <TableHead className="font-medium">Nome</TableHead>
                    <TableHead className="font-medium">Descrição</TableHead>
                    <TableHead className="font-medium">Status</TableHead>
                    <TableHead className="font-medium">Função</TableHead>
                    <TableHead className="w-[100px] font-medium">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {intents.map((intent) => (
                    <TableRow key={intent.id}>
                      <TableCell className="font-mono text-sm">
                        {intent.id ? intent.id.substring(0, 8) + '...' : '-'}
                      </TableCell>
                      <TableCell className="font-medium">{intent.name || '-'}</TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                        {intent.intention || '-'}
                      </TableCell>
                      <TableCell>
                        <Badge variant={intent.active ? "default" : "secondary"}>
                          {intent.active ? 'Ativa' : 'Inativa'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {intent.function_id || '-'}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleEdit(intent)}>
                              <Edit className="mr-2 h-4 w-4" />
                              Editar
                            </DropdownMenuItem>
                            <DropdownMenuItem 
                              onClick={() => handleDeleteClick(intent)}
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

      <IntentForm
        open={formOpen}
        onOpenChange={setFormOpen}
        intent={selectedIntent}
        mode={formMode}
        botId={selectedBotId}
        onSuccess={() => fetchIntents(selectedBotId)}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar exclusão</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja excluir a intenção "{intentToDelete?.name}"? 
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

export default IntentionsManagement;