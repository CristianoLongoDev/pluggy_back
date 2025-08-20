
import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Send, Bot, User, MoreVertical, UserPlus, MessageSquare, Info, ChevronDown, ChevronUp } from 'lucide-react';
import { Separator } from '@/components/ui/separator';
import { validateAndSanitizeMessage } from '@/lib/validation';

interface Message {
  id: string;
  content: string;
  timestamp: string;
  sender: 'customer' | 'ai' | 'agent';
  senderName?: string;
}

interface ChatAreaProps {
  selectedChat: any;
  messages: Message[];
  onSendMessage: (message: string) => void;
  onTransferToHuman: () => void;
  isInfoExpanded?: boolean;
  onToggleInfoExpanded?: () => void;
}

const ChatArea: React.FC<ChatAreaProps> = ({
  selectedChat,
  messages,
  onSendMessage,
  onTransferToHuman,
  isInfoExpanded = false,
  onToggleInfoExpanded,
}) => {
  const [messageInput, setMessageInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change or chat is selected
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, selectedChat]);

  // Debug logs
  console.log('🎯 ChatArea render - selectedChat:', selectedChat?.id);
  console.log('💬 ChatArea render - messages count:', messages.length);
  console.log('📝 ChatArea render - messages:', messages);

  const handleSendMessage = () => {
    if (messageInput.trim()) {
      try {
        const sanitizedMessage = validateAndSanitizeMessage(messageInput);
        onSendMessage(sanitizedMessage);
        setMessageInput('');
      } catch (error) {
        console.error('Invalid message:', error);
        // Could show a toast notification here
        return;
      }
    }
  };

  if (!selectedChat) {
    return (
      <div className="flex-1 flex items-center justify-center bg-muted/20">
        <div className="text-center">
          <MessageSquare className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">Selecione uma conversa</h3>
          <p className="text-muted-foreground">
            Escolha uma conversa da lista para começar a visualizar e responder mensagens.
          </p>
        </div>
      </div>
    );
  }

  const getChannelBadge = (channel: string) => {
    const channelConfig = {
      whatsapp: { label: 'WhatsApp', color: 'bg-green-500' },
      instagram: { label: 'Instagram', color: 'bg-pink-500' },
      facebook: { label: 'Facebook', color: 'bg-blue-500' },
      widget: { label: 'Widget', color: 'bg-purple-500' },
    };
    const config = channelConfig[channel as keyof typeof channelConfig];
    return (
      <Badge variant="secondary" className="text-xs">
        <div className={`w-2 h-2 rounded-full ${config.color} mr-1`}></div>
        {config.label}
      </Badge>
    );
  };

  return (
    <div className="flex-1 flex flex-col">
      {/* Chat Header */}
      <div className="p-4 border-b border-border bg-card">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Avatar className="w-10 h-10">
              <AvatarImage src={selectedChat.customerAvatar} />
              <AvatarFallback>{selectedChat.customerName.charAt(0)}</AvatarFallback>
            </Avatar>
            <div>
              <h3 className="font-medium">{selectedChat.customerName}</h3>
              <div className="flex items-center space-x-2 mt-1">
                {getChannelBadge(selectedChat.channel)}
                <Badge variant={selectedChat.status === 'ai' ? 'secondary' : 'default'} className="text-xs">
                  {selectedChat.status === 'ai' ? (
                    <>
                      <Bot className="w-3 h-3 mr-1" />
                      IA Ativa
                    </>
                  ) : (
                    <>
                      <User className="w-3 h-3 mr-1" />
                      Atendimento Humano
                    </>
                  )}
                </Badge>
              </div>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            {selectedChat.status === 'ai' && (
              <Button size="sm" variant="outline" onClick={onTransferToHuman}>
                <UserPlus className="w-4 h-4 mr-2" />
                Transferir
              </Button>
            )}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="ghost">
                  <MoreVertical className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                {onToggleInfoExpanded && (
                  <DropdownMenuItem onClick={onToggleInfoExpanded}>
                    <Info className="w-4 h-4 mr-2" />
                    {isInfoExpanded ? (
                      <>
                        <ChevronUp className="w-4 h-4 mr-1" />
                        Ocultar informações
                      </>
                    ) : (
                      <>
                        <ChevronDown className="w-4 h-4 mr-1" />
                        Exibir informações
                      </>
                    )}
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-muted-foreground">
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>Nenhuma mensagem para exibir</p>
            </div>
          </div>
        ) : (
        messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.sender === 'customer' ? 'justify-start' : 'justify-end'}`}
          >
            <div
              className={`max-w-[70%] ${
                message.sender === 'customer'
                  ? 'bg-muted/80 text-foreground rounded-l-lg rounded-tr-lg rounded-br-sm'
                  : message.sender === 'ai'
                  ? 'bg-blue-500 text-white rounded-r-lg rounded-tl-lg rounded-bl-sm'
                  : 'bg-primary text-primary-foreground rounded-r-lg rounded-tl-lg rounded-bl-sm'
              } p-3 shadow-sm`}
            >
              {message.sender !== 'customer' && (
                <div className="flex items-center space-x-1 mb-1">
                  {message.sender === 'ai' ? (
                    <Bot className="w-3 h-3" />
                  ) : (
                    <User className="w-3 h-3" />
                  )}
                  <span className="text-xs opacity-80">
                    {message.sender === 'ai' ? 'IA' : (selectedChat.botAgentName || 'Atendente')}
                  </span>
                </div>
              )}
              <p className="text-sm leading-relaxed">{message.content}</p>
              <span className="text-xs opacity-70 mt-1 block">{message.timestamp}</span>
            </div>
          </div>
        ))
        )}
        {/* Invisible element to scroll to */}
        <div ref={messagesEndRef} />
      </div>

      {/* Message Input */}
      <div className="p-4 border-t border-border bg-card">
        <div className="flex items-center space-x-2">
          <Input
            placeholder="Digite sua mensagem..."
            value={messageInput}
            onChange={(e) => setMessageInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            className="flex-1"
          />
          <Button onClick={handleSendMessage} size="sm">
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ChatArea;
