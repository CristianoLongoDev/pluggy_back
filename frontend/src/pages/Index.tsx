
import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useAccountData } from '@/hooks/useAccountData';
import { useChannels } from '@/hooks/useChannels';
import { useRealtimeConversations } from '@/hooks/useRealtimeConversations';
import Header from '@/components/Header';
import ChatSidebar from '@/components/ChatSidebar';
import ChatList from '@/components/ChatList';
import ChatArea from '@/components/ChatArea';
import ChatInfo from '@/components/ChatInfo';
import { ChannelForm } from '@/components/ChannelForm';
import { BotList } from '@/components/BotList';
import PromptsManagement from '@/pages/PromptsManagement';
import IntentionsManagement from '@/pages/IntentionsManagement';
import FunctionsManagement from '@/pages/FunctionsManagement';
import IntegrationsManagement from '@/pages/IntegrationsManagement';
import PageHeader from '@/components/PageHeader';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { useToast } from '@/hooks/use-toast';
import { MessageSquare, Plus, Edit, Trash2, MoreHorizontal } from 'lucide-react';


const Index = () => {
  const { profile, isAdmin } = useAuth();
  const { accountData, loading: accountLoading } = useAccountData();
  const { channels, loading: channelsLoading, fetchChannels, createChannel, updateChannel, deleteChannel } = useChannels();
  const { chats, messages, isConnected, sendMessage, transferToHuman, refreshConversations, fetchMessages, markAsRead } = useRealtimeConversations();
  const { toast } = useToast();
  
  const [selectedFilter, setSelectedFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [selectedSection, setSelectedSection] = useState('conversations');
  const [isInfoExpanded, setIsInfoExpanded] = useState(false);
  
  // Channel management states
  const [isChannelFormOpen, setIsChannelFormOpen] = useState(false);
  const [editingChannel, setEditingChannel] = useState(null);
  const [channelFormMode, setChannelFormMode] = useState<'create' | 'edit'>('create');
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [channelToDelete, setChannelToDelete] = useState<string | null>(null);
  
  // Fetch channels when entering channels section
  useEffect(() => {
    if (selectedSection === 'channels') {
      fetchChannels();
    }
  }, [selectedSection]); // Remove fetchChannels dependency to avoid infinite loop
  
  const selectedChat = chats.find(chat => chat.id === selectedChatId);
  
  const filteredChats = chats.filter(chat => {
    const matchesFilter = selectedFilter === 'all' || chat.status === selectedFilter;
    const matchesSearch = chat.customerName.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         chat.lastMessage.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  // Mock data for settings sections
  const mockUsers = [
    { id: '1', name: 'Admin User', email: 'admin@empresa.com', role: 'Administrador', status: 'Ativo', createdAt: '2024-01-15' },
    { id: '2', name: 'Agent User', email: 'agent@empresa.com', role: 'Agente', status: 'Ativo', createdAt: '2024-02-20' },
  ];

  const handleSendMessage = (message: string) => {
    if (selectedChatId) {
      sendMessage(selectedChatId, message);
    }
  };

  const handleTransferToHuman = () => {
    if (selectedChatId) {
      transferToHuman(selectedChatId);
      toast({
        title: "Chat transferido",
        description: "A conversa foi transferida para um atendente humano.",
      });
    }
  };

  // Channel management handlers
  const handleCreateChannel = () => {
    setChannelFormMode('create');
    setEditingChannel(null);
    setIsChannelFormOpen(true);
  };

  const handleEditChannel = (channel: any) => {
    setChannelFormMode('edit');
    setEditingChannel(channel);
    setIsChannelFormOpen(true);
  };

  const handleDeleteChannel = (channelId: string) => {
    setChannelToDelete(channelId);
    setIsDeleteDialogOpen(true);
  };

  const confirmDeleteChannel = async () => {
    if (channelToDelete) {
      const result = await deleteChannel(channelToDelete);
      if (result.success) {
        toast({
          title: "Sucesso",
          description: "Canal excluído com sucesso"
        });
      } else {
        toast({
          title: "Erro",
          description: result.error || "Erro ao excluir canal",
          variant: "destructive"
        });
      }
    }
    setIsDeleteDialogOpen(false);
    setChannelToDelete(null);
  };

  const handleChannelSubmit = async (channelData: any) => {
    if (channelFormMode === 'edit' && editingChannel) {
      return await updateChannel(channelData.id, channelData);
    } else {
      return await createChannel(channelData);
    }
  };

  const renderMainContent = () => {
    switch (selectedSection) {
      case 'conversations':
        if (!isConnected) {
          return (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center space-y-2">
                <div className="text-lg font-medium text-destructive">Conexão perdida</div>
                <div className="text-sm text-muted-foreground">Tentando reconectar...</div>
              </div>
            </div>
          );
        }

        if (chats.length === 0) {
          return (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center space-y-2">
                <MessageSquare className="w-12 h-12 text-muted-foreground mx-auto" />
                <div className="text-lg font-medium">Nenhuma conversa ativa</div>
                <div className="text-sm text-muted-foreground">As conversas aparecerão aqui quando chegarem</div>
              </div>
            </div>
          );
        }

        return (
          <>
            <div className="w-80 border-r border-border bg-card overflow-y-auto">
              <div className="p-4 border-b border-border">
                <h3 className="font-medium text-sm text-muted-foreground mb-3">
                  CONVERSAS ATIVAS ({filteredChats.length})
                </h3>
              </div>
              <div className="p-2">
                <ChatList
                  chats={filteredChats}
                  selectedChatId={selectedChatId}
                  onChatSelect={(chatId) => {
                    console.log('🎯 CHAT SELECTED:', chatId);
                    setSelectedChatId(chatId);
                    markAsRead(chatId); // Reset unread count
                    console.log('📞 CALLING fetchMessages for chat:', chatId);
                    fetchMessages(chatId);
                  }}
                />
              </div>
            </div>

            <ChatArea
              selectedChat={selectedChat}
              messages={selectedChatId ? messages[selectedChatId] || [] : []}
              onSendMessage={handleSendMessage}
              onTransferToHuman={handleTransferToHuman}
              isInfoExpanded={isInfoExpanded}
              onToggleInfoExpanded={() => setIsInfoExpanded(!isInfoExpanded)}
            />

            {isInfoExpanded && (
              <ChatInfo 
                selectedChat={selectedChat} 
                isExpanded={isInfoExpanded} 
              />
            )}
          </>
        );

      case 'account':
        return (
          <div className="flex-1 p-6">
            <Tabs defaultValue="account" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="account">Conta</TabsTrigger>
                <TabsTrigger value="users">Usuários</TabsTrigger>
              </TabsList>
              <TabsContent value="account" className="space-y-4">
                <PageHeader 
                  title="Informações da Conta" 
                  description="Visualize e gerencie as configurações da sua conta" 
                />
                <Card>
                  <CardContent className="space-y-4">
                    <div>
                      <label className="text-sm font-medium">ID da Conta</label>
                      {accountLoading ? (
                        <Skeleton className="h-6 w-48 mt-1" />
                      ) : (
                        <p className="text-lg mt-1 font-mono">{accountData?.id || 'Não informado'}</p>
                      )}
                    </div>
                    
                    <div>
                      <label className="text-sm font-medium">Nome da Conta</label>
                      {accountLoading ? (
                        <Skeleton className="h-6 w-64 mt-1" />
                      ) : (
                        <p className="text-lg mt-1">{accountData?.name || 'Nome não disponível'}</p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
              
              <TabsContent value="users" className="space-y-4">
                <div className="flex justify-between items-center">
                  <div>
                    <PageHeader 
                      title="Usuários" 
                      description="Gerencie os usuários com acesso ao sistema" 
                    />
                  </div>
                  <Button>
                    <Plus className="w-4 h-4 mr-2" />
                    Cadastrar Usuário
                  </Button>
                </div>
                
                <Card>
                  <CardContent className="p-0">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Nome</TableHead>
                          <TableHead>Email</TableHead>
                          <TableHead>Função</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Data Criação</TableHead>
                          <TableHead>Ações</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {mockUsers.map((user) => (
                          <TableRow key={user.id}>
                            <TableCell>{user.name}</TableCell>
                            <TableCell>{user.email}</TableCell>
                            <TableCell>{user.role}</TableCell>
                            <TableCell>
                              <Badge variant={user.status === 'Ativo' ? 'default' : 'secondary'}>
                                {user.status}
                              </Badge>
                            </TableCell>
                            <TableCell>{user.createdAt}</TableCell>
                            <TableCell>
                              <div className="flex space-x-2">
                                <Button variant="ghost" size="sm">
                                  <Edit className="w-4 h-4" />
                                </Button>
                                <Button variant="ghost" size="sm">
                                  <Trash2 className="w-4 h-4" />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        );

      case 'channels':
        return (
          <div className="flex-1 p-6">
            <div className="flex justify-between items-center mb-6">
              <div>
                <PageHeader 
                  title="Canais de Atendimento" 
                  description="Configure e gerencie os canais de comunicação com seus clientes" 
                />
              </div>
              <Button onClick={handleCreateChannel}>
                <Plus className="w-4 h-4 mr-2" />
                Incluir Novo
              </Button>
            </div>
            
            <Card>
              <CardContent className="p-0">
                {channelsLoading ? (
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
                         <TableHead className="font-medium">ID</TableHead>
                         <TableHead className="font-medium">Nome</TableHead>
                         <TableHead className="font-medium">Tipo</TableHead>
                         <TableHead className="font-medium">Status</TableHead>
                         <TableHead className="font-medium">Data Criação</TableHead>
                         <TableHead className="w-[100px] font-medium">Ações</TableHead>
                       </TableRow>
                     </TableHeader>
                    <TableBody>
                       {channels.length === 0 ? (
                         <TableRow>
                           <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                             Nenhum canal encontrado
                           </TableCell>
                         </TableRow>
                       ) : (
                         channels.map((channel) => (
                           <TableRow key={channel.id}>
                             <TableCell className="font-mono text-sm">
                               {channel.id ? channel.id.substring(0, 8) + '...' : '-'}
                             </TableCell>
                             <TableCell className="font-medium">{channel.name}</TableCell>
                             <TableCell>
                               <Badge variant="outline">
                                 {channel.type}
                               </Badge>
                             </TableCell>
                              <TableCell>
                                <Badge variant={channel.active ? "success" : "destructive"}>
                                  {channel.active ? 'Ativo' : 'Desabilitado'}
                                </Badge>
                              </TableCell>
                             <TableCell className="text-sm text-muted-foreground">
                               {channel.created_at ? new Date(channel.created_at).toLocaleDateString('pt-BR') : '-'}
                             </TableCell>
                            <TableCell>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" className="h-8 w-8 p-0">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end" className="bg-background border z-50">
                                  <DropdownMenuItem onClick={() => handleEditChannel(channel)}>
                                    <Edit className="mr-2 h-4 w-4" />
                                    Alterar
                                  </DropdownMenuItem>
                                  <DropdownMenuItem 
                                    onClick={() => handleDeleteChannel(channel.id)}
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

            <ChannelForm
              open={isChannelFormOpen}
              onOpenChange={setIsChannelFormOpen}
              onSubmit={handleChannelSubmit}
              channel={editingChannel}
              mode={channelFormMode}
            />

            <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Confirmar Exclusão</AlertDialogTitle>
                  <AlertDialogDescription>
                    Tem certeza que deseja excluir este canal? Esta ação não pode ser desfeita.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={confirmDeleteChannel}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    Excluir
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        );

      case 'agent-bots':
        return (
          <div className="flex-1 p-6">
            <BotList />
          </div>
        );

      case 'prompts':
        return (
          <div className="flex-1 p-6">
            <PromptsManagement />
          </div>
        );

      case 'intents':
        return (
          <div className="flex-1 p-6">
            <IntentionsManagement />
          </div>
        );

      case 'roles':
        return (
          <div className="flex-1 p-6">
            <FunctionsManagement />
          </div>
        );

      case 'integrations':
        return <IntegrationsManagement />;

      default:
        return null;
    }
  };

  return (
    <div className="h-screen flex flex-col bg-background">
      <Header />
      
      <div className="flex-1 flex overflow-hidden">
              <ChatSidebar
                selectedFilter={selectedFilter}
                onFilterChange={setSelectedFilter}
                searchTerm={searchTerm}
                onSearchChange={setSearchTerm}
                selectedSection={selectedSection}
                onSectionChange={setSelectedSection}
                chats={chats}
              />
        
        {renderMainContent()}
      </div>
    </div>
  );
};

export default Index;
