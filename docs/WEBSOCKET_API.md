# 🔌 WebSocket API - Documentação Frontend

## 📋 **Visão Geral**

Esta API WebSocket permite comunicação em tempo real entre o frontend e o sistema de atendimento, fornecendo funcionalidades para:
- Receber mensagens em tempo real
- Buscar histórico de mensagens com paginação
- Enviar mensagens
- Monitorar conversas específicas

**URL do WebSocket:** `wss://atendimento.pluggerbi.com/ws`

---

## 🔐 **Autenticação**

### **1. Conectar ao WebSocket**
```javascript
const ws = new WebSocket('wss://atendimento.pluggerbi.com/ws');
```

### **2. Autenticar (OBRIGATÓRIO)**
Primeira mensagem deve ser de autenticação:
```javascript
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'authenticate',
    data: {
      token: 'seu_jwt_token_aqui'
    }
  }));
};
```

---

## 📨 **Comandos Disponíveis**

### **1. Monitorar Conversas** 

#### **1a. Monitorar conversas específicas**
```javascript
ws.send(JSON.stringify({
  type: 'subscribe_conversations',
  data: {
    conversation_ids: [123, 456, 789] // Array de IDs das conversas
  }
}));
```

**Resposta (IDs específicos):**
```javascript
{
  "type": "subscription_updated",
  "conversation_ids": [123, 456, 789],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### **1b. Monitorar TODAS as conversas da conta**
```javascript
ws.send(JSON.stringify({
  type: 'subscribe_conversations',
  data: {
    conversation_ids: [] // Array vazio = todas as conversas
  }
}));
```

**Resposta (todas as conversas):**
```javascript
{
  "type": "subscription_updated",
  "conversation_ids": [123, 456, 789],
  "data": {
    "conversations": [
      {
        "id": 123,
        "customer_name": "João Silva",
        "channel": "whatsapp",
        "status": "ai",                   // ai|human|waiting - Status normalizado
        "conversation_status": "active",  // NOVO: active|closed - Status do banco
        "created_at": "2024-01-15T09:00:00Z",
        "updated_at": "2024-01-15T10:30:00Z",
        "last_message": "Última mensagem",
        "unread_count": 0,
        "metadata": {
          "contact": {
            "id": "contact_123",
            "phone": "+5511999999999",
            "email": "joao@email.com"
          },
          "channel": {
            "id": "channel_456",
            "name": "WhatsApp Principal",
            "type": "whatsapp"
          },
          "bot": {
            "name": "Bot Atendimento",
            "agent_name": "Maria Assistente"
          },
          "stats": {
            "message_count": 15,
            "ended_at": null
          }
        }
      }
    ]
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### **2. Buscar Mensagens**
```javascript
ws.send(JSON.stringify({
  type: 'get_messages',
  data: {
    conversation_id: 123,  // OBRIGATÓRIO
    limit: 50,             // Opcional, padrão: 50, máximo: 1000
    offset: 0              // Opcional, padrão: 0
  }
}));
```

**Resposta:**
```javascript
{
  "type": "messages_response",
  "conversation_id": 123,
  "data": {
    "messages": [
      {
        "id": "msg_001",
        "conversation_id": 123,
        "content": "Olá! Como posso ajudar?",
        "sender": "customer",           // customer|agent|ai
        "timestamp": "2024-01-15T10:30:00Z",
        "channel": "whatsapp",
        "message_type": "text",
        "tokens": 0,
        "metadata": {
          "contact": {
            "id": "contact_123",
            "name": "João Silva",
            "phone": "+5511999999999"
          },
          "bot": {
            "name": "Bot Atendimento",
            "agent_name": "Maria"
          }
        }
      }
    ],
    "conversation_status": "active",    // NOVO: active|closed
    "pagination": {
      "limit": 50,
      "offset": 0,
      "total": 1,
      "has_more": false
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### **3. Enviar Mensagem**
```javascript
ws.send(JSON.stringify({
  type: 'send_message',
  data: {
    conversation_id: 123,           // OBRIGATÓRIO
    content: "Olá! Como posso ajudar?", // OBRIGATÓRIO
    sender: "agent",                // Opcional, padrão: "agent"
    user_id: "user-uuid-12345"      // Opcional: ID do usuário que enviou (para mensagens humanas)
  }
}));
```

**Resposta:**
```javascript
{
  "type": "message_sent",
  "conversation_id": 123,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### **4. Manter Conexão (Ping)**
```javascript
// Enviar a cada 30 segundos para manter conexão
ws.send(JSON.stringify({
  type: 'ping'
}));
```

**Resposta:**
```javascript
{
  "type": "pong",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## 📥 **Eventos Recebidos**

### **1. Nova Mensagem**
Recebido automaticamente quando há nova mensagem em conversas monitoradas:
```javascript
{
  "type": "new_message",
  "conversation_id": 123,
  "data": {
    "id": "msg_002",
    "conversation_id": 123,
    "content": "Preciso de ajuda com meu pedido",
    "sender": "customer",
    "timestamp": "2024-01-15T10:35:00Z",
    "channel": "whatsapp",
    "message_type": "text",
    "tokens": 0,
    "metadata": {
      "contact": {
        "id": "contact_123",
        "name": "João Silva",
        "phone": "+5511999999999"
      },
      "bot": {
        "name": "Bot Atendimento",
        "agent_name": "Maria"
      }
    }
  },
  "timestamp": "2024-01-15T10:35:00Z"
}
```

### **2. Confirmação de Conexão**
```javascript
{
  "type": "connection_confirmed",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### **3. Erros**
```javascript
{
  "type": "error",
  "error": "conversation_id é obrigatório para get_messages",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## 🔧 **Implementação Completa**

### **Exemplo React Hook**
```javascript
import { useState, useEffect, useCallback } from 'react';

export const useWebSocket = (url, token) => {
  const [ws, setWs] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState({});

  useEffect(() => {
    if (!token) return;

    const websocket = new WebSocket(url);
    
    websocket.onopen = () => {
      // Autenticar
      websocket.send(JSON.stringify({
        type: 'authenticate',
        data: { token }
      }));
    };

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'connection_confirmed':
          setIsConnected(true);
          console.log('✅ WebSocket conectado');
          break;
          
        case 'new_message':
          // Adicionar nova mensagem
          const { conversation_id, data: messageData } = data;
          setMessages(prev => ({
            ...prev,
            [conversation_id]: [
              ...(prev[conversation_id] || []),
              messageData
            ]
          }));
          break;
          
        case 'messages_response':
          // Atualizar mensagens da conversa
          setMessages(prev => ({
            ...prev,
            [data.conversation_id]: data.data.messages
          }));
          break;
          
        case 'error':
          console.error('❌ Erro WebSocket:', data.error);
          break;
      }
    };

    websocket.onclose = () => {
      setIsConnected(false);
      console.log('🔌 WebSocket desconectado');
    };

    setWs(websocket);

    return () => websocket.close();
  }, [url, token]);

  // Buscar mensagens
  const getMessages = useCallback((conversationId, limit = 50, offset = 0) => {
    if (!ws || !isConnected) return;
    
    ws.send(JSON.stringify({
      type: 'get_messages',
      data: { conversation_id: conversationId, limit, offset }
    }));
  }, [ws, isConnected]);

  // Enviar mensagem
  const sendMessage = useCallback((conversationId, content, userId = null) => {
    if (!ws || !isConnected) return;
    
    ws.send(JSON.stringify({
      type: 'send_message',
      data: { 
        conversation_id: conversationId, 
        content,
        user_id: userId  // Incluir user_id quando disponível
      }
    }));
  }, [ws, isConnected]);

  // Monitorar conversas
  const subscribeConversations = useCallback((conversationIds = []) => {
    if (!ws || !isConnected) return;
    
    ws.send(JSON.stringify({
      type: 'subscribe_conversations',
      data: { conversation_ids: conversationIds }
    }));
  }, [ws, isConnected]);

  return {
    isConnected,
    messages,
    getMessages,
    sendMessage,
    subscribeConversations
  };
};
```

### **Uso do Hook**
```javascript
function ChatApp() {
  const { isConnected, messages, getMessages, sendMessage, subscribeConversations } = 
    useWebSocket('wss://atendimento.pluggerbi.com/ws', userToken);

  useEffect(() => {
    if (isConnected) {
      // Monitorar todas as conversas
      subscribeConversations();
    }
  }, [isConnected, subscribeConversations]);

  const handleSendMessage = (conversationId, text) => {
    sendMessage(conversationId, text);
  };

  const handleLoadMessages = (conversationId) => {
    getMessages(conversationId, 50, 0);
  };

  return (
    <div>
      <div>Status: {isConnected ? '🟢 Conectado' : '🔴 Desconectado'}</div>
      {/* Renderizar conversas e mensagens */}
    </div>
  );
}
```

---

## 📊 **Estrutura de Dados**

### **Campos Padronizados da Mensagem**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | ID único da mensagem |
| `conversation_id` | number | ID da conversa (CRÍTICO para agrupamento) |
| `content` | string | Conteúdo da mensagem |
| `sender` | string | `customer`\|`agent`\|`ai` |
| `timestamp` | string | ISO 8601 format |
| `channel` | string | Sempre `whatsapp` |
| `message_type` | string | `text`\|`image`\|`document`\|`audio` |
| `tokens` | number | Tokens usados (se IA) |
| `metadata` | object | Informações adicionais |

### **Campos da Conversa (subscription_updated)** 
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | number | ID único da conversa |
| `customer_name` | string | Nome do cliente |
| `channel` | string | Sempre `whatsapp` |
| `status` | string | `ai`\|`human`\|`waiting` - Status normalizado do atendimento |
| `conversation_status` | string | **NOVO**: `active`\|`closed` - Status original do banco |
| `created_at` | string | ISO 8601 format |
| `updated_at` | string | ISO 8601 format |
| `last_message` | string | Última mensagem |
| `unread_count` | number | Mensagens não lidas (atualmente sempre 0) |
| `metadata` | object | Informações adicionais (contato, canal, bot, estatísticas) |

### **Resposta get_messages**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `messages` | array | Array de mensagens da conversa |
| `conversation_status` | string | `active`\|`closed` - Status da conversa no banco |
| `pagination` | object | Informações de paginação |

### **📝 Campos de Status Disponíveis**

- **`status`**: Status normalizado (`ai|human|waiting`) - quem está atendendo
- **`conversation_status`**: Status do banco (`active|closed`) - estado da conversa

**Ambos os campos estão disponíveis em:**
- ✅ `subscription_updated` (quando busca todas as conversas)
- ✅ `get_messages` (ao buscar mensagens específicas)

---

## ⚠️ **Tratamento de Erros**

### **Erros Comuns**
- `Token não fornecido` - Faltou token na autenticação
- `conversation_id é obrigatório` - Parâmetro obrigatório não enviado
- `Parâmetros inválidos` - Tipos de dados incorretos
- `Falha ao salvar mensagem` - Erro interno no servidor

### **Reconexão Automática**
```javascript
const connectWithRetry = () => {
  const connect = () => {
    const ws = new WebSocket(url);
    
    ws.onclose = () => {
      console.log('Reconectando em 3s...');
      setTimeout(connect, 3000);
    };
    
    // ... resto da implementação
  };
  
  connect();
};
```

---

## 🚀 **Melhores Práticas**

1. **✅ Sempre incluir `conversation_id`** em todas as operações
2. **✅ Implementar reconexão automática**
3. **✅ Enviar ping a cada 30s** para manter conexão
4. **✅ Tratar todos os tipos de evento** recebidos
5. **✅ Validar dados** antes de enviar
6. **✅ Usar paginação** para histórico de mensagens
7. **✅ Implementar loading states** durante operações

---

## 📞 **Suporte**

Para dúvidas ou problemas:
- Verificar logs do console do navegador
- Conferir se o token JWT está válido
- Testar conectividade WebSocket
- Validar formato dos dados enviados

**Status da conexão:** O campo `isConnected` indica se o WebSocket está ativo e autenticado.
