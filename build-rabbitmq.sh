#!/bin/bash

# Script de build para imagem Docker customizada do RabbitMQ
# Autor: WhatsApp Webhook Team
# Data: $(date +%Y-%m-%d)

set -e

# Configurações
DOCKER_USERNAME="cristianopluggerbi"
IMAGE_NAME="rabbitmq-webhook"
TAG="latest"
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${TAG}"

echo "🚀 Iniciando build da imagem customizada do RabbitMQ..."
echo "📦 Imagem: ${FULL_IMAGE_NAME}"

# Verificar se Docker está rodando
if ! docker info > /dev/null 2>&1; then
    echo "❌ Erro: Docker não está rodando!"
    exit 1
fi

# Verificar se o Dockerfile existe
if [ ! -f "Dockerfile.rabbitmq" ]; then
    echo "❌ Erro: Dockerfile.rabbitmq não encontrado!"
    exit 1
fi

# Verificar se as configurações existem
if [ ! -d "k8s/rabbitmq-config" ]; then
    echo "❌ Erro: Diretório k8s/rabbitmq-config não encontrado!"
    exit 1
fi

echo "📋 Verificando login no Docker Hub..."
if ! docker info | grep -q "Username: ${DOCKER_USERNAME}"; then
    echo "🔐 Fazendo login no Docker Hub..."
    docker login
    if [ $? -ne 0 ]; then
        echo "❌ Erro no login do Docker Hub!"
        exit 1
    fi
fi

echo "🔨 Construindo imagem Docker..."
docker build -f Dockerfile.rabbitmq -t ${FULL_IMAGE_NAME} .

if [ $? -eq 0 ]; then
    echo "✅ Build concluído com sucesso!"
    echo "📊 Informações da imagem:"
    docker images | grep "${DOCKER_USERNAME}/${IMAGE_NAME}"
    
    echo ""
    echo "🚀 Para fazer push da imagem, execute:"
    echo "   docker push ${FULL_IMAGE_NAME}"
    echo ""
    echo "📝 Para usar no Kubernetes, atualize o deployment com:"
    echo "   image: ${FULL_IMAGE_NAME}"
else
    echo "❌ Erro no build da imagem!"
    exit 1
fi

echo "🎉 Script finalizado!" 