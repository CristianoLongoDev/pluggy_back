# Sistema de Timeout de Conversas

Sistema automático para detectar conversas inativas e dar seguimento pela IA após 1 hora sem resposta do usuário.

## 🎯 **Objetivo**

Quando um usuário não responde por 1 hora após o bot fazer uma pergunta, o sistema automaticamente:
1. **Registra** uma mensagem interna de timeout (não enviada ao usuário)
2. **Envia o contexto** para a IA dar seguimento/encerramento automático

## 🔧 **Como funciona**

### **Fluxo automático:**

```
Usuário envia mensagem → Agenda timeout de 1h → (1h depois) → Verifica inatividade → Salva mensagem → IA processa
```

### **Detalhes técnicos:**

#### **1. Agendamento do timeout**
- **Quando**: A cada mensagem do usuário
- **Duração**: 3600 segundos (1 hora)  
- **Cancelamento**: Se usuário enviar nova mensagem, o timeout anterior é automaticamente cancelado pela verificação

#### **2. Verificação de timeout**
- **Validações**:
  - Conversa ainda está ativa (`status = 'active'`)
  - Última mensagem do usuário foi há mais de 59 minutos
  - Conversa ainda existe
- **Cancelamento automático**: Se usuário respondeu recentemente

#### **3. Processamento do timeout**
- **Mensagem salva**: `"Se passaram 60 minutos sem resposta do usuário. Fica entendido que usuário não tem mais nada a acrescentar."`
- **Tipo**: `sender = 'system'` (mensagem interna)
- **Não enviada**: Apenas registrada no banco, não vai para WhatsApp
- **IA acionada**: Sistema envia contexto completo para IA dar seguimento

## 🏗️ **Arquitetura**

### **Componentes utilizados:**
- **RabbitMQ**: Fila de delay para agendamento
- **ChatGPTDelayWorker**: Processa timeouts agendados  
- **WebhookWorker**: Lógica de processamento
- **Database**: Armazena mensagens de timeout

### **Fluxo de dados:**
```
webhook_worker.py:
  _process_single_message() → _schedule_conversation_timeout()
                                      ↓
                             RabbitMQ (delay 1h)
                                      ↓
chatgpt_delay_worker.py:
  callback() → process conversation_timeout
                      ↓  
webhook_worker.py:
  _process_conversation_timeout() → salva mensagem → chama IA
```

## 📋 **Implementação**

### **Código principal:**

#### **1. Agendamento (webhook_worker.py)**
```python
def _schedule_conversation_timeout(self, contact_id):
    """Agenda timeout de 1 hora para conversas inativas"""
    conversation = db_manager.get_active_conversation(contact_id)
    if not conversation:
        return
    
    timeout_task = {
        'task_type': 'conversation_timeout',
        'contact_id': contact_id,
        'conversation_id': conversation['id'],
        'created_at': time.time(),
        'timeout_duration': 3600  # 1 hora
    }
    
    # Enviar para fila de delay
    rabbitmq_manager.publish_with_delay(timeout_task, delay_seconds=3600)
```

#### **2. Processamento (webhook_worker.py)**
```python
def _process_conversation_timeout(self, event_data):
    """Processa timeout de conversa (1h sem resposta)"""
    # Verificar se conversa ainda está ativa
    # Verificar se não houve mensagens recentes
    # Salvar mensagem de timeout (NÃO enviar ao usuário)
    # Enviar para IA processar
    
    timeout_message = "Se passaram 60 minutos sem resposta do usuário..."
    
    db_manager.insert_conversation_message(
        conversation_id=conversation_id,
        message_text=timeout_message,
        sender='system',
        notify_websocket=False  # Mensagem interna
    )
    
    # IA processa contexto atualizado
    self._process_chatgpt_with_conversation_config(contact_id, conversation_id)
```

## 🛡️ **Proteções implementadas**

### **Cancelamento automático:**
- **Nova mensagem do usuário**: Se usuário responder antes do timeout, a verificação detecta e cancela
- **Conversa encerrada**: Se conversa foi fechada manualmente
- **Conversa inexistente**: Se conversa foi deletada

### **Verificações de segurança:**
```python
# Verificar se conversa ainda ativa
if conversation.get('status') != 'active':
    return  # Cancelar timeout

# Verificar mensagens recentes  
time_diff = current_time - last_timestamp
if time_diff < (timeout_duration - 60):  # Margem de 1 minuto
    return  # Cancelar - usuário respondeu
```

## 📊 **Logs e monitoramento**

### **Logs principais:**
```
⏰ Timeout de 1h agendado para conversa 123 (contato 456)
⏰ Processando timeout de conversa 123 (contato 456)
❌ Timeout cancelado - usuário enviou mensagem há 25.5 min
💾 Mensagem de timeout salva: ID 789
🤖 Enviando contexto para IA dar seguimento à conversa 123
✅ IA processou timeout com sucesso para conversa 123
```

### **Possíveis erros:**
```
❌ Falha ao agendar timeout para conversa 123
❌ Conversa 123 não encontrada - timeout cancelado
❌ Erro ao processar timeout com IA: {error}
```

## ⚙️ **Configuração**

### **Parâmetros ajustáveis:**
```python
# Duração do timeout (segundos)
timeout_duration = 3600  # 1 hora

# Margem de segurança para cancelamento  
safety_margin = 60  # 1 minuto

# Texto da mensagem de timeout
timeout_message = "Se passaram {minutes} minutos sem resposta..."
```

### **Variáveis de ambiente:**
- `RABBITMQ_ENABLED`: Deve estar `True`
- `CHATGPT_DELAY_QUEUE`: Fila para processamento

## 🔄 **Integração com sistema existente**

### **Compatibilidade:**
- ✅ **Funciona com**: Sistema de delay do ChatGPT (10s)
- ✅ **Usa infraestrutura**: RabbitMQ, workers, database existentes
- ✅ **Não interfere**: Em mensagens normais ou fluxo de atendimento humano

### **Coexistência:**
- **Delay de 10s**: Para evitar spam de mensagens
- **Timeout de 1h**: Para inatividade prolongada
- **Ambos funcionam juntos** sem interferência

## 🚀 **Deploy**

### **Arquivos alterados:**
- `webhook_worker.py`: Agendamento e processamento
- `chatgpt_delay_worker.py`: Processamento na fila delay

### **Deploy necessário:**
```bash
# Aplicar alterações
kubectl apply -f k8s/configmap.yaml

# Reiniciar workers
kubectl rollout restart deployment/whatsapp-webhook -n whatsapp-webhook
kubectl rollout restart deployment/chatgpt-delay-worker -n whatsapp-webhook

# Verificar funcionamento
kubectl logs -f deployment/chatgpt-delay-worker -n whatsapp-webhook
```

## 📈 **Benefícios**

### **Para o negócio:**
- ✅ **Zero abandono**: Conversas sempre têm fechamento
- ✅ **Experiência melhor**: IA conclui atendimentos pendentes
- ✅ **Automação**: Reduz intervenção manual

### **Para a tecnologia:**
- ✅ **Escalável**: Usa infraestrutura assíncrona
- ✅ **Confiável**: Múltiplas validações e cancelamentos
- ✅ **Observável**: Logs detalhados para monitoramento
- ✅ **Eficiente**: Reutiliza workers existentes

## 🔍 **Exemplo prático**

### **Cenário:**
1. **14:00** - Bot pergunta: "Precisa de mais alguma coisa?"
2. **14:05** - Usuário não responde
3. **15:00** - Sistema agenda timeout para 15:00
4. **15:00** - Timeout executado:
   - Salva: "Se passaram 60 minutos sem resposta..."
   - IA recebe contexto e responde: "Vou entender que está tudo resolvido. Obrigado!"
   - Conversa pode ser encerrada automaticamente

### **Logs correspondentes:**
```
14:05:23 ⏰ Timeout de 1h agendado para conversa 789 (contato 123)
15:05:23 ⏰ Processando timeout de conversa 789 (contato 123)  
15:05:24 💾 Mensagem de timeout salva: ID 1001
15:05:25 🤖 Enviando contexto para IA dar seguimento à conversa 789
15:05:27 ✅ IA processou timeout com sucesso para conversa 789
```

**Sistema implementado com sucesso! Conversas nunca mais ficarão "perdidas" por inatividade.** 🎉
