#!/bin/bash

# Script completo para build, push para Docker Hub e deploy do webhook worker otimizado

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

echo ""
log_info "📊 Deletando pod:"
kubectl delete pod -n whatsapp-webhook -l app=webhook-worker-optimized
kubectl delete pod -n whatsapp-webhook -l app=message-worker-optimized

# Etapa 6: Verificar status
log_info "🔍 Verificando status dos pods..."
sleep 5

echo ""
log_info "📊 Status dos deployments:"
kubectl get deployments -n whatsapp-webhook -l version=optimized

echo ""
log_info "📋 Status dos pods:"
kubectl get pods -n whatsapp-webhook -l version=optimized

echo ""
log_info "📜 Eventos recentes:"
kubectl get events -n whatsapp-webhook --sort-by='.lastTimestamp' | tail -5

# Limpeza
rm -f "${TEMP_DEPLOYMENT}"

echo ""
log_success "🎉 Deploy completo finalizado!"
log_info "📋 Comandos úteis para monitoramento:"
echo "   kubectl logs -n whatsapp-webhook -l app=webhook-worker-optimized -f"
echo "   kubectl top pods -n whatsapp-webhook -l version=optimized"
echo "   kubectl describe deployment webhook-worker-optimized -n whatsapp-webhook" 