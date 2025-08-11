
import React, { useState } from 'react';
import Header from '@/components/Header';
import ChatSidebar from '@/components/ChatSidebar';
import ChatList from '@/components/ChatList';
import ChatArea from '@/components/ChatArea';
import ChatInfo from '@/components/ChatInfo';
import { MessageSquare } from 'lucide-react';

// Mock data
const mockChats = [
  {
    id: '1',
    customerName: 'Maria Silva',
    customerAvatar: '',
    lastMessage: 'Preciso de ajuda com meu pedido',
    timestamp: '14:32',
    channel: 'whatsapp' as const,
    status: 'ai' as const,
    unreadCount: 2,
    isActive: true,
  },
  {
    id: '2',
    customerName: 'João Santos',
    customerAvatar: '',
    lastMessage: 'Quando será feita a entrega?',
    timestamp: '14:15',
    channel: 'instagram' as const,
    status: 'human' as const,
    unreadCount: 0,
    isActive: false,
  },
  {
    id: '3',
    customerName: 'Ana Costa',
    customerAvatar: '',
    lastMessage: 'Gostaria de cancelar minha assinatura',
    timestamp: '13:45',
    channel: 'facebook' as const,
    status: 'ai' as const,
    unreadCount: 1,
    isActive: false,
  },
  {
    id: '4',
    customerName: 'Pedro Oliveira',
    customerAvatar: '',
    lastMessage: 'Como faço para trocar um produto?',
    timestamp: '13:20',
    channel: 'widget' as const,
    status: 'pending' as const,
    unreadCount: 3,
    isActive: false,
  },
];

const mockMessages = [
  {
    id: '1',
    content: 'Olá! Preciso de ajuda com meu pedido',
    timestamp: '14:30',
    sender: 'customer' as const,
  },
  {
    id: '2',
    content: 'Olá Maria! Sou a IA assistente da empresa. Em que posso ajudá-la com seu pedido?',
    timestamp: '14:30',
    sender: 'ai' as const,
  },
  {
    id: '3',
    content: 'Meu pedido não chegou e já passou do prazo',
    timestamp: '14:31',
    sender: 'customer' as const,
  },
  {
    id: '4',
    content: 'Entendo sua preocupação. Vou verificar o status do seu pedido. Poderia me informar o número do pedido?',
    timestamp: '14:31',
    sender: 'ai' as const,
  },
  {
    id: '5',
    content: 'É o pedido #12345',
    timestamp: '14:32',
    sender: 'customer' as const,
  },
];

const Index = () => {
  const [selectedFilter, setSelectedFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedChatId, setSelectedChatId] = useState<string | null>('1');
  
  const selectedChat = mockChats.find(chat => chat.id === selectedChatId);
  
  const filteredChats = mockChats.filter(chat => {
    const matchesFilter = selectedFilter === 'all' || chat.status === selectedFilter;
    const matchesSearch = chat.customerName.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         chat.lastMessage.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const handleSendMessage = (message: string) => {
    console.log('Sending message:', message);
    // Implement message sending logic
  };

  const handleTransferToHuman = () => {
    console.log('Transferring to human');
    // Implement transfer logic
  };

  return (
    <div className="h-screen flex flex-col bg-background">
      <Header />
      
      <div className="flex-1 flex overflow-hidden">
        <div className="flex">
          <ChatSidebar
            selectedFilter={selectedFilter}
            onFilterChange={setSelectedFilter}
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
          />
          
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
                onChatSelect={setSelectedChatId}
              />
            </div>
          </div>
        </div>

        <ChatArea
          selectedChat={selectedChat}
          messages={mockMessages}
          onSendMessage={handleSendMessage}
          onTransferToHuman={handleTransferToHuman}
        />

        <ChatInfo selectedChat={selectedChat} />
      </div>
    </div>
  );
};

export default Index;
