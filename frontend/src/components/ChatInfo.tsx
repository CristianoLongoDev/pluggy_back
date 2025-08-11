
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { 
  User, 
  Calendar, 
  MessageSquare, 
  Clock, 
  Phone, 
  Mail, 
  MapPin,
  Tag,
  History
} from 'lucide-react';

interface ChatInfoProps {
  selectedChat: any;
}

const ChatInfo: React.FC<ChatInfoProps> = ({ selectedChat }) => {
  if (!selectedChat) {
    return (
      <div className="w-80 bg-card border-l border-border p-4">
        <p className="text-muted-foreground text-center">
          Selecione uma conversa para ver os detalhes
        </p>
      </div>
    );
  }

  const customerInfo = {
    email: 'cliente@email.com',
    phone: '+55 11 99999-9999',
    location: 'São Paulo, SP',
    firstContact: '15/12/2024',
    totalChats: 5,
    avgResponseTime: '2min',
    tags: ['VIP', 'Recorrente']
  };

  return (
    <div className="w-80 bg-card border-l border-border flex flex-col h-full overflow-y-auto">
      <div className="p-4 border-b border-border">
        <h3 className="font-semibold mb-3">Informações do Cliente</h3>
        
        <div className="text-center mb-4">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white text-xl font-bold mx-auto mb-2">
            {selectedChat.customerName.charAt(0)}
          </div>
          <h4 className="font-medium">{selectedChat.customerName}</h4>
        </div>

        <div className="space-y-2 text-sm">
          <div className="flex items-center space-x-2">
            <Mail className="w-4 h-4 text-muted-foreground" />
            <span>{customerInfo.email}</span>
          </div>
          <div className="flex items-center space-x-2">
            <Phone className="w-4 h-4 text-muted-foreground" />
            <span>{customerInfo.phone}</span>
          </div>
          <div className="flex items-center space-x-2">
            <MapPin className="w-4 h-4 text-muted-foreground" />
            <span>{customerInfo.location}</span>
          </div>
        </div>

        <div className="flex flex-wrap gap-1 mt-3">
          {customerInfo.tags.map((tag) => (
            <Badge key={tag} variant="outline" className="text-xs">
              <Tag className="w-3 h-3 mr-1" />
              {tag}
            </Badge>
          ))}
        </div>
      </div>

      <div className="p-4 space-y-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Estatísticas</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center text-muted-foreground">
                <Calendar className="w-4 h-4 mr-2" />
                Primeiro contato
              </span>
              <span>{customerInfo.firstContact}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center text-muted-foreground">
                <MessageSquare className="w-4 h-4 mr-2" />
                Total de chats
              </span>
              <span>{customerInfo.totalChats}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center text-muted-foreground">
                <Clock className="w-4 h-4 mr-2" />
                Tempo médio
              </span>
              <span>{customerInfo.avgResponseTime}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center">
              <History className="w-4 h-4 mr-2" />
              Histórico Recente
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="text-xs text-muted-foreground border-l-2 border-blue-500 pl-3 py-1">
                <p className="font-medium">Chat iniciado</p>
                <p>Hoje às 14:30</p>
              </div>
              <div className="text-xs text-muted-foreground border-l-2 border-green-500 pl-3 py-1">
                <p className="font-medium">Problema resolvido</p>
                <p>Ontem às 16:45</p>
              </div>
              <div className="text-xs text-muted-foreground border-l-2 border-purple-500 pl-3 py-1">
                <p className="font-medium">Primeira interação</p>
                <p>15/12/2024</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-2">
          <Button variant="outline" size="sm" className="w-full">
            <User className="w-4 h-4 mr-2" />
            Ver perfil completo
          </Button>
          <Button variant="outline" size="sm" className="w-full">
            <MessageSquare className="w-4 h-4 mr-2" />
            Histórico completo
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ChatInfo;
