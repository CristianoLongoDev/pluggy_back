#!/bin/bash

# Script para executar a aplicação com HTTPS

echo "🔒 Iniciando aplicação com HTTPS..."

# Verificar se os certificados existem
if [ ! -f "cert.pem" ] || [ ! -f "key.pem" ]; then
    echo "❌ Certificados SSL não encontrados!"
    echo "Gerando certificados..."
    ./generate_ssl_cert.sh
fi

# Configurar variáveis de ambiente para HTTPS
export USE_SSL=True
export SSL_CERT_PATH=cert.pem
export SSL_KEY_PATH=key.pem

echo "✅ Certificados SSL configurados"
echo "🌐 Iniciando servidor HTTPS..."
echo "📱 URL do webhook: https://$(hostname -I | awk '{print $1}'):5000/webhook"
echo ""

# Executar a aplicação
python app.py 