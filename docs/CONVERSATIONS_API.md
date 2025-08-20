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

### **Objeto Conversation**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | UUID único da conversa |
| `contact_id` | string | UUID do contato |
| `channel_id` | string | UUID do canal |
| `status` | string | `active`\|`closed` - Status da conversa |
| `started_at` | string | Data/hora de início (ISO 8601) |
| `ended_at` | string\|null | Data/hora de encerramento (ISO 8601) |

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

### **Visualizar Histórico de Conversa**
Buscar todas as mensagens de uma conversa para exibir o histórico completo no frontend.

### **Carregamento Paginado**
Usar o parâmetro `limit` para implementar carregamento em lotes de mensagens antigas.

### **Auditoria e Monitoramento**
Acessar mensagens para fins de auditoria, qualidade do atendimento e análise.

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

### **Próximas Funcionalidades Planejadas**

- **GET** `/conversations` - Listar todas as conversas da conta
- **GET** `/conversations/{conversation_id}` - Detalhes de uma conversa específica  
- **PUT** `/conversations/{conversation_id}/status` - Alterar status da conversa
- **POST** `/conversations/{conversation_id}/messages` - Enviar mensagem via REST
- **GET** `/conversations/stats` - Estatísticas de conversas

### **Melhorias Futuras**

- Suporte a filtros avançados (data, status, canal)
- Busca textual dentro das mensagens
- Exportação de conversas em diferentes formatos
- Webhooks para notificações de novas mensagens
- Suporte a anexos e mídias na resposta
