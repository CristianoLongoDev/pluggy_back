#!/bin/bash

# Script para deploy da aplicação WhatsApp Webhook no Kubernetes
# Oracle Cloud Infrastructure + DockerHub

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
DOCKERHUB_USERNAME="cristianopluggerbi"
NAMESPACE="whatsapp-webhook"
IMAGE_NAME="whatsapp-webhook"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${IMAGE_TAG}"

echo -e "${GREEN}🚀 Iniciando deploy da aplicação WhatsApp Webhook${NC}"
echo -e "${GREEN}📊 Versão: Sistema com RabbitMQ Manager Otimizado${NC}"
echo -e "${YELLOW}🐋 Imagem: ${FULL_IMAGE_NAME}${NC}"

# Função para verificar status dos pods
check_pod_status() {
    local app_label=$1
    local timeout=${2:-180}
    
    echo -e "${BLUE}📊 Verificando status dos pods para app=${app_label}...${NC}"
    kubectl get pods -n ${NAMESPACE} -l app=${app_label} -o wide
    
    echo -e "${BLUE}🔍 Aguardando pods ficarem Ready (timeout: ${timeout}s)...${NC}"
    kubectl wait --for=condition=Ready pod -l app=${app_label} -n ${NAMESPACE} --timeout=${timeout}s
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Todos os pods estão Ready!${NC}"
        kubectl get pods -n ${NAMESPACE} -l app=${app_label}
    else
        echo -e "${YELLOW}⚠️ Alguns pods ainda não estão Ready. Verificando detalhes...${NC}"
        kubectl get pods -n ${NAMESPACE} -l app=${app_label} -o wide
        echo -e "${YELLOW}📋 Logs dos pods:${NC}"
        kubectl logs -n ${NAMESPACE} -l app=${app_label} --tail=10
    fi
}

# Verificar se o Docker está rodando
if ! docker ps &> /dev/null; then
    echo -e "${RED}❌ Docker não está rodando ou não acessível${NC}"
    exit 1
fi

# Verificar se o kubectl está configurado
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ kubectl não está configurado ou não consegue conectar ao cluster${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker e kubectl configurados${NC}"

# Criar namespace se não existir
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    echo -e "${YELLOW}⚠️  Namespace $NAMESPACE não existe. Criando...${NC}"
    kubectl apply -f k8s/namespace.yaml
fi

# Verificar se há mudanças no código
echo -e "${BLUE}🔍 Verificando alterações no código...${NC}"
if [ -f "rabbitmq_manager.py" ]; then
    echo -e "${GREEN}✅ Código do RabbitMQ Manager encontrado - incluindo correções de canal${NC}"
else
    echo -e "${RED}❌ Arquivo rabbitmq_manager.py não encontrado${NC}"
    exit 1
fi

# Construir imagem Docker
echo -e "${YELLOW}🔨 Construindo imagem Docker...${NC}"
docker build -t $FULL_IMAGE_NAME .

# Verificar se a imagem foi criada
if ! docker images $FULL_IMAGE_NAME | grep -q $IMAGE_TAG; then
    echo -e "${RED}❌ Falha ao criar imagem Docker${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Imagem Docker criada com sucesso${NC}"

# Fazer login no DockerHub se necessário
echo -e "${YELLOW}🔐 Verificando login no DockerHub...${NC}"
if ! docker info 2>/dev/null | grep -q "Username: ${DOCKERHUB_USERNAME}"; then
    echo -e "${YELLOW}🔐 Fazendo login no DockerHub...${NC}"
    docker login
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Erro no login do DockerHub${NC}"
        exit 1
    fi
fi

# Push da imagem para DockerHub
echo -e "${YELLOW}📤 Enviando imagem para DockerHub...${NC}"
docker push $FULL_IMAGE_NAME

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Falha ao enviar imagem para DockerHub${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Imagem enviada para DockerHub com sucesso${NC}"

# Aplicar configurações
echo -e "${YELLOW}📝 Aplicando configurações...${NC}"

# Aplicar secret
if [ -f "k8s/secret.yaml" ]; then
    kubectl apply -f k8s/secret.yaml
    echo -e "${GREEN}✅ Secret aplicado${NC}"
fi

# Aplicar configmap
if [ -f "k8s/configmap.yaml" ]; then
kubectl apply -f k8s/configmap.yaml
    echo -e "${GREEN}✅ ConfigMap aplicado${NC}"
fi

# Aplicar service
if [ -f "k8s/service.yaml" ]; then
    kubectl apply -f k8s/service.yaml
    echo -e "${GREEN}✅ Service aplicado${NC}"
fi

# Aplicar deployment
echo -e "${YELLOW}🚀 Aplicando deployment...${NC}"
kubectl apply -f k8s/deployment.yaml

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Falha ao aplicar deployment${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Deployment aplicado com sucesso${NC}"

# Aguardar deployment
echo -e "${YELLOW}⏳ Aguardando deployment ser processado...${NC}"
sleep 10

# Verificar status dos pods
check_pod_status "whatsapp-webhook" 240

# Verificar se há ingress
if [ -f "k8s/ingress.yaml" ]; then
    echo -e "${YELLOW}🌐 Aplicando ingress...${NC}"
    kubectl apply -f k8s/ingress.yaml
    echo -e "${GREEN}✅ Ingress aplicado${NC}"
fi

echo ""
echo -e "${GREEN}🌐 Deletando pod"
kubectl delete pod -n whatsapp-webhook -l app=whatsapp-webhook


# Verificação final
echo -e "${BLUE}🔍 Verificação final do sistema...${NC}"
echo ""
echo -e "${GREEN}📊 STATUS DOS PODS:${NC}"
kubectl get pods -n ${NAMESPACE} -o wide

echo ""
echo -e "${GREEN}🌐 STATUS DOS SERVICES:${NC}"
kubectl get services -n ${NAMESPACE}

echo ""
echo -e "${GREEN}📋 STATUS DOS DEPLOYMENTS:${NC}"
kubectl get deployments -n ${NAMESPACE}

# Testar saúde da aplicação
echo ""
echo -e "${BLUE}🩺 Testando saúde da aplicação...${NC}"
kubectl get pods -n ${NAMESPACE} -l app=whatsapp-webhook --no-headers | head -1 | while read pod_name rest; do
    if [ ! -z "$pod_name" ]; then
        echo -e "${YELLOW}🔍 Testando health check do pod: $pod_name${NC}"
        kubectl exec -n ${NAMESPACE} $pod_name -- curl -f http://localhost:5000/health 2>/dev/null || echo -e "${YELLOW}⚠️ Health check falhou ou ainda não está pronto${NC}"
    fi
done

echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}🎉 DEPLOY CONCLUÍDO COM SUCESSO!${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""
echo -e "${BLUE}📋 INFORMAÇÕES ÚTEIS:${NC}"
echo ""
echo -e "${YELLOW}🔗 URL da aplicação:${NC}"
echo -e "   https://atendimento.pluggerbi.com"
echo ""
echo -e "${YELLOW}🩺 Health check:${NC}"
echo -e "   https://atendimento.pluggerbi.com/health"
echo ""
echo -e "${YELLOW}🤖 Status do bot:${NC}"
echo -e "   https://atendimento.pluggerbi.com/bot/status"
echo ""
echo -e "${YELLOW}📊 Para verificar logs:${NC}"
echo -e "   kubectl logs -f deployment/whatsapp-webhook -n ${NAMESPACE}"
echo ""
echo -e "${YELLOW}🧪 Para testar webhook:${NC}"
echo -e "   curl -X POST https://atendimento.pluggerbi.com/webhook \\\\"
echo -e "        -H 'Content-Type: application/json' \\\\"
echo -e "        -d '{\"test\": \"message\"}'"
echo ""
echo -e "${YELLOW}🐰 Status do RabbitMQ:${NC}"
echo -e "   https://atendimento.pluggerbi.com/rabbitmq/status"
echo ""
echo -e "${GREEN}=================================================${NC}" 