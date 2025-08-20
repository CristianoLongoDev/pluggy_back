# API de Encerramento de Conversas

Esta API permite que usuários do frontend encerrem conversas, definindo `conversation.status = 'closed'` e `ended_at`.

## **Endpoint**

```
PUT /conversations/{conversation_id}/close
```

## **Autenticação**

Requer token JWT no header:
```
Authorization: Bearer <jwt_token>
```

## **Parâmetros**

### **URL Parameters**
- `conversation_id` (int): ID da conversa a ser encerrada

### **Request Body (JSON) - Opcional**
```json
{
  "user_id": "user-uuid-12345"
}
```

#### **Todos os campos são opcionais:**
- `user_id` (string): UUID do usuário que está encerrando (para auditoria)

## **Responses**

### **✅ Sucesso - Conversa encerrada (200)**
```json
{
  "success": true,
  "message": "Conversa encerrada com sucesso",
  "data": {
    "conversation_id": 123,
    "status": "closed",
    "ended_at": "2024-01-15T14:30:00.000Z",
    "closed_by_user_id": "user-uuid-12345"
  },
  "status": "success"
}
```

### **✅ Sucesso - Já estava encerrada (200)**
```json
{
  "success": true,
  "message": "Conversa já está encerrada",
  "data": {
    "conversation_id": 123,
    "status": "closed",
    "already_closed": true,
    "ended_at": "2024-01-15T10:00:00.000Z"
  },
  "status": "success"
}
```

### **❌ Erros (400/401/403/404/500)**

#### **Parâmetros inválidos (400)**
```json
{
  "success": false,
  "error": "conversation_id deve ser um número inteiro"
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

#### **Erro interno (500)**
```json
{
  "success": false,
  "error": "Falha ao encerrar conversa no banco de dados",
  "status": "error"
}
```

## **Comportamento**

### **Fluxo da API**
1. **Validação**: Verifica parâmetros, autenticação e permissões
2. **Verificação**: Checa se conversa já está encerrada (retorna sucesso se sim)
3. **Encerramento**: Executa `UPDATE conversation SET status = 'closed', ended_at = NOW()`
4. **Auditoria**: Registra log com usuário que encerrou

### **Alterações no banco**
```sql
-- Apenas altera o status da conversa
UPDATE conversation 
SET status = 'closed', ended_at = NOW() 
WHERE id = {conversation_id};
```

### **Segurança**
- Verifica se a conversa pertence ao account do usuário autenticado
- Usa JWT para autenticação e autorização
- Valida propriedade da conversa via `contacts.account_id`
- Permite encerrar conversas múltiplas vezes (idempotente)

### **Notificações WebSocket**
- Outros clientes conectados são notificados automaticamente sobre mudança de status
- Status da conversa é atualizado em tempo real no frontend

## **Exemplo de uso**

### **cURL - Com user_id**
```bash
curl -X PUT "https://atendimento.pluggerbi.com/conversations/123/close" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-uuid-12345"
  }'
```

### **cURL - Simples**
```bash
curl -X PUT "https://atendimento.pluggerbi.com/conversations/123/close" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```

### **JavaScript**
```javascript
// Com user_id para auditoria
const closeConversationWithUserId = async (conversationId, userId) => {
  const response = await fetch(`/conversations/${conversationId}/close`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      user_id: userId
    })
  });

  const result = await response.json();
  if (result.success) {
    console.log('Conversa encerrada:', result.data);
  } else {
    console.error('Erro:', result.error);
  }
};

// Simples
const closeConversation = async (conversationId) => {
  const response = await fetch(`/conversations/${conversationId}/close`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  return await response.json();
};
```

## **Integração com frontend**

### **Botão de encerramento**
```javascript
const handleCloseConversation = async () => {
  try {
    const result = await closeConversationWithUserId(
      currentConversationId, 
      currentUserId
    );
    
    if (result.success) {
      // Atualizar UI para mostrar conversa encerrada
      updateConversationStatus(currentConversationId, 'closed');
      showNotification('Conversa encerrada com sucesso');
    } else {
      showError(result.error);
    }
  } catch (error) {
    showError('Erro ao encerrar conversa');
  }
};
```

### **Estado da conversa no frontend**
```javascript
// O WebSocket receberá automaticamente:
// Status atualizado da conversa via subscription_updated

// Implementar handler para status "closed"
const handleConversationClosed = (conversationId) => {
  // Desabilitar input de mensagens
  setInputDisabled(true);
  
  // Mostrar badge "Encerrada"
  setConversationStatus(conversationId, 'closed');
  
  // Opcional: Mover para seção "Conversas encerradas"
  moveToClosedSection(conversationId);
};
```

## **Logs e auditoria**

A API gera logs detalhados para auditoria:
- `🔚 CONVERSA ENCERRADA - ID: 123, User: user@email.com, User ID: user-uuid-12345`
- `❌ Falha ao encerrar conversa 123: {error}`

## **Considerações importantes**

### **Idempotência**
- Encerrar uma conversa já encerrada retorna sucesso (200)
- Não gera erro, apenas informa que já estava encerrada
- Útil para evitar problemas em interfaces com múltiplos cliques

### **Reversibilidade**
- O endpoint apenas fecha conversas (`status = 'closed'`)
- Para reabrir, use o endpoint de status: `PUT /conversations/{id}/status`
- Ou implemente endpoint específico de reabertura se necessário

### **Comportamento simplificado**
- Apenas altera o status da conversa para `closed`
- Define `ended_at` com timestamp atual
- **Não cria mensagens** - apenas atualiza status

### **Diferença dos endpoints**
- `/conversations/{id}/status` → Altera `status_attendance` (bot/human)
- `/conversations/{id}/close` → Altera `status` (active/closed) + `ended_at`
