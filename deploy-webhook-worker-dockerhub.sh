#!/bin/bash

# Script completo para build, push para Docker Hub e deploy do webhook worker otimizado
# AGORA INCLUI: Outbox Pattern + Arquitetura Particionada (Fase 2)
#
# Uso:
#   ./deploy-webhook-worker-dockerhub.sh [TAG] [DEPLOY_PARTITIONED]
#
# Exemplos:
#   ./deploy-webhook-worker-dockerhub.sh                    # latest + particionado
#   ./deploy-webhook-worker-dockerhub.sh latest            # latest + particionado  
#   ./deploy-webhook-worker-dockerhub.sh v1.2 true         # v1.2 + particionado
#   ./deploy-webhook-worker-dockerhub.sh latest false      # latest sem particionado
#
# Componentes deployados automaticamente:
#   ✅ Webhook Worker (workers originais)
#   ✅ Outbox Publisher (transações atômicas)
#   ✅ Partitioned Workers (4 partições para escalabilidade)

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

# Definir usuário Docker Hub (mesmo usado nos outros scripts)
export DOCKER_HUB_USER="cristianopluggerbi"

# Configurações
IMAGE_NAME="webhook-worker"
TAG="${1:-latest}"
FULL_IMAGE_NAME="${DOCKER_HUB_USER}/${IMAGE_NAME}:${TAG}"
DEPLOYMENT_FILE="k8s/webhook-worker-deployment-optimized.yaml"

log_info "🚀 Iniciando deploy completo do webhook worker otimizado"
log_info "📦 Imagem: ${FULL_IMAGE_NAME}"
log_info "👤 Usuário Docker Hub: ${DOCKER_HUB_USER}"

# === NOVO: DEPLOY AUTOMÁTICO DOS COMPONENTES PARTICIONADOS ===
DEPLOY_PARTITIONED="${2:-true}"  # Por padrão, sempre fazer deploy particionado
OUTBOX_DEPLOYMENT_FILE="k8s/outbox-publisher-deployment.yaml"
PARTITIONED_DEPLOYMENT_FILE="k8s/partitioned-workers-deployment.yaml"

if [ "$DEPLOY_PARTITIONED" = "true" ]; then
    log_info "🎯 Deploy particionado habilitado - incluindo outbox publisher e workers particionados"
fi

# Etapa 1: Verificar login no Docker Hub
log_info "🔐 Verificando login no Docker Hub..."
if ! docker info | grep -q "Username:"; then
    log_warning "Não está logado no Docker Hub. Fazendo login..."
    docker login
fi
log_success "Login no Docker Hub verificado"

# Etapa 2: Construir a imagem
log_info "🔨 Construindo imagem Docker..."
docker build -f Dockerfile.webhook-worker -t "${FULL_IMAGE_NAME}" .
log_success "Imagem construída com sucesso"

# Etapa 3: Fazer push para Docker Hub
log_info "📤 Fazendo push para Docker Hub..."
docker push "${FULL_IMAGE_NAME}"
log_success "Push para Docker Hub concluído"
log_info "🌍 Imagem disponível em: https://hub.docker.com/r/${DOCKER_HUB_USER}/${IMAGE_NAME}"

# Etapa 4: Atualizar deployment com a nova imagem
log_info "📝 Atualizando deployment com a nova imagem..."
TEMP_DEPLOYMENT="/tmp/webhook-worker-deployment-temp.yaml"
cp "${DEPLOYMENT_FILE}" "${TEMP_DEPLOYMENT}"

# Substituir placeholder do usuário no deployment
sed -i "s/seu_usuario_dockerhub/${DOCKER_HUB_USER}/g" "${TEMP_DEPLOYMENT}"
sed -i "s/:latest/:${TAG}/g" "${TEMP_DEPLOYMENT}"

# Etapa 5: Aplicar no Kubernetes
log_info "🚀 Aplicando deployment no Kubernetes..."
kubectl apply -f "${TEMP_DEPLOYMENT}"
log_success "Deployment aplicado no Kubernetes"

# Etapa 6: Deploy dos componentes particionados (se habilitado)
if [ "$DEPLOY_PARTITIONED" = "true" ]; then
    echo ""
    log_info "🎯 Aplicando arquitetura particionada..."
    
    # Deploy do Outbox Publisher
    if [ -f "$OUTBOX_DEPLOYMENT_FILE" ]; then
        log_info "📤 Fazendo deploy do Outbox Publisher..."
        kubectl apply -f "$OUTBOX_DEPLOYMENT_FILE"
        log_success "Outbox Publisher aplicado"
    else
        log_warning "Arquivo $OUTBOX_DEPLOYMENT_FILE não encontrado"
    fi
    
    # Deploy dos Workers Particionados
    if [ -f "$PARTITIONED_DEPLOYMENT_FILE" ]; then
        log_info "🔄 Fazendo deploy dos Workers Particionados..."
        kubectl apply -f "$PARTITIONED_DEPLOYMENT_FILE"
        log_success "Workers Particionados aplicados"
        
        # Escalar apenas 2 workers particionados (0 e 1) - economizar recursos
        log_info "⚖️ Escalando workers particionados para economia de recursos..."
        kubectl scale deployment partitioned-msg-worker-0 --replicas=1 -n whatsapp-webhook
        kubectl scale deployment partitioned-msg-worker-1 --replicas=1 -n whatsapp-webhook
        kubectl scale deployment partitioned-msg-worker-2 --replicas=1 -n whatsapp-webhook
        kubectl scale deployment partitioned-msg-worker-3 --replicas=1 -n whatsapp-webhook
        log_success "✅ Apenas 2 workers particionados ativos (0 e 1)"
    else
        log_warning "Arquivo $PARTITIONED_DEPLOYMENT_FILE não encontrado"
    fi
    
    # Aguardar um pouco para os pods iniciarem
    log_info "⏱️ Aguardando pods particionados iniciarem..."
    sleep 10
fi

# Etapa 7: Verificar status
log_info "🔍 Verificando status dos pods..."
sleep 5

echo ""
log_info "📊 Status dos deployments originais:"
kubectl get deployments -n whatsapp-webhook -l version=optimized

if [ "$DEPLOY_PARTITIONED" = "true" ]; then
    echo ""
    log_info "📊 Status dos deployments particionados:"
    kubectl get deployments -n whatsapp-webhook -l app=outbox-publisher
    kubectl get deployments -n whatsapp-webhook -l app=partitioned-msg-worker
fi

echo ""
log_info "📋 Status de todos os pods:"
kubectl get pods -n whatsapp-webhook

echo ""
log_info "📜 Eventos recentes:"
kubectl get events -n whatsapp-webhook --sort-by='.lastTimestamp' | tail -10

# Limpeza
rm -f "${TEMP_DEPLOYMENT}"

echo ""
log_info "📊 Deletando pod:"
kubectl delete pod -n whatsapp-webhook -l app=webhook-worker-optimized
kubectl delete pod -n whatsapp-webhook -l app=message-worker-optimized
kubectl delete pod -n whatsapp-webhook -l app=partitioned-msg-worker
kubectl delete pod -n whatsapp-webhook -l app=outbox-publisher

echo ""
log_success "🎉 Deploy completo finalizado!"
log_info "📋 Comandos úteis para monitoramento:"
echo ""
echo "   📱 Workers Originais:"
echo "   kubectl logs -n whatsapp-webhook -l app=webhook-worker-optimized -f"
echo "   kubectl top pods -n whatsapp-webhook -l version=optimized"

if [ "$DEPLOY_PARTITIONED" = "true" ]; then
    echo ""
    echo "   🎯 Arquitetura Particionada (2 workers ativos):"
    echo "   kubectl logs -n whatsapp-webhook -l app=outbox-publisher -f"
    echo "   kubectl logs -n whatsapp-webhook -l app=partitioned-msg-worker -f"
    echo "   kubectl logs -n whatsapp-webhook deployment/partitioned-msg-worker-0 -f"
    echo "   kubectl logs -n whatsapp-webhook deployment/partitioned-msg-worker-1 -f"
    echo "   # Workers 2 e 3 desabilitados para economia de recursos"
    echo ""
    echo "   📊 Monitoramento de Filas (RabbitMQ):"
    echo "   kubectl exec -it deployment/rabbitmq -n whatsapp-webhook -- rabbitmqctl list_queues name messages"
    echo "   kubectl exec -it deployment/rabbitmq -n whatsapp-webhook -- rabbitmqctl list_bindings"
fi

echo ""
echo "   🔍 Geral:"
echo "   kubectl get pods -n whatsapp-webhook -w"
echo "   kubectl describe deployment webhook-worker-optimized -n whatsapp-webhook" 