# 📞 Conversations API - Documentação

## 📋 **Visão Geral**

A API de Conversations permite gerenciar e acessar conversas do sistema de atendimento WhatsApp. Todas as operações requerem autenticação JWT válida e respeitam o isolamento por conta.

**Base URL:** `https://atendimento.pluggerbi.com`

---

## 🔐 **Autenticação**

Todos os endpoints requerem autenticação via JWT no header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

O token JWT deve conter um `account_id` válido para isolamento de dados por conta.

---

## 📡 **Endpoints**

### **GET** `/api/conversations/recent`

Busca as conversas mais recentes da conta com dados completos dos contatos. **Ideal para carregamento inicial do frontend.**

#### **Parâmetros de Query**
- **`limit`** (integer, opcional): Número máximo de conversas a retornar (padrão: 50, máximo: 100)
- **`include_closed`** (boolean, opcional): Incluir conversas encerradas (padrão: true)

#### **Headers Obrigatórios**
```
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

#### **Exemplo de Requisição**
```
GET /api/conversations/recent?limit=50&include_closed=true
```

#### **Resposta de Sucesso (200)**
```json
{
  "status": "success",
  "data": {
    "conversations": [
      {
        "conversation_id": 217,
        "status": "active",
        "status_attendance": "bot",
        "started_at": "2025-09-19T12:29:51",
        "ended_at": null,
        "message_count": 2,
        "last_message": {
          "text": "Olá! Como posso ajudar?",
          "sender": "agent",
          "timestamp": "2025-09-19T12:30:15"
        },
        "contact": {
          "id": "20a09a1b-c84e-4b22-a157-095db6b6fe61",
          "name": "Cristiano",
          "phone": "555496598592",
          "email": "cristiano@pluggerbi.com"
        },
        "channel": {
          "id": "22646f94-0eda-43f6-a79f-6b24669dcdf4",
          "name": "WhatsApp Support",
          "type": "whatsapp"
        },
        "bot": {
          "name": "Gerador Tickets Movidesk",
          "agent_name": "Assistente IA"
        }
      }
    ],
    "pagination": {
      "limit": 50,
      "total": 1,
      "include_closed": true
    },
    "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136"
  }
}
```

---

### **GET** `/conversations/{conversation_id}/messages`

Busca todas as mensagens de uma conversa específica.

#### **Parâmetros da URL**
- **`conversation_id`** (string, obrigatório): UUID da conversa

#### **Parâmetros de Query**
- **`limit`** (integer, opcional): Número máximo de mensagens a retornar (padrão: 50, máximo: 100)

#### **Headers Obrigatórios**
```
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

#### **Resposta de Sucesso (200)**
```json
{
  "status": "success",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    {
      "id": 1,
      "conversation_id": 123,
      "message_text": "Olá! Como posso ajudar?",
      "sender": "user",
      "message_type": "text",
      "timestamp": "2024-01-15T10:30:00",
      "prompt": null,
      "tokens": 0
    },
    {
      "id": 2,
      "conversation_id": 123,
      "message_text": "Preciso de ajuda com meu pedido",
      "sender": "agent",
      "message_type": "text",
      "timestamp": "2024-01-15T10:31:00",
      "prompt": "Você é um assistente de atendimento...",
      "tokens": 25
    }
  ],
  "total": 2,
  "limit": 50
}
```

#### **Resposta de Erro (400)**
```json
{
  "error": "Token JWT não contém account_id válido",
  "status": "error"
}
```

#### **Resposta de Erro (400)**
```json
{
  "error": "conversation_id deve ser um UUID válido",
  "status": "error"
}
```

#### **Resposta de Erro (403)**
```json
{
  "error": "Acesso negado - conversa não pertence à sua conta",
  "status": "error"
}
```

#### **Resposta de Erro (404)**
```json
{
  "error": "Conversa não encontrada",
  "status": "error"
}
```

#### **Resposta de Erro (503)**
```json
{
  "error": "Banco de dados não está habilitado",
  "status": "error"
}
```

---

## 📊 **Estruturas de Dados**

### **Objeto Message**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | integer | ID único da mensagem |
| `conversation_id` | integer | ID da conversa |
| `message_text` | string | Conteúdo da mensagem |
| `sender` | string | `user`\|`agent`\|`bot` - Remetente da mensagem |
| `message_type` | string | `text`\|`image`\|`document`\|`audio` - Tipo da mensagem |
| `timestamp` | string | Data/hora da mensagem (ISO 8601) |
| `prompt` | string\|null | Prompt usado (apenas para mensagens de IA) |
| `tokens` | integer | Tokens consumidos (apenas para mensagens de IA) |

### **Objeto Conversation (Completo)**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `conversation_id` | integer | ID único da conversa |
| `status` | string | `active`\|`closed` - Status da conversa |
| `status_attendance` | string | `bot`\|`agent`\|`user` - Quem está atendendo |
| `started_at` | string | Data/hora de início (ISO 8601) |
| `ended_at` | string\|null | Data/hora de encerramento (ISO 8601) |
| `message_count` | integer | Número total de mensagens na conversa |
| `last_message` | object\|null | Última mensagem da conversa |
| `contact` | object | Dados do contato |
| `channel` | object | Dados do canal |
| `bot` | object\|null | Dados do bot (se houver) |

### **Objeto Last Message**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `text` | string | Texto da última mensagem |
| `sender` | string | `user`\|`agent`\|`bot` - Remetente |
| `timestamp` | string | Data/hora da mensagem (ISO 8601) |

### **Objeto Contact**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | UUID do contato |
| `name` | string | Nome do contato |
| `phone` | string | Número de telefone |
| `email` | string\|null | Email do contato |

### **Objeto Channel**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | UUID do canal |
| `name` | string | Nome do canal |
| `type` | string | Tipo do canal (`whatsapp`, etc.) |

### **Objeto Bot**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `name` | string | Nome do bot |
| `agent_name` | string | Nome do agente virtual |

---

## 🔒 **Segurança e Permissões**

1. **Autenticação JWT**: Todos os endpoints requerem token válido
2. **Isolamento por Conta**: Usuários só podem acessar conversas da própria conta
3. **Validação de UUID**: IDs são validados como UUID v4
4. **Validação de Propriedade**: Verifica se a conversa pertence à conta antes de retornar dados
5. **Logs de Auditoria**: Todos os acessos são registrados
6. **Rate Limiting**: Limitação de requisições para evitar abuso

---

## 📈 **Códigos de Status HTTP**

- **200 OK**: Mensagens listadas com sucesso
- **400 Bad Request**: Dados inválidos ou ausentes / Token JWT sem account_id
- **401 Unauthorized**: Token JWT ausente, inválido ou expirado
- **403 Forbidden**: Acesso negado - conversa não pertence à sua conta
- **404 Not Found**: Conversa não encontrada
- **500 Internal Server Error**: Erro interno do servidor
- **503 Service Unavailable**: Banco de dados não está habilitado

---

## 🎯 **Casos de Uso**

### **Carregamento Inicial do Frontend**
Usar `/api/conversations/recent` para carregar as conversas mais recentes ao abrir a aplicação, incluindo dados completos dos contatos e última mensagem.

### **Visualizar Histórico de Conversa**
Buscar todas as mensagens de uma conversa específica usando `/conversations/{conversation_id}/messages` para exibir o histórico completo.

### **Dashboard de Conversas**
Listar conversas ativas e encerradas com filtros para monitoramento do atendimento.

### **Carregamento Paginado**
Usar o parâmetro `limit` para implementar carregamento em lotes de conversas ou mensagens.

### **Auditoria e Monitoramento**
Acessar conversas e mensagens para fins de auditoria, qualidade do atendimento e análise.

### **Integração com Dashboards**
Extrair dados de conversas para relatórios e métricas de atendimento.

---

## ⚠️ **Limitações**

1. **Máximo de Mensagens**: Limitado a 100 mensagens por requisição
2. **Somente Leitura**: Atualmente não há endpoints para criar/editar mensagens via REST API
3. **Conversas Ativas**: Acesso limitado a conversas da conta autenticada
4. **Ordenação**: Mensagens são retornadas em ordem cronológica (mais antigas primeiro)

---

## 🔗 **APIs Relacionadas**

- **[WebSocket API](WEBSOCKET_API.md)**: Para comunicação em tempo real e envio de mensagens
- **[Channels API](CHANNELS_API.md)**: Para gerenciar canais de atendimento
- **[Bots API](BOTS_API.md)**: Para configurar bots e automações

---

## 📝 **Notas Importantes**

1. **UUIDs**: Todos os IDs de conversa devem ser UUIDs válidos no formato v4
2. **Fuso Horário**: Timestamps são retornados no formato ISO 8601 (UTC)
3. **Paginação**: Para conversas com muitas mensagens, use o parâmetro `limit` para paginar
4. **Performance**: Limite requisições a intervalos razoáveis para melhor performance
5. **Cache**: Considere implementar cache no frontend para mensagens já carregadas

---

## 🚀 **Roadmap**

### **Funcionalidades Implementadas**

- ✅ **GET** `/api/conversations/recent` - Listar conversas recentes com dados completos
- ✅ **GET** `/conversations/{conversation_id}/messages` - Mensagens de uma conversa
- ✅ **POST** `/api/conversations/search` - Busca textual em conversas

### **Próximas Funcionalidades Planejadas**

- **GET** `/conversations/{conversation_id}` - Detalhes de uma conversa específica  
- **PUT** `/conversations/{conversation_id}/status` - Alterar status da conversa
- **POST** `/conversations/{conversation_id}/messages` - Enviar mensagem via REST
- **GET** `/conversations/stats` - Estatísticas de conversas

### **Melhorias Futuras**

- Suporte a filtros avançados (data, status, canal)
- Exportação de conversas em diferentes formatos  
- Suporte a anexos e mídias na resposta
- Cache inteligente de conversas
- Filtros por período de tempo

---

## 🌐 **Integração com WebSocket**

### **Fluxo Recomendado para Frontend**

1. **Carregamento Inicial**: Use `GET /api/conversations/recent` para carregar conversas existentes
2. **Tempo Real**: Conecte ao WebSocket `wss://pluggyapi.pluggerbi.com/ws` para atualizações

### **WebSocket Events Relacionados**

- **`subscription_updated`**: Lista de conversas ativas atualizadas
- **`new_message`**: Nova mensagem em uma conversa existente

### **Estratégia de Sincronização**

```
1. Load da Página → GET /api/conversations/recent
2. WebSocket Connect → wss://pluggyapi.pluggerbi.com/ws  
3. Authenticate → { type: "authenticate", data: { token: jwt } }
4. Subscribe → { type: "subscribe_conversations", data: { conversation_ids: [] } }
5. Receber → subscription_updated (conversas ativas) + new_message (mensagens)
```

### **Vantagens da Abordagem Híbrida**

- ✅ **REST**: Dados completos e estruturados no carregamento
- ✅ **WebSocket**: Atualizações instantâneas em tempo real  
- ✅ **Performance**: Cache local + sincronização eficiente
- ✅ **Confiabilidade**: Fallback para REST se WebSocket falhar
