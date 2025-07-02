#!/bin/bash

# Script para construir e fazer push da imagem otimizada do webhook worker

set -e

# Configurações
DOCKER_HUB_USER="${DOCKER_HUB_USER:-seu_usuario_dockerhub}"  # Definir via variável de ambiente
IMAGE_NAME="webhook-worker"
TAG="${1:-latest}"
REGISTRY="${2:-${DOCKER_HUB_USER}}"  # Docker Hub por padrão
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo "🔨 Construindo imagem otimizada do webhook worker..."
echo "📦 Imagem: ${FULL_IMAGE_NAME}"

# Construir a imagem
docker build -f Dockerfile.webhook-worker -t "${FULL_IMAGE_NAME}" .

# Mostrar informações da imagem
echo ""
echo "📊 Informações da imagem:"
docker images "${FULL_IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

# Verificar se deve fazer login no Docker Hub
if [ "${REGISTRY}" != "localhost:5000" ] && [ "${3}" = "--push" ]; then
    echo ""
    echo "🔐 Verificando login no Docker Hub..."
    if ! docker info | grep -q "Username:"; then
        echo "⚠️ Faça login no Docker Hub primeiro:"
        echo "   docker login"
        exit 1
    fi
fi

# Fazer push para o registry (padrão agora é sempre fazer push para Docker Hub)
if [ "${3}" = "--push" ] || [ "${REGISTRY}" != "localhost:5000" ]; then
    echo ""
    echo "📤 Fazendo push para ${REGISTRY}..."
    docker push "${FULL_IMAGE_NAME}"
    echo "✅ Push concluído!"
    echo "🌍 Imagem disponível em: https://hub.docker.com/r/${REGISTRY}/${IMAGE_NAME}"
fi

echo ""
echo "🎉 Imagem construída com sucesso!"
echo "🔧 Para usar no Kubernetes, atualize o deployment com a imagem: ${FULL_IMAGE_NAME}"

# Mostrar comandos úteis
echo ""
echo "📋 Comandos úteis:"
echo "   Testar localmente: docker run --rm -it ${FULL_IMAGE_NAME}"
echo "   Ver logs: docker logs <container_id>"
echo "   Inspecionar: docker exec -it <container_id> /bin/sh"
echo ""
echo "🚀 Para fazer push para Docker Hub:"
echo "   1. docker login"
echo "   2. export DOCKER_HUB_USER=seu_usuario"
echo "   3. ./build-webhook-worker.sh latest --push" 