import React, { useState, useEffect } from 'react';
import PageHeader from '@/components/PageHeader';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { IntegrationForm } from '@/components/IntegrationForm';
import { useIntegrations } from '@/hooks/useIntegrations';
import { useToast } from '@/hooks/use-toast';
import { Plus, Edit, Trash2, MoreHorizontal, Hash } from 'lucide-react';

const IntegrationsManagement = () => {
  const { integrations, loading, fetchIntegrations, createIntegration, updateIntegration, deleteIntegration } = useIntegrations();
  const { toast } = useToast();
  
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingIntegration, setEditingIntegration] = useState(null);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [integrationToDelete, setIntegrationToDelete] = useState<string | null>(null);

  useEffect(() => {
    if (fetchIntegrations) {
      fetchIntegrations();
    }
  }, [fetchIntegrations]);

  const getIntegrationIcon = (type: string) => {
    switch (type) {
      case 'movidesk':
        return <img src="/lovable-uploads/569333c2-882a-47f0-a979-7cb705164fbd.png" alt="Movidesk" className="w-5 h-5 object-contain" />;
      default:
        return <Hash className="w-4 h-4" />;
    }
  };

  const getIntegrationTypeLabel = (type: string) => {
    switch (type) {
      case 'movidesk':
        return 'Movidesk';
      default:
        return type;
    }
  };


  const handleCreateIntegration = () => {
    setFormMode('create');
    setEditingIntegration(null);
    setIsFormOpen(true);
  };

  const handleEditIntegration = (integration: any) => {
    setFormMode('edit');
    setEditingIntegration(integration);
    setIsFormOpen(true);
  };

  const handleDeleteIntegration = (integrationId: string) => {
    setIntegrationToDelete(integrationId);
    setIsDeleteDialogOpen(true);
  };

  const confirmDeleteIntegration = async () => {
    if (integrationToDelete) {
      const result = await deleteIntegration(integrationToDelete);
      if (result.success) {
        toast({
          title: "Sucesso",
          description: "Integração excluída com sucesso"
        });
      } else {
        toast({
          title: "Erro",
          description: result.error || "Erro ao excluir integração",
          variant: "destructive"
        });
      }
    }
    setIsDeleteDialogOpen(false);
    setIntegrationToDelete(null);
  };

  const handleIntegrationSubmit = async (integrationData: any) => {
    if (formMode === 'edit' && editingIntegration) {
      return await updateIntegration(editingIntegration.id, integrationData);
    } else {
      return await createIntegration(integrationData);
    }
  };

  return (
    <div className="flex-1 p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <PageHeader 
            title="Integrações" 
            description="Configure e gerencie as integrações com serviços externos" 
          />
        </div>
        <Button onClick={handleCreateIntegration}>
          <Plus className="w-4 h-4 mr-2" />
          Incluir Integração
        </Button>
      </div>
      
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6">
              <div className="space-y-3">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="font-medium">Tipo</TableHead>
                  <TableHead className="font-medium">Nome</TableHead>
                  <TableHead className="font-medium">Status</TableHead>
                  <TableHead className="font-medium">Data Criação</TableHead>
                  <TableHead className="w-[100px] font-medium">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {!integrations || integrations.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                      Nenhuma integração encontrada
                    </TableCell>
                  </TableRow>
                ) : (
                  integrations.map((integration) => (
                    <TableRow key={integration.id}>
                      <TableCell>
                        <div className="flex items-center space-x-2">
                          {getIntegrationIcon(integration.integration_type)}
                          <span>{getIntegrationTypeLabel(integration.integration_type)}</span>
                        </div>
                      </TableCell>
                      <TableCell className="font-medium">{integration.name}</TableCell>
                      <TableCell>
                        <Badge variant={integration.is_active ? "success" : "destructive"}>
                          {integration.is_active ? 'Ativo' : 'Inativo'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {integration.created_at ? new Date(integration.created_at).toLocaleDateString('pt-BR') : '-'}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="bg-background border z-50">
                            <DropdownMenuItem onClick={() => handleEditIntegration(integration)}>
                              <Edit className="mr-2 h-4 w-4" />
                              Alterar
                            </DropdownMenuItem>
                            <DropdownMenuItem 
                              onClick={() => handleDeleteIntegration(integration.id)}
                              className="text-destructive focus:text-destructive"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Excluir
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <IntegrationForm
        open={isFormOpen}
        onOpenChange={setIsFormOpen}
        onSubmit={handleIntegrationSubmit}
        integration={editingIntegration}
        mode={formMode}
      />

      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar Exclusão</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja excluir esta integração? Esta ação não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteIntegration}
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

export default IntegrationsManagement;