import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { MoreHorizontal, Plus, Edit, Trash2, Bot as BotIcon } from 'lucide-react';
import { useBots, Bot } from '@/hooks/useBots';
import { useIntegrations } from '@/hooks/useIntegrations';
import { BotForm } from './BotForm';
import { useToast } from '@/hooks/use-toast';
import PageHeader from '@/components/PageHeader';

export const BotList: React.FC = () => {
  const { bots, loading, error, fetchBots, createBot, updateBot, deleteBot } = useBots();
  const { integrations, fetchIntegrations } = useIntegrations();
  const { toast } = useToast();
  
  const [formOpen, setFormOpen] = useState(false);
  const [selectedBot, setSelectedBot] = useState<Bot | null>(null);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [botToDelete, setBotToDelete] = useState<Bot | null>(null);

  React.useEffect(() => {
    console.log('BotList - Component mounted, calling fetchBots');
    fetchBots();
    fetchIntegrations();
  }, []);

  const handleCreate = () => {
    setSelectedBot(null);
    setFormMode('create');
    setFormOpen(true);
  };

  const handleEdit = (bot: Bot) => {
    setSelectedBot(bot);
    setFormMode('edit');
    setFormOpen(true);
  };

  const handleDeleteClick = (bot: Bot) => {
    setBotToDelete(bot);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!botToDelete) return;
    
    const result = await deleteBot(botToDelete.id);
    if (result.success) {
      toast({
        title: "Sucesso",
        description: "Bot excluído com sucesso"
      });
    } else {
      toast({
        title: "Erro",
        description: "Erro ao excluir bot",
        variant: "destructive"
      });
    }
    
    setDeleteDialogOpen(false);
    setBotToDelete(null);
  };

  const handleFormSubmit = async (botData: any) => {
    if (formMode === 'edit' && selectedBot) {
      return await updateBot(selectedBot.id, botData);
    } else {
      return await createBot(botData);
    }
  };

  const getIntegrationInfo = (integrationId: string) => {
    if (!integrationId) {
      return { name: 'Nenhuma integração', logo: null };
    }
    
    const integration = integrations.find(i => i.id === integrationId);
    return {
      name: integration?.name || 'Integração não encontrada',
      logo: '/lovable-uploads/569333c2-882a-47f0-a979-7cb705164fbd.png'
    };
  };

  if (loading && bots.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Carregando bots...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-destructive mb-4">Erro ao carregar bots: {error}</p>
          <Button onClick={fetchBots} variant="outline">
            Tentar novamente
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <PageHeader 
            title="Agent Bots" 
            description="Gerencie seus agentes bot" 
          />
        </div>
        <Button onClick={handleCreate}>
          <Plus className="w-4 h-4 mr-2" />
          Novo Bot
        </Button>
      </div>

      {bots.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-64">
            <BotIcon className="w-12 h-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Nenhum bot encontrado</h3>
            <p className="text-muted-foreground text-center mb-4">
              Crie seu primeiro agente bot para começar
            </p>
            <Button onClick={handleCreate}>
              <Plus className="w-4 h-4 mr-2" />
              Criar primeiro bot
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {bots.map((bot) => (
            <Card key={bot.id} className="hover:shadow-md transition-shadow">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-lg font-semibold truncate">
                  {bot.name}
                </CardTitle>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" className="h-8 w-8 p-0">
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => handleEdit(bot)}>
                      <Edit className="mr-2 h-4 w-4" />
                      Editar
                    </DropdownMenuItem>
                    <DropdownMenuItem 
                      onClick={() => handleDeleteClick(bot)}
                      className="text-destructive"
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Excluir
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div>
                    {(() => {
                      const integrationInfo = getIntegrationInfo((bot as any).integration_id);
                      return (
                        <div className="flex items-center space-x-2">
                          {integrationInfo.logo && (
                            <img 
                              src={integrationInfo.logo} 
                              alt="Integração" 
                              className="w-4 h-4 object-contain" 
                            />
                          )}
                          <Badge variant="secondary">
                            {integrationInfo.name}
                          </Badge>
                        </div>
                      );
                    })()}
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground line-clamp-3">
                      {bot.system_prompt}
                    </p>
                  </div>
                  {bot.created_at && (
                    <div className="text-xs text-muted-foreground">
                      Criado em: {new Date(bot.created_at).toLocaleDateString('pt-BR')}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <BotForm
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={handleFormSubmit}
        bot={selectedBot}
        mode={formMode}
        selectedBotId={selectedBot?.id}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar exclusão</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja excluir o bot "{botToDelete?.name}"?
              Esta ação não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};