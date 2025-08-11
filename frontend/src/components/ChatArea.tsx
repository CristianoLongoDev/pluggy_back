
import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Send, Bot, User, MoreVertical, UserPlus, MessageSquare } from 'lucide-react';
import { Separator } from '@/components/ui/separator';

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
}

const ChatArea: React.FC<ChatAreaProps> = ({
  selectedChat,
  messages,
  onSendMessage,
  onTransferToHuman,
}) => {
  const [messageInput, setMessageInput] = useState('');

  const handleSendMessage = () => {
    if (messageInput.trim()) {
      onSendMessage(messageInput);
      setMessageInput('');
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
            <Button size="sm" variant="ghost">
              <MoreVertical className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.sender === 'customer' ? 'justify-start' : 'justify-end'}`}
          >
            <div
              className={`max-w-[70%] ${
                message.sender === 'customer'
                  ? 'bg-muted'
                  : message.sender === 'ai'
                  ? 'bg-blue-500 text-white'
                  : 'bg-primary text-primary-foreground'
              } rounded-lg p-3`}
            >
              {message.sender !== 'customer' && (
                <div className="flex items-center space-x-1 mb-1">
                  {message.sender === 'ai' ? (
                    <Bot className="w-3 h-3" />
                  ) : (
                    <User className="w-3 h-3" />
                  )}
                  <span className="text-xs opacity-80">
                    {message.sender === 'ai' ? 'IA' : 'Atendente'}
                  </span>
                </div>
              )}
              <p className="text-sm">{message.content}</p>
              <span className="text-xs opacity-70 mt-1 block">{message.timestamp}</span>
            </div>
          </div>
        ))}
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
