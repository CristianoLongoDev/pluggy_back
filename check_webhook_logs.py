#!/usr/bin/env python3
"""
Script simples para verificar os logs do webhook
"""

import requests
import json
import os
from datetime import datetime

# Configurações - Pode ser alterado manualmente ou via variável de ambiente
# Para forçar uso local: export WEBHOOK_BASE_URL="http://localhost:5000"
# Para forçar uso externo: export WEBHOOK_BASE_URL="https://atendimento.pluggerbi.com"

WEBHOOK_BASE_URL = os.getenv('WEBHOOK_BASE_URL', 'http://localhost:5000')
LOGS_URL = f"{WEBHOOK_BASE_URL}/logs"
HEALTH_URL = f"{WEBHOOK_BASE_URL}/health"

def check_logs():
    """Verifica os logs salvos no banco"""
    print("🔍 Verificando logs do webhook...")
    
    try:
        # Verificar todos os logs
        response = requests.get(LOGS_URL)
        if response.status_code == 200:
            logs = response.json()
            total_logs = logs.get('count', 0)
            print(f"✅ Total de logs: {total_logs}")
            
            if total_logs == 0:
                print("⚠️  Nenhum log encontrado. Possíveis causas:")
                print("   - Webhook não está recebendo eventos")
                print("   - Banco de dados não está conectado")
                print("   - Aplicação não está funcionando")
                return
            
            # Mostrar os últimos 10 logs
            recent_logs = logs.get('logs', [])[:10]
            print(f"\n📋 Últimos {len(recent_logs)} logs:")
            
            for i, log in enumerate(recent_logs, 1):
                event_type = log.get('event_type', 'unknown')
                created_at = log.get('created_at', 'unknown')
                
                print(f"\n{i}. {event_type} - {created_at}")
                
                # Mostrar detalhes específicos por tipo
                event_data = log.get('event_data', {})
                if event_type == 'message_received':
                    from_number = event_data.get('from', 'unknown')
                    message_type = event_data.get('type', 'unknown')
                    if 'text' in event_data:
                        text = event_data['text'].get('body', '')[:50]
                        print(f"   📱 De: {from_number} | Tipo: {message_type}")
                        print(f"   💬 Texto: {text}...")
                    else:
                        print(f"   📱 De: {from_number} | Tipo: {message_type}")
                        
                elif event_type == 'status_update':
                    status = event_data.get('status', 'unknown')
                    message_id = event_data.get('id', 'unknown')
                    print(f"   📊 Status: {status} | ID: {message_id}")
                    
                elif event_type == 'webhook_received':
                    object_type = event_data.get('object', 'unknown')
                    print(f"   🌐 Object: {object_type}")
                    
                elif event_type == 'webhook_verification':
                    mode = event_data.get('mode', 'unknown')
                    print(f"   ✅ Mode: {mode}")
                    
        else:
            print(f"❌ Erro ao buscar logs: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Erro ao verificar logs: {e}")

def check_health():
    """Verifica o status de saúde da aplicação"""
    print("\n🏥 Verificando saúde da aplicação...")
    
    try:
        response = requests.get(HEALTH_URL)
        if response.status_code == 200:
            health = response.json()
            print(f"✅ Status: {health.get('status')}")
            print(f"📊 Database: {health.get('database_status')}")
        else:
            print(f"❌ Erro no health check: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro ao verificar saúde: {e}")

def main():
    """Executa as verificações"""
    print("=" * 60)
    print("🔍 DIAGNÓSTICO DO WEBHOOK WHATSAPP")
    print("=" * 60)
    print(f"📍 URL Base: {WEBHOOK_BASE_URL}")
    print(f"🔗 Health: {HEALTH_URL}")
    print(f"📋 Logs: {LOGS_URL}")
    print("=" * 60)
    
    check_health()
    check_logs()
    
    print("\n" + "=" * 60)
    print("🎯 PRÓXIMOS PASSOS:")
    print("1. Se não há logs: verifique se o webhook está configurado na Meta")
    print("2. Se há logs mas não de mensagens: verifique se o número está ativo")
    print("3. Execute: python3 test_webhook_manual.py para testes manuais")
    print("4. Verifique os logs do pod: kubectl logs -n whatsapp-webhook -l app=whatsapp-webhook")
    print("5. Para testar externo: export WEBHOOK_BASE_URL='https://atendimento.pluggerbi.com'")
    print("=" * 60)

if __name__ == "__main__":
    main() 