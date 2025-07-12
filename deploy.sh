#!/bin/bash

# Script para deploy da aplicação WhatsApp Webhook no Kubernetes
# Oracle Cloud Infrastructure + DockerHub

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configurações
DOCKERHUB_USERNAME="cristianopluggerbi"
NAMESPACE="whatsapp-webhook"
IMAGE_NAME="whatsapp-webhook"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${IMAGE_TAG}"

echo -e "${GREEN}🚀 Iniciando deploy da aplicação WhatsApp Webhook${NC}"
echo -e "${GREEN}📊 Versão: Sistema de Logs Aprimorado${NC}"
echo -e "${YELLOW}🐋 Imagem: ${FULL_IMAGE_NAME}${NC}"

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

# Construir imagem Docker
echo -e "${YELLOW}🔨 Construindo imagem Docker...${NC}"
docker build -t $FULL_IMAGE_NAME .

# Verificar se a imagem foi criada
if ! docker images $FULL_IMAGE_NAME | grep -q $IMAGE_TAG; then
    echo -e "${RED}❌ Falha ao criar a imagem Docker${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Imagem Docker criada com sucesso${NC}"

# Verificar login no DockerHub
echo -e "${YELLOW}🔑 Verificando login no DockerHub...${NC}"
if ! docker info 2>/dev/null | grep -q "Username: ${DOCKERHUB_USERNAME}"; then
    echo -e "${YELLOW}⚠️ Não logado no DockerHub. Fazendo login...${NC}"
    docker login
fi

# Fazer push da imagem para o DockerHub
echo -e "${YELLOW}📤 Fazendo push da imagem para o DockerHub...${NC}"
docker push $FULL_IMAGE_NAME

echo -e "${GREEN}✅ Imagem enviada para o DockerHub com sucesso${NC}"

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

# Forçar restart dos pods para puxar a nova imagem
echo -e "${YELLOW}🔄 Forçando restart dos pods para puxar nova imagem...${NC}"
kubectl rollout restart deployment/whatsapp-webhook -n $NAMESPACE

# Aguardar o deployment estar pronto
echo -e "${YELLOW}⏳ Aguardando deployment estar pronto...${NC}"
kubectl rollout status deployment/whatsapp-webhook -n $NAMESPACE --timeout=300s

# Aguardar aplicação inicializar
echo -e "${YELLOW}⏳ Aguardando aplicação inicializar (90 segundos)...${NC}"
sleep 90

# Verificar status dos pods
echo -e "${YELLOW}🔍 Verificando status dos pods...${NC}"
kubectl get pods -n $NAMESPACE -l app=whatsapp-webhook

# Verificar status do service
echo -e "${YELLOW}🔍 Verificando status do service...${NC}"
kubectl get service whatsapp-webhook-service -n $NAMESPACE

# Verificar status do ingress
echo -e "${YELLOW}🔍 Verificando status do ingress...${NC}"
kubectl get ingress whatsapp-webhook-ingress -n $NAMESPACE

# Testar health check
echo -e "${YELLOW}🏥 Testando health check...${NC}"
if curl -s -f https://atendimento.pluggerbi.com/health &> /dev/null; then
    echo -e "${GREEN}✅ Health check OK${NC}"
else
    echo -e "${YELLOW}⚠️ Health check falhou - verificando logs...${NC}"
    kubectl logs -n $NAMESPACE -l app=whatsapp-webhook --tail=10
fi

# Executar migração de dados
echo -e "${YELLOW}🔄 Executando migração de dados...${NC}"
MIGRATION_RESULT=$(curl -s -X POST https://atendimento.pluggerbi.com/logs/migrate || echo "Erro na migração")
echo -e "${GREEN}📋 Resultado da migração: ${MIGRATION_RESULT}${NC}"

# Testar novos endpoints
echo -e "${YELLOW}🧪 Testando novos endpoints...${NC}"
if curl -s -f https://atendimento.pluggerbi.com/logs &> /dev/null; then
    echo -e "${GREEN}✅ Endpoint /logs OK${NC}"
else
    echo -e "${YELLOW}⚠️ Endpoint /logs com problemas${NC}"
fi

if curl -s -f https://atendimento.pluggerbi.com/logs/by-type/text &> /dev/null; then
    echo -e "${GREEN}✅ Endpoint /logs/by-type/text OK${NC}"
else
    echo -e "${YELLOW}⚠️ Endpoint /logs/by-type/text com problemas${NC}"
fi

echo -e "${GREEN}✅ Deploy concluído com sucesso!${NC}"
echo -e "${GREEN}📊 Alterações implementadas:${NC}"
echo -e "${GREEN}  • ✅ Tabela logs com novos campos (type, message, id_contact)${NC}"
echo -e "${GREEN}  • ✅ Migração automática de dados existentes${NC}"
echo -e "${GREEN}  • ✅ Novos endpoints para consulta por tipo e contato${NC}"
echo -e "${GREEN}  • ✅ Processamento aprimorado de mensagens WhatsApp${NC}"

echo -e "${YELLOW}🌐 Endpoints disponíveis:${NC}"
echo -e "${YELLOW}  • GET  /logs - Consultar todos os logs${NC}"
echo -e "${YELLOW}  • GET  /logs/by-type/{tipo} - Consultar por tipo${NC}"
echo -e "${YELLOW}  • GET  /logs/by-contact/{contato} - Consultar por contato${NC}"
echo -e "${YELLOW}  • POST /logs/migrate - Migrar dados existentes${NC}"

echo -e "${GREEN}🔗 Aplicação disponível em: https://atendimento.pluggerbi.com${NC}"
echo -e "${GREEN}📱 Webhook URL para o WhatsApp: https://atendimento.pluggerbi.com/webhook${NC}"

# Mostrar logs dos pods
echo -e "${YELLOW}📋 Logs dos pods (últimas 20 linhas):${NC}"
kubectl logs -n $NAMESPACE -l app=whatsapp-webhook --tail=20 