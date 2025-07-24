#!/bin/bash

# Script completo para build e deploy do frontend no Docker Hub e Kubernetes
set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
DOCKER_USERNAME="cristianopluggerbi"
IMAGE_NAME="whatsapp-frontend"
TAG="latest"
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${TAG}"
NAMESPACE="whatsapp-webhook"

echo -e "${BLUE}🚀 DEPLOY COMPLETO DO FRONTEND${NC}"
echo "============================================="
echo "📦 Build da imagem + Deploy no Kubernetes"
echo "🐳 Imagem: ${FULL_IMAGE_NAME}"
echo "🎯 Namespace: ${NAMESPACE}"
echo "============================================="

# Verificar pré-requisitos
echo -e "${YELLOW}🔍 Verificando pré-requisitos...${NC}"

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não encontrado!${NC}"
    exit 1
fi

# Verificar kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl não encontrado!${NC}"
    exit 1
fi

# Verificar arquivo HTML
if [ ! -f "frontend/index.html" ]; then
    echo -e "${RED}❌ frontend/index.html não encontrado!${NC}"
    exit 1
fi

# Verificar Dockerfile
if [ ! -f "Dockerfile.frontend" ]; then
    echo -e "${RED}❌ Dockerfile.frontend não encontrado!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Pré-requisitos verificados${NC}"

# Build da imagem
echo -e "${YELLOW}📦 Construindo imagem Docker...${NC}"
docker build -f Dockerfile.frontend -t "${FULL_IMAGE_NAME}" .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Imagem construída com sucesso!${NC}"
else
    echo -e "${RED}❌ Erro ao construir a imagem!${NC}"
    exit 1
fi

# Verificar login no Docker Hub
echo -e "${YELLOW}🔐 Verificando login no Docker Hub...${NC}"
if ! docker info 2>/dev/null | grep -q "Username: ${DOCKER_USERNAME}"; then
    echo -e "${YELLOW}⚠️ Não está logado no Docker Hub. Fazendo login...${NC}"
    if [ -n "$DOCKER_PASSWORD" ]; then
        echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
    else
        docker login -u "$DOCKER_USERNAME"
    fi
else
    echo -e "${GREEN}✅ Já está logado no Docker Hub como ${DOCKER_USERNAME}${NC}"
fi

# Push da imagem
echo -e "${YELLOW}📤 Fazendo push da imagem...${NC}"
docker push "${FULL_IMAGE_NAME}"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Push realizado com sucesso!${NC}"
else
    echo -e "${RED}❌ Erro ao fazer push da imagem!${NC}"
    exit 1
fi

# Verificar namespace
echo -e "${YELLOW}🔍 Verificando namespace...${NC}"
if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo -e "${YELLOW}📝 Criando namespace ${NAMESPACE}...${NC}"
    kubectl create namespace "${NAMESPACE}"
fi

# Deploy no Kubernetes
echo -e "${YELLOW}🚀 Fazendo deploy no Kubernetes...${NC}"

# Aplicar deployment do frontend
if [ -f "k8s/frontend-deployment.yaml" ]; then
    kubectl apply -f k8s/frontend-deployment.yaml
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Deployment aplicado com sucesso!${NC}"
    else
        echo -e "${RED}❌ Erro ao aplicar deployment!${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ k8s/frontend-deployment.yaml não encontrado!${NC}"
    exit 1
fi

# Aguardar deployment
echo -e "${YELLOW}⏳ Aguardando pod ser criado...${NC}"
sleep 10

# Verificar status do pod
echo -e "${YELLOW}🔍 Verificando status do pod...${NC}"
timeout=120
counter=0

while [ $counter -lt $timeout ]; do
    pod_status=$(kubectl get pods -n "${NAMESPACE}" -l app=whatsapp-frontend -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
    
    if [ "$pod_status" = "Running" ]; then
        echo -e "${GREEN}✅ Pod está rodando!${NC}"
        break
    elif [ "$pod_status" = "Failed" ]; then
        echo -e "${RED}❌ Pod falhou!${NC}"
        kubectl describe pods -n "${NAMESPACE}" -l app=whatsapp-frontend
        exit 1
    else
        echo -e "${YELLOW}⏳ Pod status: ${pod_status:-Pending} (${counter}s/${timeout}s)${NC}"
        sleep 5
        counter=$((counter + 5))
    fi
done

if [ $counter -ge $timeout ]; then
    echo -e "${RED}❌ Timeout aguardando pod ficar pronto!${NC}"
    kubectl describe pods -n "${NAMESPACE}" -l app=whatsapp-frontend
    exit 1
fi

# Verificação final
echo -e "${BLUE}🔍 Verificação final...${NC}"
echo ""
echo "📋 Status dos recursos:"
kubectl get pods,svc,ingress -n "${NAMESPACE}" -l app=whatsapp-frontend

# Informações finais
echo ""
echo -e "${GREEN}🎉 DEPLOY DO FRONTEND CONCLUÍDO COM SUCESSO!${NC}"
echo "============================================="
echo "✅ Imagem: ${FULL_IMAGE_NAME}"
echo "✅ Namespace: ${NAMESPACE}"
echo "✅ Status: Ativo"
echo ""
echo "🌐 Para acessar o frontend:"
echo "   - Localmente: kubectl port-forward -n ${NAMESPACE} svc/whatsapp-frontend-service 8080:80"
echo "   - Via ingress: https://atendimento.pluggerbi.com"
echo ""
echo -e "${BLUE}📊 Logs do pod:${NC}"
kubectl logs -n "${NAMESPACE}" -l app=whatsapp-frontend --tail=10 