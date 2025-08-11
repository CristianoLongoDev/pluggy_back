
import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { MessageSquare, Bot, User } from 'lucide-react';

interface Chat {
  id: string;
  customerName: string;
  customerAvatar?: string;
  lastMessage: string;
  timestamp: string;
  channel: 'whatsapp' | 'instagram' | 'facebook' | 'widget';
  status: 'ai' | 'human' | 'pending' | 'closed';
  unreadCount: number;
  isActive: boolean;
}

interface ChatListProps {
  chats: Chat[];
  selectedChatId: string | null;
  onChatSelect: (chatId: string) => void;
}

const ChatList: React.FC<ChatListProps> = ({ chats, selectedChatId, onChatSelect }) => {
  const getChannelColor = (channel: string) => {
    const colors = {
      whatsapp: 'bg-green-500',
      instagram: 'bg-pink-500',
      facebook: 'bg-blue-500',
      widget: 'bg-purple-500',
    };
    return colors[channel as keyof typeof colors] || 'bg-gray-500';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ai':
        return <Bot className="w-3 h-3 text-blue-500" />;
      case 'human':
        return <User className="w-3 h-3 text-green-500" />;
      default:
        return <MessageSquare className="w-3 h-3 text-gray-500" />;
    }
  };

  const getStatusText = (status: string) => {
    const statusMap = {
      ai: 'IA',
      human: 'Humano',
      pending: 'Pendente',
      closed: 'Finalizado'
    };
    return statusMap[status as keyof typeof statusMap] || status;
  };

  return (
    <div className="space-y-1">
      {chats.map((chat) => (
        <div
          key={chat.id}
          className={`p-3 rounded-lg cursor-pointer transition-colors hover:bg-muted/50 ${
            selectedChatId === chat.id ? 'bg-muted' : ''
          }`}
          onClick={() => onChatSelect(chat.id)}
        >
          <div className="flex items-start space-x-3">
            <div className="relative">
              <Avatar className="w-10 h-10">
                <AvatarImage src={chat.customerAvatar} />
                <AvatarFallback>{chat.customerName.charAt(0)}</AvatarFallback>
              </Avatar>
              <div 
                className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full ${getChannelColor(chat.channel)} flex items-center justify-center`}
              >
                <div className="w-2 h-2 bg-white rounded-full"></div>
              </div>
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <h4 className="font-medium truncate">{chat.customerName}</h4>
                <span className="text-xs text-muted-foreground">{chat.timestamp}</span>
              </div>
              
              <p className="text-sm text-muted-foreground truncate mb-2">
                {chat.lastMessage}
              </p>
              
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-1">
                  {getStatusIcon(chat.status)}
                  <span className="text-xs text-muted-foreground">
                    {getStatusText(chat.status)}
                  </span>
                </div>
                
                {chat.unreadCount > 0 && (
                  <Badge variant="destructive" className="text-xs h-5 min-w-5 flex items-center justify-center">
                    {chat.unreadCount}
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default ChatList;
