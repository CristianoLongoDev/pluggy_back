#!/bin/bash

# Script para deploy da aplicação WhatsApp Webhook no Kubernetes
# Oracle Cloud Infrastructure

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configurações
REGISTRY_URL="seu-registro.ocir.io"
NAMESPACE="whatsapp-webhook"
IMAGE_NAME="whatsapp-webhook"
IMAGE_TAG="latest"

echo -e "${GREEN}🚀 Iniciando deploy da aplicação WhatsApp Webhook${NC}"

# Verificar se o kubectl está configurado
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ kubectl não está configurado ou não consegue conectar ao cluster${NC}"
    exit 1
fi

echo -e "${GREEN}✅ kubectl configurado${NC}"

# Criar namespace se não existir
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    echo -e "${YELLOW}⚠️  Namespace $NAMESPACE não existe. Criando...${NC}"
    kubectl apply -f k8s/namespace.yaml
fi

# Construir imagem Docker
echo -e "${YELLOW}🔨 Construindo imagem Docker...${NC}"
docker build -t $IMAGE_NAME:$IMAGE_TAG .

# Tag da imagem para o registry
FULL_IMAGE_NAME="$REGISTRY_URL/$NAMESPACE/$IMAGE_NAME:$IMAGE_TAG"
docker tag $IMAGE_NAME:$IMAGE_TAG $FULL_IMAGE_NAME

# Fazer push da imagem (descomente se estiver usando registry)
# echo -e "${YELLOW}📤 Fazendo push da imagem...${NC}"
# docker push $FULL_IMAGE_NAME

# Aplicar configurações do Kubernetes
echo -e "${YELLOW}📋 Aplicando configurações do Kubernetes...${NC}"

# Verificar se o Cert-Manager está instalado
if kubectl get namespace cert-manager &> /dev/null; then
    echo -e "${GREEN}✅ Cert-Manager encontrado. Aplicando ClusterIssuer...${NC}"
    kubectl apply -f k8s/cluster-issuer.yaml
else
    echo -e "${YELLOW}⚠️  Cert-Manager não encontrado. Certificados SSL não serão gerados automaticamente.${NC}"
    echo -e "${YELLOW}   Para instalar o Cert-Manager, execute:${NC}"
    echo -e "${YELLOW}   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml${NC}"
fi

# Aplicar ConfigMap e Secret
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# Aplicar Deployment, Service e Ingress
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Aguardar o deployment estar pronto
echo -e "${YELLOW}⏳ Aguardando deployment estar pronto...${NC}"
kubectl rollout status deployment/whatsapp-webhook -n $NAMESPACE

# Aguardar 6 minutos para os pods inicializarem completamente
echo -e "${YELLOW}⏳ Aguardando 6 minutos para os pods inicializarem completamente...${NC}"
echo -e "${YELLOW}   Isso garante que as dependências sejam instaladas e a aplicação esteja pronta${NC}"
for i in {1..6}; do
    echo -e "${YELLOW}   Aguardando... ${i}/6 minutos${NC}"
    sleep 60
done
echo -e "${GREEN}✅ Tempo de espera concluído${NC}"

# Verificar status dos pods
echo -e "${YELLOW}🔍 Verificando status dos pods...${NC}"
kubectl get pods -n $NAMESPACE -l app=whatsapp-webhook

# Verificar status do service
echo -e "${YELLOW}🔍 Verificando status do service...${NC}"
kubectl get service whatsapp-webhook-service -n $NAMESPACE

# Verificar status do ingress
echo -e "${YELLOW}🔍 Verificando status do ingress...${NC}"
kubectl get ingress whatsapp-webhook-ingress -n $NAMESPACE

echo -e "${GREEN}✅ Deploy concluído com sucesso!${NC}"
echo -e "${GREEN}🌐 A aplicação estará disponível em: https://atendimento.pluggerbi.com${NC}"
echo -e "${YELLOW}📝 Webhook URL para o WhatsApp: https://atendimento.pluggerbi.com/webhook${NC}"

# Mostrar logs dos pods
echo -e "${YELLOW}📋 Logs dos pods (últimas 10 linhas):${NC}"
kubectl logs -n $NAMESPACE -l app=whatsapp-webhook --tail=10 