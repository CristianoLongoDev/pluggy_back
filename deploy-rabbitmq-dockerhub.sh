#!/bin/bash

# Script completo de deploy para RabbitMQ customizado
# Build, Push para Docker Hub e Deploy no Kubernetes
# Autor: WhatsApp Webhook Team
# Data: $(date +%Y-%m-%d)

set -e

# Configurações
DOCKER_USERNAME="cristianopluggerbi"
IMAGE_NAME="rabbitmq-webhook"
TAG="latest"
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${TAG}"
NAMESPACE="whatsapp-webhook"
DEPLOYMENT_FILE="k8s/rabbitmq-deployment-optimized.yaml"

echo "🚀 Deploy completo do RabbitMQ customizado"
echo "📦 Imagem: ${FULL_IMAGE_NAME}"
echo "🎯 Namespace: ${NAMESPACE}"

# Função para verificar status dos pods
check_pod_status() {
    echo "📊 Verificando status dos pods..."
    kubectl get pods -n ${NAMESPACE} -l app=rabbitmq -o wide
    
    echo ""
    echo "🔍 Aguardando pods ficarem Ready (timeout: 180s)..."
    kubectl wait --for=condition=Ready pod -l app=rabbitmq -n ${NAMESPACE} --timeout=180s
    
    if [ $? -eq 0 ]; then
        echo "✅ Todos os pods estão Ready!"
        kubectl get pods -n ${NAMESPACE} -l app=rabbitmq
    else
        echo "⚠️ Alguns pods ainda não estão Ready. Verificando status..."
        kubectl get pods -n ${NAMESPACE} -l app=rabbitmq -o wide
        kubectl describe pods -n ${NAMESPACE} -l app=rabbitmq
    fi
}

# Verificar se Docker está rodando
if ! docker info > /dev/null 2>&1; then
    echo "❌ Erro: Docker não está rodando!"
    exit 1
fi

# Verificar login no Docker Hub
echo "📋 Verificando login no Docker Hub..."
if ! docker info | grep -q "Username: ${DOCKER_USERNAME}"; then
    echo "🔐 Fazendo login no Docker Hub..."
    docker login
    if [ $? -ne 0 ]; then
        echo "❌ Erro no login do Docker Hub!"
        exit 1
    fi
fi

echo "🔨 Etapa 1: Build da imagem Docker..."
docker build -f Dockerfile.rabbitmq -t ${FULL_IMAGE_NAME} .

if [ $? -ne 0 ]; then
    echo "❌ Erro no build da imagem!"
    exit 1
fi

echo "📤 Etapa 2: Push para Docker Hub..."
docker push ${FULL_IMAGE_NAME}

if [ $? -ne 0 ]; then
    echo "❌ Erro no push para Docker Hub!"
    exit 1
fi

echo "📝 Etapa 3: Criando deployment otimizado..."
cat > ${DEPLOYMENT_FILE} << 'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: rabbitmq-pvc
  namespace: whatsapp-webhook
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
  storageClassName: oci-bv
---
apiVersion: v1
kind: Secret
metadata:
  name: rabbitmq-secret
  namespace: whatsapp-webhook
type: Opaque
data:
  # usuario: admin
  username: YWRtaW4=
  # senha: rabbitmq123
  password: cmFiYml0bXExMjM=
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rabbitmq
  namespace: whatsapp-webhook
  labels:
    app: rabbitmq
spec:
  replicas: 1
  selector:
    matchLabels:
      app: rabbitmq
  template:
    metadata:
      labels:
        app: rabbitmq
    spec:
      containers:
      - name: rabbitmq
        image: PLACEHOLDER_IMAGE
        ports:
        - containerPort: 5672
          name: amqp
        - containerPort: 15672
          name: management
        env:
        - name: RABBITMQ_DEFAULT_USER
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secret
              key: username
        - name: RABBITMQ_DEFAULT_PASS
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secret
              key: password
        - name: RABBITMQ_ERLANG_COOKIE
          value: "whatsapp-webhook-cookie"
        volumeMounts:
        - name: rabbitmq-storage
          mountPath: /var/lib/rabbitmq
        resources:
          requests:
            memory: "96Mi"    # Reduzido: customizada inicia mais rápido
            cpu: "40m"        # Reduzido: menos overhead
          limits:
            memory: "192Mi"   # Reduzido: configurações pré-carregadas
            cpu: "150m"       # Reduzido: melhor performance
        livenessProbe:
          exec:
            command:
            - rabbitmq-diagnostics
            - ping
          initialDelaySeconds: 60    # Reduzido: imagem otimizada
          periodSeconds: 30
          timeoutSeconds: 15
          failureThreshold: 5
        readinessProbe:
          exec:
            command:
            - rabbitmq-diagnostics
            - check_port_connectivity
          initialDelaySeconds: 30    # Reduzido: inicialização mais rápida
          periodSeconds: 10
          timeoutSeconds: 10
          failureThreshold: 3
        securityContext:
          runAsNonRoot: true
          runAsUser: 999
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: false
      volumes:
      - name: rabbitmq-storage
        persistentVolumeClaim:
          claimName: rabbitmq-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq-service
  namespace: whatsapp-webhook
  labels:
    app: rabbitmq
spec:
  type: ClusterIP
  ports:
  - port: 5672
    targetPort: 5672
    name: amqp
  - port: 15672
    targetPort: 15672
    name: management
  selector:
    app: rabbitmq
---
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq-management
  namespace: whatsapp-webhook
  labels:
    app: rabbitmq
spec:
  type: NodePort
  ports:
  - port: 15672
    targetPort: 15672
    nodePort: 31672
    name: management
  selector:
    app: rabbitmq
EOF

# Substituir placeholder pela imagem real
sed -i "s|PLACEHOLDER_IMAGE|${FULL_IMAGE_NAME}|g" ${DEPLOYMENT_FILE}

echo "🚀 Etapa 4: Deploy no Kubernetes..."
kubectl apply -f ${DEPLOYMENT_FILE}

if [ $? -ne 0 ]; then
    echo "❌ Erro no deploy do Kubernetes!"
    exit 1
fi

echo "⏳ Aguardando deployment ser processado..."
sleep 10

check_pod_status

echo ""
echo "✅ Deploy completo realizado com sucesso!"
echo "📋 Resumo:"
echo "  🐳 Imagem: ${FULL_IMAGE_NAME}"
echo "  📊 Recursos: 96Mi/192Mi (25% menos memória)"
echo "  ⚡ Health checks otimizados"
echo "  🔒 Security context configurado"
echo ""
echo "🔍 Para verificar logs:"
echo "  kubectl logs -f deployment/rabbitmq -n ${NAMESPACE}"
echo ""
echo "🌐 Para acessar management:"
echo "  kubectl port-forward svc/rabbitmq-management 15672:15672 -n ${NAMESPACE}" 