#!/usr/bin/env python3
"""
Script para testar manualmente o webhook com diferentes tipos de eventos do WhatsApp
"""

import requests
import json
import time
import os

# Configurações - Pode ser alterado manualmente ou via variável de ambiente
# Para forçar uso local: export WEBHOOK_BASE_URL="http://localhost:5000"
# Para forçar uso externo: export WEBHOOK_BASE_URL="https://atendimento.pluggerbi.com"

WEBHOOK_BASE_URL = os.getenv('WEBHOOK_BASE_URL', 'http://localhost:5000')
WEBHOOK_URL = f"{WEBHOOK_BASE_URL}/webhook"
LOGS_URL = f"{WEBHOOK_BASE_URL}/logs"
HEALTH_URL = f"{WEBHOOK_BASE_URL}/health"

def test_webhook_verification():
    """Testa a verificação do webhook (GET)"""
    print("=== Teste de Verificação do Webhook ===")
    
    params = {
        'hub.mode': 'subscribe',
        'hub.verify_token': 'seu_token_de_verificacao_aqui',
        'hub.challenge': 'test_challenge_123'
    }
    
    try:
        response = requests.get(WEBHOOK_URL, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Erro: {e}")
        return False

def test_webhook_message():
    """Testa o webhook com uma mensagem de texto"""
    print("\n=== Teste de Mensagem de Texto ===")
    
    # Payload simulado de uma mensagem de texto do WhatsApp
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
                                "phone_number_id": "987654321"
                            },
                            "contacts": [
                                {
                                    "profile": {
                                        "name": "João Silva"
                                    },
                                    "wa_id": "5511888888888"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "5511888888888",
                                    "id": "wamid.123456789",
                                    "timestamp": str(int(time.time())),
                                    "text": {
                                        "body": "Olá! Esta é uma mensagem de teste."
                                    },
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload, headers={'Content-Type': 'application/json'})
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Erro: {e}")
        return False

def test_webhook_status():
    """Testa o webhook com um status de entrega"""
    print("\n=== Teste de Status de Entrega ===")
    
    # Payload simulado de um status de entrega
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
                                "phone_number_id": "987654321"
                            },
                            "statuses": [
                                {
                                    "id": "wamid.123456789",
                                    "status": "delivered",
                                    "timestamp": str(int(time.time())),
                                    "recipient_id": "5511888888888"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload, headers={'Content-Type': 'application/json'})
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Erro: {e}")
        return False

def test_webhook_invalid():
    """Testa o webhook com um payload inválido"""
    print("\n=== Teste de Payload Inválido ===")
    
    # Payload inválido (sem 'object' ou com 'object' diferente)
    payload = {
        "invalid_object": "test",
        "data": "test data"
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload, headers={'Content-Type': 'application/json'})
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Erro: {e}")
        return False

def check_logs():
    """Verifica os logs salvos no banco"""
    print("\n=== Verificando Logs ===")
    
    try:
        # Verificar todos os logs
        response = requests.get(LOGS_URL)
        if response.status_code == 200:
            logs = response.json()
            print(f"Total de logs: {logs.get('count', 0)}")
            
            # Mostrar os últimos 5 logs
            recent_logs = logs.get('logs', [])[:5]
            for i, log in enumerate(recent_logs, 1):
                print(f"\nLog {i}:")
                print(f"  Tipo: {log.get('event_type')}")
                print(f"  Data: {log.get('created_at')}")
                print(f"  Dados: {json.dumps(log.get('event_data'), indent=2)[:200]}...")
        else:
            print(f"Erro ao buscar logs: {response.status_code}")
            
    except Exception as e:
        print(f"Erro ao verificar logs: {e}")

def main():
    """Executa todos os testes"""
    print("🧪 Iniciando testes manuais do webhook...")
    print(f"📍 URL Base: {WEBHOOK_BASE_URL}")
    print(f"🔗 Webhook: {WEBHOOK_URL}")
    print(f"📋 Logs: {LOGS_URL}")
    
    # Executar testes
    tests = [
        ("Verificação", test_webhook_verification),
        ("Mensagem", test_webhook_message),
        ("Status", test_webhook_status),
        ("Inválido", test_webhook_invalid)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        success = test_func()
        results.append((test_name, success))
        time.sleep(2)  # Pausa entre testes
    
    # Mostrar resultados
    print(f"\n{'='*50}")
    print("📊 RESULTADOS DOS TESTES:")
    for test_name, success in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"  {test_name}: {status}")
    
    # Verificar logs
    check_logs()
    
    print(f"\n{'='*50}")
    print("🎯 PRÓXIMOS PASSOS:")
    print("1. Verifique se os logs foram salvos no banco")
    print("2. Confirme se o webhook está configurado corretamente na Meta")
    print("3. Verifique se o domínio está acessível externamente")
    print("4. Teste com uma mensagem real do WhatsApp")
    print("5. Para testar externo: export WEBHOOK_BASE_URL='https://atendimento.pluggerbi.com'")

if __name__ == "__main__":
    main() 