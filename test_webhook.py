#!/usr/bin/env python3
"""
Script para testar o webhook simulando eventos do WhatsApp Business API
"""

import requests
import json

# URL do webhook
WEBHOOK_URL = "http://localhost:5000/webhook"

def test_webhook_verification():
    """Testa a verificação do webhook"""
    print("🧪 Testando verificação do webhook...")
    
    params = {
        'hub.mode': 'subscribe',
        'hub.verify_token': 'seu_token_de_verificacao_aqui',
        'hub.challenge': 'test_challenge_123'
    }
    
    response = requests.get(WEBHOOK_URL, params=params)
    
    print(f"Status: {response.status_code}")
    print(f"Resposta: {response.text}")
    
    if response.status_code == 200:
        print("✅ Verificação do webhook funcionando!")
    else:
        print("❌ Falha na verificação do webhook")

def test_message_webhook():
    """Testa o webhook com uma mensagem simulada"""
    print("\n🧪 Testando webhook com mensagem...")
    
    # Simula uma mensagem de texto do WhatsApp
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "5511999999999",
                                "phone_number_id": "123456789"
                            },
                            "messages": [
                                {
                                    "from": "5511999999999",
                                    "id": "wamid.test123",
                                    "timestamp": "1234567890",
                                    "type": "text",
                                    "text": {
                                        "body": "Olá! Esta é uma mensagem de teste."
                                    }
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    response = requests.post(WEBHOOK_URL, json=payload, headers=headers)
    
    print(f"Status: {response.status_code}")
    print(f"Resposta: {response.text}")
    
    if response.status_code == 200:
        print("✅ Webhook de mensagem funcionando!")
    else:
        print("❌ Falha no webhook de mensagem")

def test_status_webhook():
    """Testa o webhook com um status de entrega"""
    print("\n🧪 Testando webhook com status de entrega...")
    
    # Simula um status de entrega do WhatsApp
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "5511999999999",
                                "phone_number_id": "123456789"
                            },
                            "statuses": [
                                {
                                    "id": "wamid.test123",
                                    "status": "delivered",
                                    "timestamp": "1234567890",
                                    "recipient_id": "5511999999999"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    response = requests.post(WEBHOOK_URL, json=payload, headers=headers)
    
    print(f"Status: {response.status_code}")
    print(f"Resposta: {response.text}")
    
    if response.status_code == 200:
        print("✅ Webhook de status funcionando!")
    else:
        print("❌ Falha no webhook de status")

if __name__ == "__main__":
    print("🚀 Iniciando testes do webhook...")
    print(f"URL do webhook: {WEBHOOK_URL}")
    
    try:
        # Testa se o servidor está rodando
        health_response = requests.get("http://localhost:5000/health")
        if health_response.status_code == 200:
            print("✅ Servidor está rodando!")
        else:
            print("❌ Servidor não está respondendo")
            exit(1)
    except requests.exceptions.ConnectionError:
        print("❌ Não foi possível conectar ao servidor. Certifique-se de que a aplicação está rodando.")
        exit(1)
    
    # Executa os testes
    test_webhook_verification()
    test_message_webhook()
    test_status_webhook()
    
    print("\n🎉 Testes concluídos!") 