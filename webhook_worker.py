#!/usr/bin/env python3
"""
Worker para processar mensagens do webhook via RabbitMQ
Este worker consome mensagens das filas e processa de forma assíncrona
"""

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from config import (
    WEBHOOK_QUEUE, MESSAGE_QUEUE, STATUS_QUEUE, ERROR_QUEUE,
    LOG_LEVEL, RABBITMQ_ENABLED
)
from rabbitmq_manager import rabbitmq_manager
from database import db_manager

# Configurar logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/webhook_worker.log')
    ]
)
logger = logging.getLogger(__name__)

class WebhookWorker:
    def __init__(self):
        self.running = True
        self.processed_count = 0
        self.error_count = 0
        
        # Configurar handler para interrupção
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handler para sinais de interrupção"""
        logger.info(f"📡 Sinal {signum} recebido. Parando worker...")
        self.running = False
        if rabbitmq_manager.channel:
            rabbitmq_manager.channel.stop_consuming()
    
    def process_webhook_message(self, message):
        """Processa uma mensagem genérica do webhook"""
        try:
            event_type = message.get('event_type', 'unknown')
            event_data = message.get('event_data', {})
            timestamp = message.get('timestamp', time.time())
            
            logger.info(f"📨 Processando evento: {event_type}")
            
            # Salvar no banco de dados se disponível
            if db_manager.enabled:
                success = db_manager.save_webhook_event(event_type, event_data)
                if success:
                    logger.info(f"💾 Evento {event_type} salvo no banco")
                else:
                    logger.warning(f"⚠️ Falha ao salvar evento {event_type} no banco")
            
            # Processar lógica específica baseada no tipo
            if event_type == 'webhook_received':
                self._process_webhook_received(event_data)
            elif event_type == 'message_received':
                self._process_message_received(event_data)
            elif event_type == 'status_update':
                self._process_status_update(event_data)
            elif 'error' in event_type:
                self._process_error(event_data)
            
            self.processed_count += 1
            logger.info(f"✅ Evento processado com sucesso. Total: {self.processed_count}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem: {e}")
            self.error_count += 1
            return False
    
    def _process_webhook_received(self, event_data):
        """Processa webhook completo recebido"""
        logger.info("🔄 Processando webhook completo...")
        
        # Verificar se é evento do WhatsApp
        if event_data.get('object') == 'whatsapp_business_account':
            entries = event_data.get('entry', [])
            logger.info(f"📬 Webhook contém {len(entries)} entradas")
            
            for entry in entries:
                changes = entry.get('changes', [])
                for change in changes:
                    value = change.get('value', {})
                    
                    # Processar mensagens
                    if 'messages' in value:
                        for message in value['messages']:
                            logger.info(f"📱 Mensagem detectada de: {message.get('from')}")
                    
                    # Processar status
                    if 'statuses' in value:
                        for status in value['statuses']:
                            logger.info(f"📊 Status detectado: {status.get('status')}")
    
    def _process_message_received(self, event_data):
        """Processa mensagem individual recebida"""
        message_type = event_data.get('type', 'unknown')
        from_number = event_data.get('from')
        message_id = event_data.get('id')
        
        logger.info(f"💬 Processando mensagem {message_type} de {from_number} (ID: {message_id})")
        
        # CHATGPT BOT: Processar apenas mensagens de texto
        if message_type == 'text':
            text_body = event_data.get('text', {}).get('body', '')
            logger.info(f"📝 Conteúdo da mensagem: {text_body[:100]}...")
            
            # Processar com ChatGPT
            try:
                self._process_chatgpt_response(from_number, text_body)
            except Exception as e:
                logger.error(f"Erro ao processar ChatGPT: {e}")
        
        else:
            logger.info(f"📨 Tipo de mensagem {message_type} não processado pelo bot")
            
    def _process_chatgpt_response(self, contact_id, message_text):
        """Processa mensagem com ChatGPT e envia resposta"""
        try:
            # Importar serviços aqui para evitar problemas de inicialização
            from chatgpt_service import chatgpt_service
            from whatsapp_service import whatsapp_service
            
            logger.info(f"🤖 Processando mensagem com ChatGPT para {contact_id}")
            
            # Gerar resposta com ChatGPT
            chatgpt_response = chatgpt_service.process_message(contact_id, message_text)
            
            if chatgpt_response:
                logger.info(f"✅ ChatGPT respondeu: {chatgpt_response[:50]}...")
                
                # Enviar resposta via WhatsApp
                sent = whatsapp_service.process_outgoing_message(contact_id, chatgpt_response)
                
                if sent:
                    logger.info(f"📤 Resposta enviada com sucesso para {contact_id}")
                else:
                    logger.warning(f"⚠️ Falha ao enviar resposta para {contact_id}")
            else:
                logger.warning(f"⚠️ ChatGPT não gerou resposta para {contact_id}")
                
        except Exception as e:
            logger.error(f"❌ Erro no processamento ChatGPT para {contact_id}: {e}")
            # Em caso de erro, enviar mensagem padrão (opcional)
            try:
                from whatsapp_service import whatsapp_service
                whatsapp_service.process_outgoing_message(
                    contact_id, 
                    "Desculpe, estou com dificuldades técnicas no momento. Tente novamente em alguns minutos."
                )
            except:
                pass
    
    def _process_status_update(self, event_data):
        """Processa atualização de status"""
        status = event_data.get('status')
        message_id = event_data.get('id')
        recipient_id = event_data.get('recipient_id')
        
        logger.info(f"📈 Status '{status}' para mensagem {message_id} (destinatário: {recipient_id})")
        
        # Aqui você pode implementar:
        # - Atualização de status no CRM
        # - Notificações para usuários
        # - Métricas de entrega
    
    def _process_error(self, event_data):
        """Processa erros do webhook"""
        error_msg = event_data.get('error', 'Erro desconhecido')
        logger.error(f"🚨 Erro do webhook: {error_msg}")
        
        # Aqui você pode implementar:
        # - Alertas para administradores
        # - Retry automático
        # - Análise de erros
    
    def start_consuming(self, queue_name):
        """Inicia o consumo de uma fila específica"""
        if not RABBITMQ_ENABLED:
            logger.error("❌ RabbitMQ está desabilitado")
            return False
        
        logger.info(f"🚀 Iniciando worker para fila: {queue_name}")
        logger.info("=" * 60)
        logger.info(f"Worker PID: {os.getpid()}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("=" * 60)
        
        try:
            # Conectar ao RabbitMQ
            if not rabbitmq_manager.connect():
                logger.error("❌ Falha ao conectar ao RabbitMQ")
                return False
            
            # Consumir mensagens
            def callback(message):
                if not self.running:
                    return False
                return self.process_webhook_message(message)
            
            logger.info(f"🎧 Aguardando mensagens da fila '{queue_name}'...")
            rabbitmq_manager.consume_messages(queue_name, callback, auto_ack=False)
            
        except KeyboardInterrupt:
            logger.info("⏹️ Parando worker por interrupção do usuário")
        except Exception as e:
            logger.error(f"❌ Erro no worker: {e}")
        finally:
            self._cleanup()
        
        return True
    
    def _cleanup(self):
        """Limpa recursos antes de finalizar"""
        logger.info("🧹 Realizando limpeza...")
        
        # Fechar conexões
        try:
            rabbitmq_manager.disconnect()
            db_manager.disconnect()
        except Exception as e:
            logger.error(f"❌ Erro na limpeza: {e}")
        
        # Log final
        logger.info("=" * 60)
        logger.info("📊 ESTATÍSTICAS DO WORKER")
        logger.info(f"✅ Mensagens processadas: {self.processed_count}")
        logger.info(f"❌ Erros encontrados: {self.error_count}")
        logger.info(f"⏰ Tempo de execução: {datetime.now().isoformat()}")
        logger.info("=" * 60)
        logger.info("🏁 Worker finalizado")

def main():
    """Função principal do worker"""
    import os
    
    # Verificar argumentos
    if len(sys.argv) < 2:
        print("Uso: python webhook_worker.py <queue_name>")
        print("Filas disponíveis:")
        print(f"  - {WEBHOOK_QUEUE} (webhook geral)")
        print(f"  - {MESSAGE_QUEUE} (mensagens)")
        print(f"  - {STATUS_QUEUE} (status)")
        print(f"  - {ERROR_QUEUE} (erros)")
        sys.exit(1)
    
    queue_name = sys.argv[1]
    valid_queues = [WEBHOOK_QUEUE, MESSAGE_QUEUE, STATUS_QUEUE, ERROR_QUEUE]
    
    if queue_name not in valid_queues:
        logger.error(f"❌ Fila inválida: {queue_name}")
        logger.info(f"Filas válidas: {', '.join(valid_queues)}")
        sys.exit(1)
    
    # Iniciar worker
    worker = WebhookWorker()
    worker.start_consuming(queue_name)

if __name__ == '__main__':
    main() 