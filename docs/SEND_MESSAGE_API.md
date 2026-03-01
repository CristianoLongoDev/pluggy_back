# API de Envio de Mensagens de Agentes Humanos

Esta API permite que agentes humanos enviem mensagens para conversas que serão automaticamente entregues aos usuários via canal (WhatsApp).

## **Endpoint**

```
POST /conversations/{conversation_id}/send-message
```

## **Autenticação**

Requer token JWT no header:
```
Authorization: Bearer <jwt_token>
```

## **Parâmetros**

### **URL Parameters**
- `conversation_id` (int): ID da conversa onde a mensagem será enviada

### **Request Body (JSON)**
```json
{
  "content": "Olá! Como posso ajudar você hoje?",
  "sender": "human",
  "user_id": "user-uuid-12345"  // Opcional: ID do usuário que está enviando
}
```

#### **Campos obrigatórios:**
- `content` (string): Conteúdo da mensagem (não pode estar vazio)
- `sender` (string): Tipo do remetente (`human` ou `agent`)

#### **Campos opcionais:**
- `user_id` (string): UUID do usuário que está enviando a mensagem (para auditoria)

## **Responses**

### **✅ Sucesso (200)**
```json
{
  "success": true,
  "message": "Mensagem enviada com sucesso",
  "data": {
    "message_id": 12345,
    "conversation_id": 789,
    "sent_to_channel": true,
    "channel_type": "whatsapp"
  },
  "status": "success"
}
```

### **⚠️ Erro parcial (500)**
Mensagem salva no banco mas não enviada para o canal:
```json
{
  "success": false,
  "error": "Mensagem salva no banco mas falha ao enviar para WhatsApp",
  "data": {
    "message_id": 12345,
    "conversation_id": 789,
    "sent_to_channel": false
  },
  "status": "error"
}
```

### **❌ Erros (400/401/403/404)**

#### **Parâmetros inválidos (400)**
```json
{
  "success": false,
  "error": "Campo 'content' é obrigatório e não pode estar vazio"
}
```

```json
{
  "success": false,
  "error": "Campo 'sender' é obrigatório"
}
```

#### **Não autorizado (401)**
```json
{
  "success": false,
  "error": "account_id não encontrado no token"
}
```

#### **Não permitido (403)**
```json
{
  "success": false,
  "error": "Conversa não pertence ao account do usuário"
}
```

#### **Não encontrado (404)**
```json
{
  "success": false,
  "error": "Conversa não encontrada"
}
```

## **Comportamento**

### **Fluxo da API**
1. **Validação**: Verifica parâmetros, autenticação e permissões
2. **Salvar no banco**: Insere mensagem na tabela `conversation_message` 
3. **Enviar para canal**: Envia mensagem via WhatsApp com prefixo do agente
4. **Notificação**: Notifica outros clientes WebSocket conectados
5. **Resposta**: Retorna status do envio

### **Prefixo automático**
- A mensagem será enviada via WhatsApp com prefixo: `*{agent_name}:*\nConteúdo`
- O `agent_name` é obtido automaticamente do bot configurado no canal
- Se não houver `agent_name`, usa fallback: `*Plugger Assistente:*`

### **Segurança**
- Verifica se a conversa pertence ao account do usuário autenticado
- Usa JWT para autenticação e autorização
- Valida propriedade da conversa via `contacts.account_id`

### **Campos salvos no banco**
```sql
INSERT INTO conversation_message (
  conversation_id,
  message_text,      -- Conteúdo sem prefixo
  sender,            -- Valor enviado pelo frontend ('human' ou 'agent')
  message_type,      -- 'text'
  timestamp,         -- Timestamp atual
  user_id            -- UUID do usuário (opcional)
)
```

## **Exemplo de uso**

### **cURL**
```bash
curl -X POST "https://atendimento.pluggerbi.com/conversations/123/send-message" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Olá! Recebi sua solicitação e vou analisar o problema.",
    "sender": "human",
    "user_id": "user-uuid-12345"
  }'
```

### **JavaScript**
```javascript
const response = await fetch('/conversations/123/send-message', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    content: 'Olá! Como posso ajudar você hoje?',
    sender: 'human',
    user_id: 'user-uuid-12345'
  })
});

const result = await response.json();
if (result.success) {
  console.log('Mensagem enviada:', result.data);
} else {
  console.error('Erro:', result.error);
}
```

## **Integração com frontend**

O frontend pode usar este endpoint no lugar do WebSocket `send_message` quando precisar de garantia de entrega para o canal:

```javascript
// Ao invés de:
ws.send(JSON.stringify({
  type: 'send_message',
  data: { conversation_id: 123, content: 'Olá!' }
}));

// Usar:
await sendMessageToChannel(123, 'Olá!', userUuid);
```

## **Logs e debug**

A API gera logs detalhados para auditoria:
- `✅ Mensagem enviada via WhatsApp para {phone}`
- `❌ Falha ao enviar mensagem via WhatsApp para {phone}`
- `⚠️ Erro ao buscar agent_name: {error}`

## **Limitações**

- Apenas mensagens de texto são suportadas
- Conversa deve ter um contato com `whatsapp_phone_number` válido
- Requer canal WhatsApp configurado e ativo
- O prefixo é adicionado automaticamente (não pode ser personalizado por mensagem)
