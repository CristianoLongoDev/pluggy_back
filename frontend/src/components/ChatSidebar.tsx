
import React, { useState } from 'react';
import { MessageSquare, Bot, User, Filter, Search, Plus, Settings, Users, FileText, ShieldCheck, ChevronDown, ChevronRight, Puzzle, Target } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';

interface Chat {
  id: string;
  status: 'ai' | 'human' | 'pending' | 'closed';
  unreadCount: number;
}

interface ChatSidebarProps {
  selectedFilter: string;
  onFilterChange: (filter: string) => void;
  searchTerm: string;
  onSearchChange: (term: string) => void;
  selectedSection: string;
  onSectionChange: (section: string) => void;
  chats: Chat[];
}

const ChatSidebar: React.FC<ChatSidebarProps> = ({
  selectedFilter,
  onFilterChange,
  searchTerm,
  onSearchChange,
  selectedSection,
  onSectionChange,
  chats,
}) => {
  const [isConversationsExpanded, setIsConversationsExpanded] = useState(selectedSection === 'conversations');
  
  // Calculate counts dynamically based on unread chats only
  const unreadChats = chats.filter(chat => chat.unreadCount > 0);
  const unreadAiChats = unreadChats.filter(chat => chat.status === 'ai');
  const unreadHumanChats = unreadChats.filter(chat => chat.status === 'human');
  const unreadPendingChats = unreadChats.filter(chat => chat.status === 'pending');
  
  const filters = [
    { id: 'all', label: 'Todas', icon: MessageSquare, count: unreadChats.length },
    { id: 'ai', label: 'IA Ativa', icon: Bot, count: unreadAiChats.length },
    { id: 'human', label: 'Atendimento Humano', icon: User, count: unreadHumanChats.length },
    { id: 'pending', label: 'Pendentes', icon: Filter, count: unreadPendingChats.length },
  ];

  const configSections = [
    { id: 'account', label: 'Minha Conta', icon: User },
    { id: 'agent-bots', label: 'Agentes Bots', icon: Bot },
    { id: 'channels', label: 'Canais Atendimento', icon: Settings },
    { id: 'integrations', label: 'Integrações', icon: Puzzle },
    { id: 'prompts', label: 'Eventos', icon: FileText },
    { id: 'intents', label: 'Intenções', icon: Target },
    { id: 'roles', label: 'Funções', icon: ShieldCheck },
  ];

  const handleConversationsClick = () => {
    setIsConversationsExpanded(!isConversationsExpanded);
    onSectionChange('conversations');
  };

  return (
    <div className="w-80 bg-card border-r border-border flex flex-col h-full">
      {/* Seções de navegação */}
      <div className="p-4 border-b border-border">
        <div className="space-y-1">
          {/* Menu Conversas expansível */}
          <Collapsible open={isConversationsExpanded} onOpenChange={setIsConversationsExpanded}>
            <CollapsibleTrigger asChild>
              <Button
                variant={selectedSection === 'conversations' ? "secondary" : "ghost"}
                className="w-full justify-start"
                onClick={handleConversationsClick}
              >
                <MessageSquare className="w-4 h-4 mr-3" />
                Conversas
                {isConversationsExpanded ? 
                  <ChevronDown className="w-4 h-4 ml-auto" /> : 
                  <ChevronRight className="w-4 h-4 ml-auto" />
                }
              </Button>
            </CollapsibleTrigger>
            
            <CollapsibleContent className="space-y-3 pt-3">
              <div className="pl-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-muted-foreground">Filtros</span>
                  <Button size="sm" variant="outline">
                    <Plus className="w-4 h-4 mr-2" />
                    Nova
                  </Button>
                </div>
                
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
                  <Input
                    placeholder="Buscar conversas..."
                    value={searchTerm}
                    onChange={(e) => onSearchChange(e.target.value)}
                    className="pl-10"
                  />
                </div>

                <div className="space-y-1">
                  {filters.map((filter) => {
                    const Icon = filter.icon;
                    return (
                      <Button
                        key={filter.id}
                        variant={selectedSection === 'conversations' && selectedFilter === filter.id ? "default" : "ghost"}
                        className="w-full justify-start text-sm"
                        onClick={() => {
                          onFilterChange(filter.id);
                          // Automaticamente selecionar conversas ao clicar em um filtro
                          if (selectedSection !== 'conversations') {
                            onSectionChange('conversations');
                            setIsConversationsExpanded(true);
                          }
                        }}
                      >
                        <Icon className="w-4 h-4 mr-3" />
                        {filter.label}
                        <Badge variant="secondary" className="ml-auto text-xs">
                          {filter.count}
                        </Badge>
                      </Button>
                    );
                  })}
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {/* Separador com espaçamento maior quando conversas estão expandidas */}
          <div className={isConversationsExpanded ? "pt-6" : "pt-2"}>
            <Separator className="mb-3" />
          </div>

          {/* Outras seções de configuração */}
          {configSections.map((section) => {
            const Icon = section.icon;
            return (
              <Button
                key={section.id}
                variant={selectedSection === section.id ? "secondary" : "ghost"}
                className="w-full justify-start"
                onClick={() => onSectionChange(section.id)}
              >
                <Icon className="w-4 h-4 mr-3" />
                {section.label}
              </Button>
            );
          })}
        </div>
      </div>

      {/* Lista de conversas quando a seção está expandida */}
      {selectedSection === 'conversations' && isConversationsExpanded && (
        <div className="flex-1 overflow-y-auto">
          <div className="p-2 space-y-1">
            {/* Chat list will be rendered here */}
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatSidebar;
