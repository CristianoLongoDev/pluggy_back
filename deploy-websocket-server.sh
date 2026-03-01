#!/bin/bash

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
DOCKERHUB_USERNAME="cristianopluggerbi"
IMAGE_NAME="whatsapp-websocket-server"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${IMAGE_TAG}"

# Deploy WebSocket Server
echo -e "${GREEN}🌐 Iniciando deploy do WebSocket Server${NC}"
echo -e "${YELLOW}🐋 Imagem: ${FULL_IMAGE_NAME}${NC}"

# Verificar se o Docker está rodando
if ! docker ps &> /dev/null; then
    echo -e "${RED}❌ Docker não está rodando ou não acessível${NC}"
    exit 1
fi

# Build da imagem Docker
echo -e "${YELLOW}🔨 Buildando imagem Docker...${NC}"
docker build -t $FULL_IMAGE_NAME -f Dockerfile.websocket-server .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Falha no build da imagem${NC}"
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

# Push para Docker Hub
echo -e "${YELLOW}📤 Enviando imagem para DockerHub...${NC}"
docker push $FULL_IMAGE_NAME

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Falha no push da imagem${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Imagem enviada para DockerHub com sucesso${NC}"

# Deploy no Kubernetes
echo -e "${BLUE}☸️ Fazendo deploy no Kubernetes...${NC}"

# Criar ConfigMap para WebSocket
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: websocket-config
  namespace: whatsapp-webhook
data:
  WEBSOCKET_HOST: "0.0.0.0"
  WEBSOCKET_PORT: "8765"
EOF

# Criar Deployment do WebSocket Server
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: websocket-server
  namespace: whatsapp-webhook
  labels:
    app: websocket-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: websocket-server
  template:
    metadata:
      labels:
        app: websocket-server
    spec:
      containers:
      - name: websocket-server
        image: ${FULL_IMAGE_NAME}
        ports:
        - containerPort: 8765
        env:
        - name: DB_HOST
          value: "10.0.10.69"
        - name: DB_PORT
          value: "6446"
        - name: DB_NAME
          value: "atendimento"
        - name: DB_USER
          value: "atendimento"
        - name: DB_PASSWORD
          value: "8/vLQv98vCmw%Ox1"
        - name: DB_ENABLED
          value: "True"
        - name: JWT_SECRET_KEY
          value: "websocket-default-secret-key-change-in-production"
        - name: SUPABASE_URL
          valueFrom:
            secretKeyRef:
              name: whatsapp-webhook-secret
              key: SUPABASE_URL
        - name: SUPABASE_ANON_KEY
          valueFrom:
            secretKeyRef:
              name: whatsapp-webhook-secret
              key: SUPABASE_ANON_KEY
        - name: WEBSOCKET_HOST
          valueFrom:
            configMapKeyRef:
              name: websocket-config
              key: WEBSOCKET_HOST
        - name: WEBSOCKET_PORT
          valueFrom:
            configMapKeyRef:
              name: websocket-config
              key: WEBSOCKET_PORT
        resources:
          limits:
            memory: "256Mi"
            cpu: "200m"
          requests:
            memory: "128Mi"
            cpu: "100m"
        # Health checks removidos: TCP socket não é compatível com WebSocket
        # O servidor WebSocket espera handshake completo, não conexão TCP simples
---
apiVersion: v1
kind: Service
metadata:
  name: websocket-service
  namespace: whatsapp-webhook
  labels:
    app: websocket-server
spec:
  selector:
    app: websocket-server
  ports:
  - port: 8765
    targetPort: 8765
    name: websocket
  type: ClusterIP
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${BLUE}📊 Deletando pod:${NC}"
    kubectl delete pod -n whatsapp-webhook -l app=websocket-server
    echo ""
    echo -e "${GREEN}✅ Deploy do WebSocket Server realizado com sucesso!${NC}"
    echo -e "${BLUE}📊 Verificando status dos pods...${NC}"
    kubectl get pods -n whatsapp-webhook -l app=websocket-server
    echo ""
    echo -e "${GREEN}🌐 Para conectar o frontend:${NC}"
    echo -e "${YELLOW}   URL: wss://pluggyapi.pluggerbi.com/ws${NC}"
    echo -e "${YELLOW}   Porta: 443 (HTTPS)${NC}"
    echo -e "${YELLOW}   Autenticação: JWT Token required${NC}"
    echo ""
    echo -e "${BLUE}📋 Endpoints da API:${NC}"
    echo -e "${YELLOW}   GET /websocket/info - Informações de conexão${NC}"
    echo -e "${YELLOW}   GET /websocket/stats - Estatísticas das conexões${NC}"
    echo -e "${YELLOW}   POST /websocket/test - Teste de notificação${NC}"
else
    echo -e "${RED}❌ Falha no deploy do Kubernetes${NC}"
    exit 1
fi

echo -e "${GREEN}🎯 Deploy concluído!${NC}"