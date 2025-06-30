#!/bin/bash

# Script para gerar certificados SSL auto-assinados para desenvolvimento
# ATENÇÃO: Estes certificados são apenas para desenvolvimento/teste
# Para produção, use certificados de uma autoridade certificadora confiável

echo "Gerando certificados SSL auto-assinados para desenvolvimento..."

# Gerar chave privada
openssl genrsa -out key.pem 2048

# Gerar certificado auto-assinado
openssl req -new -x509 -key key.pem -out cert.pem -days 365 -subj "/C=BR/ST=SP/L=Sao Paulo/O=WhatsApp Bot/CN=localhost"

echo "Certificados gerados com sucesso!"
echo "Arquivos criados:"
echo "  - cert.pem (certificado)"
echo "  - key.pem (chave privada)"
echo ""
echo "Para usar HTTPS, execute:"
echo "  export USE_SSL=True"
echo "  python app.py"
echo ""
echo "OU configure as variáveis de ambiente:"
echo "  USE_SSL=True SSL_CERT_PATH=cert.pem SSL_KEY_PATH=key.pem python app.py" 