#!/bin/bash

# Script para verificar o status do HTTPS no Kubernetes

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="whatsapp-webhook"
DOMAIN="atendimento.pluggerbi.com"

echo -e "${BLUE}🔒 Verificando status do HTTPS no Kubernetes${NC}"
echo -e "${BLUE}=============================================${NC}"

# Verificar se o namespace existe
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    echo -e "${RED}❌ Namespace $NAMESPACE não existe${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Namespace $NAMESPACE encontrado${NC}"

# Verificar status do Ingress
echo -e "\n${YELLOW}📋 Status do Ingress:${NC}"
kubectl get ingress whatsapp-webhook-ingress -n $NAMESPACE

# Verificar certificados
echo -e "\n${YELLOW}🔐 Verificando certificados SSL:${NC}"
if kubectl get certificates -n $NAMESPACE &> /dev/null; then
    kubectl get certificates -n $NAMESPACE
else
    echo -e "${YELLOW}⚠️  Nenhum certificado encontrado no namespace${NC}"
fi

# Verificar ClusterIssuer
echo -e "\n${YELLOW}🏭 Verificando ClusterIssuer:${NC}"
if kubectl get clusterissuer letsencrypt-prod &> /dev/null; then
    echo -e "${GREEN}✅ ClusterIssuer 'letsencrypt-prod' encontrado${NC}"
    kubectl describe clusterissuer letsencrypt-prod
else
    echo -e "${YELLOW}⚠️  ClusterIssuer 'letsencrypt-prod' não encontrado${NC}"
fi

# Verificar Cert-Manager
echo -e "\n${YELLOW}🔧 Verificando Cert-Manager:${NC}"
if kubectl get namespace cert-manager &> /dev/null; then
    echo -e "${GREEN}✅ Cert-Manager instalado${NC}"
    kubectl get pods -n cert-manager
else
    echo -e "${RED}❌ Cert-Manager não instalado${NC}"
    echo -e "${YELLOW}   Para instalar:${NC}"
    echo -e "${YELLOW}   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml${NC}"
fi

# Testar conectividade HTTPS
echo -e "\n${YELLOW}🌐 Testando conectividade HTTPS:${NC}"
if command -v curl &> /dev/null; then
    echo -e "${BLUE}Testando https://$DOMAIN...${NC}"
    if curl -I --max-time 10 https://$DOMAIN &> /dev/null; then
        echo -e "${GREEN}✅ HTTPS funcionando em https://$DOMAIN${NC}"
    else
        echo -e "${RED}❌ HTTPS não está funcionando em https://$DOMAIN${NC}"
    fi
    
    echo -e "${BLUE}Testando webhook https://$DOMAIN/webhook...${NC}"
    if curl -I --max-time 10 https://$DOMAIN/webhook &> /dev/null; then
        echo -e "${GREEN}✅ Webhook HTTPS funcionando${NC}"
    else
        echo -e "${RED}❌ Webhook HTTPS não está funcionando${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  curl não encontrado. Não foi possível testar conectividade${NC}"
fi

# Verificar logs do Ingress Controller
echo -e "\n${YELLOW}📋 Logs do Ingress Controller (últimas 5 linhas):${NC}"
if kubectl get pods -n ingress-nginx &> /dev/null; then
    kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=5
else
    echo -e "${YELLOW}⚠️  Ingress Controller não encontrado${NC}"
fi

echo -e "\n${GREEN}✅ Verificação concluída!${NC}"
echo -e "${BLUE}🌐 URL do webhook: https://$DOMAIN/webhook${NC}" 