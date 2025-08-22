#!/bin/bash

# Script completo de deploy para RabbitMQ customizado
# Build, Push para Docker Hub e Deploy no Kubernetes
# Autor: WhatsApp Webhook Team

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
DOCKER_USERNAME="cristianopluggerbi"
IMAGE_NAME="rabbitmq-webhook"
TAG="with-plugin"
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${TAG}"
NAMESPACE="whatsapp-webhook"
DEPLOYMENT_FILE="k8s/rabbitmq-deployment-optimized.yaml"

echo -e "${GREEN}🚀 Deploy completo do RabbitMQ customizado${NC}"
echo -e "${GREEN}📦 Imagem: ${FULL_IMAGE_NAME}${NC}"
echo -e "${GREEN}🎯 Namespace: ${NAMESPACE}${NC}"

# Função para verificar status dos pods
check_pod_status() {
    echo -e "${BLUE}📊 Verificando status dos pods...${NC}"
    kubectl get pods -n ${NAMESPACE} -l app=rabbitmq -o wide
    
    echo ""
    echo -e "${BLUE}🔍 Aguardando pods ficarem Ready (timeout: 180s)...${NC}"
    kubectl wait --for=condition=Ready pod -l app=rabbitmq -n ${NAMESPACE} --timeout=180s
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Todos os pods estão Ready!${NC}"
        kubectl get pods -n ${NAMESPACE} -l app=rabbitmq
    else
        echo -e "${YELLOW}⚠️ Alguns pods ainda não estão Ready. Verificando status...${NC}"
        kubectl get pods -n ${NAMESPACE} -l app=rabbitmq -o wide
        echo -e "${YELLOW}📋 Logs dos pods:${NC}"
        kubectl logs -n ${NAMESPACE} -l app=rabbitmq --tail=10
    fi
}

# Verificar se Docker está rodando
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Erro: Docker não está rodando!${NC}"
    exit 1
fi

# Verificar se kubectl está configurado
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ kubectl não está configurado ou não consegue conectar ao cluster${NC}"
    exit 1
fi

# Verificar se os arquivos necessários existem
if [ ! -f "Dockerfile.rabbitmq" ]; then
    echo -e "${RED}❌ Arquivo Dockerfile.rabbitmq não encontrado${NC}"
    exit 1
fi

if [ ! -d "k8s/rabbitmq-config" ]; then
    echo -e "${RED}❌ Diretório k8s/rabbitmq-config não encontrado${NC}"
    exit 1
fi

# Verificar login no Docker Hub
echo -e "${BLUE}📋 Verificando login no Docker Hub...${NC}"
if ! docker info 2>/dev/null | grep -q "Username: ${DOCKER_USERNAME}"; then
    echo -e "${YELLOW}🔐 Fazendo login no Docker Hub...${NC}"
    docker login
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Erro no login do Docker Hub!${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ Docker e kubectl configurados${NC}"

echo -e "${YELLOW}🔨 Etapa 1: Build da imagem Docker...${NC}"
docker build -f Dockerfile.rabbitmq -t ${FULL_IMAGE_NAME} .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Erro no build da imagem!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Imagem Docker construída com sucesso${NC}"

echo -e "${YELLOW}📤 Etapa 2: Push para Docker Hub...${NC}"
docker push ${FULL_IMAGE_NAME}

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Erro no push para Docker Hub!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Imagem enviada para Docker Hub com sucesso${NC}"

echo -e "${YELLOW}📝 Etapa 3: Verificando deployment existente...${NC}"
if [ -f "${DEPLOYMENT_FILE}" ]; then
    echo -e "${GREEN}✅ Arquivo ${DEPLOYMENT_FILE} encontrado${NC}"
else
    echo -e "${RED}❌ Arquivo ${DEPLOYMENT_FILE} não encontrado${NC}"
    exit 1
fi

echo -e "${YELLOW}🚀 Etapa 4: Deploy no Kubernetes...${NC}"
kubectl apply -f ${DEPLOYMENT_FILE}

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Erro no deploy do Kubernetes!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Deployment aplicado com sucesso${NC}"

echo -e "${YELLOW}⏳ Aguardando deployment ser processado...${NC}"
sleep 10

# Deletar pod
echo -e "${YELLOW}📊 Deletando pod...${NC}"
kubectl delete pod -n whatsapp-webhook -l app=rabbitmq

# Aguardar deployment
echo -e "${YELLOW}⏳ Aguardando pod ser criado...${NC}"
sleep 10

check_pod_status

# Verificar se RabbitMQ está funcionando
echo ""
echo -e "${BLUE}🧪 Testando conectividade do RabbitMQ...${NC}"
kubectl get pods -n ${NAMESPACE} -l app=rabbitmq --no-headers | head -1 | while read pod_name rest; do
    if [ ! -z "$pod_name" ]; then
        echo -e "${YELLOW}🔍 Testando conectividade do pod: $pod_name${NC}"
        kubectl exec -n ${NAMESPACE} $pod_name -- rabbitmq-diagnostics ping 2>/dev/null || echo -e "${YELLOW}⚠️ Ping falhou ou ainda não está pronto${NC}"
    fi
done

echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}✅ Deploy completo realizado com sucesso!${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""
echo -e "${BLUE}📋 INFORMAÇÕES ÚTEIS:${NC}"
echo ""
echo -e "${YELLOW}🐳 Imagem: ${FULL_IMAGE_NAME}${NC}"
echo -e "${YELLOW}📊 Recursos: 96Mi/192Mi (otimizado)${NC}"
echo -e "${YELLOW}⚡ Health checks otimizados${NC}"
echo -e "${YELLOW}🔒 Security context configurado${NC}"
echo ""
echo -e "${YELLOW}🔍 Para verificar logs:${NC}"
echo -e "   kubectl logs -f deployment/rabbitmq -n ${NAMESPACE}"
echo ""
echo -e "${YELLOW}🌐 Para acessar management:${NC}"
echo -e "   kubectl port-forward svc/rabbitmq-management 15672:15672 -n ${NAMESPACE}"
echo -e "   Usuário: admin"
echo -e "   Senha: rabbitmq123"
echo ""
echo -e "${YELLOW}📊 Status dos pods:${NC}"
kubectl get pods -n ${NAMESPACE} -l app=rabbitmq
echo ""
echo -e "${GREEN}=================================================${NC}" 