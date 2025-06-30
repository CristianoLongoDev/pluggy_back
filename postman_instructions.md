# 🧪 Testes do Webhook no Postman

## 📋 Configuração Inicial

### 1. **Variáveis de Ambiente**
No Postman, crie uma variável de ambiente:
- **Variable**: `base_url`
- **Value**: `https://atendimento.pluggerbi.com` (produção)
- **Value**: `http://localhost:5000` (local)

---

## 🔗 Endpoints para Testar

### 1. **Health Check**
```
GET {{base_url}}/health
```

### 2. **Verificação do Webhook (GET)**
```
GET {{base_url}}/webhook?hub.mode=subscribe&hub.verify_token=seu_token_de_verificacao_aqui&hub.challenge=test_challenge_123
```

### 3. **Mensagem de Texto (POST)**
```
POST {{base_url}}/webhook
Content-Type: application/json

{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "123456789",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "5511999999999",
              "phone_number_id": "987654321"
            },
            "contacts": [
              {
                "profile": {
                  "name": "João Silva"
                },
                "wa_id": "5511888888888"
              }
            ],
            "messages": [
              {
                "from": "5511888888888",
                "id": "wamid.123456789",
                "timestamp": "1751289207",
                "text": {
                  "body": "Olá! Esta é uma mensagem de teste via Postman."
                },
                "type": "text"
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}
```

### 4. **Status de Entrega (POST)**
```
POST {{base_url}}/webhook
Content-Type: application/json

{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "123456789",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "5511999999999",
              "phone_number_id": "987654321"
            },
            "statuses": [
              {
                "id": "wamid.123456789",
                "status": "delivered",
                "timestamp": "1751289209",
                "recipient_id": "5511888888888"
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}
```

### 5. **Verificar Logs**
```
GET {{base_url}}/logs
```

### 6. **Verificar Logs por Tipo**
```
GET {{base_url}}/logs/message_received
GET {{base_url}}/logs/status_update
GET {{base_url}}/logs/webhook_received
```

---

## 🎯 Passo a Passo no Postman

### 1. **Criar Nova Coleção**
- Clique em "Collections" → "New Collection"
- Nome: "WhatsApp Webhook Tests"

### 2. **Criar Variável de Ambiente**
- Clique em "Environments" → "New Environment"
- Nome: "WhatsApp Webhook"
- Adicione variável: `base_url` = `https://atendimento.pluggerbi.com`

### 3. **Criar Requests**
Para cada endpoint acima, crie um novo request na coleção.

### 4. **Testar Sequência**
1. Health Check
2. Webhook Verification (GET)
3. Mensagem de Texto (POST)
4. Status de Entrega (POST)
5. Verificar Logs

---

## ✅ Respostas Esperadas

### **Health Check**
```json
{
  "status": "healthy",
  "message": "API está funcionando!",
  "database_status": "connected"
}
```

### **Webhook Verification**
```
test_challenge_123
```

### **Webhook POST**
```json
{
  "status": "success"
}
```

### **Logs**
```json
{
  "status": "success",
  "count": 5,
  "logs": [...]
}
```

---

## 🔧 Dicas

1. **Use variáveis** para facilitar mudanças entre local/produção
2. **Teste a sequência** completa para verificar o fluxo
3. **Verifique os logs** após cada teste
4. **Monitore os logs** da aplicação para debug

---

## 🚀 Próximos Passos

1. Configure o webhook na Meta (WhatsApp Business API)
2. Teste com mensagens reais do WhatsApp
3. Implemente lógica de negócio nas funções `process_message()` e `process_status()` 