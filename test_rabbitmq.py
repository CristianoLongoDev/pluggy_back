#!/usr/bin/env python3
"""
Script para testar o RabbitMQ e as funcionalidades de mensageria
"""

import json
import logging
import time
from config import RABBITMQ_ENABLED
from rabbitmq_manager import rabbitmq_manager

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_rabbitmq_connection():
    """Testa a conexão com RabbitMQ"""
    print("🐰 TESTE DE CONEXÃO RABBITMQ")
    print("=" * 50)
    
    if not RABBITMQ_ENABLED:
        print("❌ RabbitMQ está desabilitado")
        return False
    
    print("🔗 Tentando conectar ao RabbitMQ...")
    connected = rabbitmq_manager.connect()
    
    if connected:
        print("✅ Conectado ao RabbitMQ com sucesso!")
        
        # Obter status
        status = rabbitmq_manager.get_status()
        print(f"📊 Status: {json.dumps(status, indent=2)}")
        
        return True
    else:
        print("❌ Falha ao conectar ao RabbitMQ")
        return False

def test_message_publishing():
    """Testa o envio de mensagens"""
    print("\n📤 TESTE DE ENVIO DE MENSAGENS")
    print("=" * 50)
    
    # Mensagem de teste para webhook
    test_webhook_data = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "test_entry_id",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15551234567",
                        "phone_number_id": "123456789"
                    },
                    "messages": [{
                        "id": "test_message_id",
                        "from": "5511999999999",
                        "timestamp": str(int(time.time())),
                        "type": "text",
                        "text": {
                            "body": "Mensagem de teste do RabbitMQ!"
                        }
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    
    # Enviar mensagem
    print("📨 Enviando webhook de teste...")
    success = rabbitmq_manager.publish_webhook_event('webhook_received', test_webhook_data)
    
    if success:
        print("✅ Mensagem enviada com sucesso!")
    else:
        print("❌ Falha ao enviar mensagem")
        return False
    
    # Enviar mensagem individual
    test_message_data = {
        "id": "individual_test_message",
        "from": "5511888888888",
        "timestamp": str(int(time.time())),
        "type": "text",
        "text": {
            "body": "Teste de mensagem individual"
        }
    }
    
    print("📱 Enviando mensagem individual...")
    success = rabbitmq_manager.publish_webhook_event('message_received', test_message_data)
    
    if success:
        print("✅ Mensagem individual enviada!")
    else:
        print("❌ Falha ao enviar mensagem individual")
        return False
    
    # Enviar status de teste
    test_status_data = {
        "id": "test_message_status",
        "status": "delivered",
        "timestamp": str(int(time.time())),
        "recipient_id": "5511999999999"
    }
    
    print("📊 Enviando status de teste...")
    success = rabbitmq_manager.publish_webhook_event('status_update', test_status_data)
    
    if success:
        print("✅ Status enviado!")
        return True
    else:
        print("❌ Falha ao enviar status")
        return False

def show_queue_status():
    """Mostra o status das filas"""
    print("\n📋 STATUS DAS FILAS")
    print("=" * 50)
    
    status = rabbitmq_manager.get_status()
    
    if status.get('status') == 'connected':
        queues = status.get('queues', {})
        
        if queues:
            for queue_name, queue_info in queues.items():
                message_count = queue_info.get('message_count', 0)
                consumer_count = queue_info.get('consumer_count', 0)
                print(f"📬 {queue_name}:")
                print(f"   📨 Mensagens: {message_count}")
                print(f"   👥 Consumidores: {consumer_count}")
        else:
            print("⚠️ Nenhuma informação de fila disponível")
    else:
        print(f"❌ RabbitMQ status: {status.get('status', 'unknown')}")

def test_worker_simulation():
    """Simula o processamento de mensagens como um worker"""
    print("\n👷 SIMULAÇÃO DE WORKER")
    print("=" * 50)
    
    print("🎧 Tentando consumir 1 mensagem da fila webhook_messages...")
    
    def process_message(message):
        print(f"📨 Mensagem recebida: {json.dumps(message, indent=2)}")
        
        event_type = message.get('event_type')
        event_data = message.get('event_data')
        
        print(f"🔍 Processando evento: {event_type}")
        
        # Simular processamento
        time.sleep(1)
        
        print("✅ Mensagem processada com sucesso!")
        return True
    
    try:
        # Consumir apenas 1 mensagem para teste
        print("⏳ Aguardando mensagem por 10 segundos...")
        
        # Criar um timeout manual
        start_time = time.time()
        timeout = 10
        
        def timeout_callback(message):
            if time.time() - start_time > timeout:
                print("⏰ Timeout atingido")
                return False
            return process_message(message)
        
        rabbitmq_manager.consume_messages('webhook_messages', timeout_callback, auto_ack=False)
        
    except KeyboardInterrupt:
        print("⏹️ Teste interrompido pelo usuário")
    except Exception as e:
        print(f"❌ Erro no teste do worker: {e}")

def main():
    """Função principal do teste"""
    print("🧪 TESTE COMPLETO DO RABBITMQ")
    print("=" * 60)
    print("Este script testa todas as funcionalidades do RabbitMQ")
    print("=" * 60)
    
    # 1. Testar conexão
    if not test_rabbitmq_connection():
        print("\n❌ Falha na conexão. Verifique se o RabbitMQ está rodando.")
        return False
    
    # 2. Mostrar status inicial das filas
    show_queue_status()
    
    # 3. Testar envio de mensagens
    if not test_message_publishing():
        print("\n❌ Falha no envio de mensagens.")
        return False
    
    # 4. Mostrar status após envio
    print("\n🔄 Status após envio de mensagens:")
    show_queue_status()
    
    # 5. Simular worker (opcional)
    print("\n❓ Deseja testar o consumo de mensagens? (s/n): ", end="")
    try:
        response = input().lower()
        if response in ['s', 'sim', 'y', 'yes']:
            test_worker_simulation()
    except KeyboardInterrupt:
        print("\n⏹️ Teste cancelado")
    
    # 6. Status final
    print("\n📊 STATUS FINAL:")
    show_queue_status()
    
    # 7. Limpeza
    print("\n🧹 Desconectando...")
    rabbitmq_manager.disconnect()
    
    print("\n🎉 TESTE CONCLUÍDO COM SUCESSO!")
    return True

if __name__ == '__main__':
    main() 