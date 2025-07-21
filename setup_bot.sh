#!/bin/bash

# Script de setup do Bot ChatGPT WhatsApp

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para logs coloridos
log_info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

API_URL="${1:-http://localhost:8080}"

log_info "🤖 Setup do Bot ChatGPT WhatsApp"
log_info "🌍 API URL: $API_URL"
echo ""

# 1. Verificar se a API está rodando
log_info "1. Verificando se a API está acessível..."
if curl -s "$API_URL/health" > /dev/null; then
    log_success "API está acessível"
else
    log_error "API não está acessível em $API_URL"
    log_info "Execute: kubectl port-forward -n whatsapp-webhook svc/whatsapp-webhook-service 8080:80"
    exit 1
fi

# 2. Verificar status do bot
log_info "2. Verificando status atual do bot..."
BOT_STATUS=$(curl -s "$API_URL/bot/status")
echo "$BOT_STATUS" | python3 -m json.tool 2>/dev/null || echo "$BOT_STATUS"

WHATSAPP_AUTH=$(echo "$BOT_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('whatsapp_authorized', False))" 2>/dev/null || echo "false")
CHATGPT_CONFIG=$(echo "$BOT_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('chatgpt_configured', False))" 2>/dev/null || echo "false")

echo ""

# 3. Configurar System Prompt se não estiver configurado
if [ "$CHATGPT_CONFIG" = "false" ]; then
    log_warning "System Prompt não configurado"
    log_info "3. Configurando System Prompt padrão..."
    
    PROMPT='Você é um assistente virtual amigável e prestativo que trabalha para a Intelectivo Sistemas Estratégicos para atender os clientes que usam o Plugger BI, uma plataforma de business intelligence. Sua função é registrar o atendimento referente o que o usuário deseja. Oriente o usuário a fornecer todos os dados relevantes que possam ajudar a entender o que ele precisa. Responda de forma clara e objetiva em português brasileiro. Mantenha as respostas concisas (máximo 200 caracteres). Não fale sobre outros assuntos que não tenham relação com o Plugger BI ou a Intelectivo.'
    
    RESPONSE=$(curl -s -X POST "$API_URL/bot/config/system-prompt" \
        -H "Content-Type: application/json" \
        -d "{\"content\": \"$PROMPT\"}")
    
    if echo "$RESPONSE" | grep -q "success"; then
        log_success "System Prompt configurado com sucesso"
    else
        log_error "Falha ao configurar System Prompt"
        echo "$RESPONSE"
    fi
else
    log_success "3. System Prompt já está configurado"
fi

echo ""

# 4. Verificar autorização WhatsApp
if [ "$WHATSAPP_AUTH" = "false" ]; then
    log_warning "WhatsApp não autorizado"
    log_info "4. Para autorizar o WhatsApp:"
    echo ""
    echo "   🌐 Acesse: $API_URL/bot/oauth/start"
    echo "   📱 Complete a autorização no Facebook"
    echo "   🔄 Execute este script novamente após autorizar"
    echo ""
else
    log_success "4. WhatsApp já está autorizado"
fi

echo ""

# 5. Status final
log_info "5. Status final do bot..."
FINAL_STATUS=$(curl -s "$API_URL/bot/status")
echo "$FINAL_STATUS" | python3 -m json.tool 2>/dev/null || echo "$FINAL_STATUS"

BOT_READY=$(echo "$FINAL_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('ready', False))" 2>/dev/null || echo "false")

echo ""

if [ "$BOT_READY" = "true" ]; then
    log_success "🎉 Bot está pronto para uso!"
    echo ""
    log_info "📋 Próximos passos:"
    echo "   • Envie uma mensagem de teste para o WhatsApp"
    echo "   • Monitore os logs: kubectl logs -f webhook-worker-xxx"
    echo "   • Veja as conversas: curl $API_URL/logs/by-type/message_received"
    echo ""
else
    log_warning "⚙️ Bot ainda precisa de configuração"
    echo ""
    log_info "📋 Próximos passos:"
    if [ "$CHATGPT_CONFIG" = "false" ]; then
        echo "   • ❌ Configurar System Prompt (execute este script novamente)"
    else
        echo "   • ✅ System Prompt configurado"
    fi
    
    if [ "$WHATSAPP_AUTH" = "false" ]; then
        echo "   • ❌ Autorizar WhatsApp: $API_URL/bot/oauth/start"
    else
        echo "   • ✅ WhatsApp autorizado"
    fi
    echo ""
fi

# 6. Comandos úteis
echo ""
log_info "🔧 Comandos úteis:"
echo "   # Verificar status"
echo "   curl $API_URL/bot/status"
echo ""
echo "   # Ver mensagens recebidas"
echo "   curl $API_URL/logs/by-type/message_received"
echo ""
echo "   # Ver mensagens enviadas"
echo "   curl $API_URL/logs/by-type/message_sent"
echo ""
echo "   # Logs em tempo real"
echo "   kubectl logs -f -n whatsapp-webhook -l app=webhook-worker-optimized"
echo ""

log_success "Setup concluído!"