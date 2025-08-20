# 🔄 Sistema de Renovação Automática de Tokens WhatsApp

## 📋 **Problema Resolvido**

O sistema anterior exigia **renovação manual** dos tokens WhatsApp, causando:
- ❌ Interrupção do serviço quando tokens expiravam
- ❌ Necessidade de intervenção manual frequente
- ❌ Risco de sistema offline sem aviso

## ✅ **Solução Implementada**

Sistema **100% automático** que:
- ✅ **Detecta expiração** antes que aconteça (24h de antecedência)
- ✅ **Renova automaticamente** tokens de longa duração (60 dias)
- ✅ **Converte tokens curtos** para longa duração automaticamente
- ✅ **Monitora continuamente** o status dos tokens
- ✅ **Alerta em caso de falha** para intervenção manual

---

## 🚀 **Como Funciona**

### **1. Tokens de Longa Duração**
```
Token curto (1 hora) → Token longo (60 dias) → Renovação automática
```

### **2. Verificação Automática**
```
A cada hora → Verifica se token expira em < 24h → Se sim, renova
```

### **3. Processo de Renovação**
```
Token atual → API Facebook → Novo token (60 dias) → Salva no banco
```

---

## 🔧 **Configuração Inicial**

### **Passo 1: Fazer primeira autorização OAuth**
```bash
# Acessar no navegador
http://localhost:8080/bot/oauth/start

# Autorizar no Facebook
# Sistema automaticamente converte para token de longa duração
```

### **Passo 2: Configurar automação**
```bash
# Executar script de setup
./setup_token_automation.sh

# Escolher opção 1 (Cron Job) ou 2 (Serviço systemd)
```

### **Passo 3: Verificar funcionamento**
```bash
# Verificar status do token
curl http://localhost:8080/bot/token/status

# Exemplo de resposta:
{
  "status": "valid",
  "expires_in_hours": 1438.2,
  "is_long_lived": true,
  "message": "Token válido por mais 1438.2 horas"
}
```

---

## 📊 **Monitoramento e Controle**

### **APIs Disponíveis**

#### **1. Verificar Status do Token**
```bash
GET /bot/token/status
```
**Resposta:**
```json
{
  "status": "valid|expired|not_found",
  "expires_at": "2025-01-15T10:30:00",
  "expires_in_hours": 1438.2,
  "is_long_lived": true,
  "message": "Token válido por mais 1438.2 horas"
}
```

#### **2. Forçar Renovação**
```bash
POST /bot/token/refresh
```
**Resposta:**
```json
{
  "success": true,
  "message": "Token verificado/renovado com sucesso",
  "token_status": { ... }
}
```

#### **3. Status Geral do Bot**
```bash
GET /bot/status
```
**Resposta:**
```json
{
  "status": "ready",
  "whatsapp_authorized": true,
  "chatgpt_configured": true,
  "ready": true
}
```

---

## 🛠️ **Opções de Automação**

### **Opção 1: Cron Job (Recomendado)**
```bash
# Verificação a cada hora
0 * * * * cd /home/repo/whatsapp && python3 token_auto_renewal.py --once

# Configurar automaticamente
./setup_token_automation.sh
# Escolher opção 1
```

### **Opção 2: Serviço systemd**
```bash
# Execução contínua em background
sudo systemctl start whatsapp-token-renewal
sudo systemctl enable whatsapp-token-renewal

# Configurar automaticamente
./setup_token_automation.sh
# Escolher opção 2
```

### **Opção 3: Script Manual**
```bash
# Executar verificação uma vez
python3 token_auto_renewal.py --once

# Executar verificação contínua
python3 token_auto_renewal.py --continuous

# Ver status
python3 token_auto_renewal.py --status
```

---

## 📄 **Logs e Monitoramento**

### **Arquivo de Log**
```bash
# Ver logs em tempo real
tail -f /tmp/token_renewal.log

# Ver últimas 50 linhas
tail -50 /tmp/token_renewal.log
```

### **Exemplo de Logs**
```
2025-01-12 15:30:00 - __main__ - INFO - 🔄 Iniciando verificação automática de token...
2025-01-12 15:30:01 - __main__ - INFO - Status do token: valid
2025-01-12 15:30:01 - __main__ - INFO - Mensagem: Token válido por mais 1438.2 horas
2025-01-12 15:30:01 - __main__ - INFO - ✅ Token válido por mais 1438.2 horas
2025-01-12 15:30:01 - __main__ - INFO - ✅ Verificação concluída com sucesso
```

---

## 🚨 **Tratamento de Erros**

### **Cenário 1: Token Expira e Não Consegue Renovar**
```bash
# Log mostrará:
❌ Falha ao renovar token automaticamente
❌ Token expirado - autorização OAuth necessária

# Solução:
http://localhost:8080/bot/oauth/start
# Fazer nova autorização manual
```

### **Cenário 2: Problema de Conectividade**
```bash
# Log mostrará:
❌ Erro na verificação automática: HTTPSConnectionPool...

# Sistema tentará novamente em 5 minutos
⏰ Aguardando 5 minutos antes de tentar novamente...
```

### **Cenário 3: Banco de Dados Inacessível**
```bash
# Log mostrará:
❌ Erro ao verificar status do token: database connection failed

# Verificar conexão com MySQL
```

---

## 🎯 **Comandos Úteis**

### **Verificação Rápida**
```bash
# Status do token
curl http://localhost:8080/bot/token/status

# Status geral do bot
curl http://localhost:8080/bot/status

# Forçar renovação
curl -X POST http://localhost:8080/bot/token/refresh
```

### **Gerenciamento de Automação**
```bash
# Ver cron jobs ativos
crontab -l

# Editar cron jobs
crontab -e

# Status do serviço systemd
sudo systemctl status whatsapp-token-renewal

# Logs do serviço systemd
sudo journalctl -u whatsapp-token-renewal -f
```

---

## 📈 **Vantagens do Sistema**

### **✅ Disponibilidade 24/7**
- Sistema nunca para por token expirado
- Renovação automática sem intervenção

### **✅ Tokens de Longa Duração**
- 60 dias de validade vs 1 hora antes
- Reduz drasticamente frequência de renovação

### **✅ Monitoramento Proativo**
- Renova com 24h de antecedência
- Logs detalhados para troubleshooting

### **✅ Múltiplas Opções de Automação**
- Cron job para verificação periódica
- Serviço systemd para execução contínua
- APIs para integração com outros sistemas

### **✅ Recuperação Automática**
- Detecta falhas de conectividade
- Retry automático em caso de erro
- Fallback para autorização manual

---

## 🎊 **Resultado Final**

**Antes**: 
- ❌ Sistema parava quando token expirava
- ❌ Precisava renovar manualmente a cada hora
- ❌ Sem monitoramento

**Agora**:
- ✅ **Sistema nunca para** - renovação automática
- ✅ **Tokens duram 60 dias** - longa duração
- ✅ **Monitoramento completo** - logs e APIs
- ✅ **Zero intervenção manual** - tudo automático

**Seu bot ChatGPT WhatsApp agora funciona 24/7 sem precisar de manutenção de tokens!** 🚀 