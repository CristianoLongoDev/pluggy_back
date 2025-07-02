import pika
import json
import logging
import threading
import time
from typing import Optional, Dict, Any, Callable
from config import (
    RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_ENABLED,
    WEBHOOK_QUEUE, MESSAGE_QUEUE, STATUS_QUEUE, ERROR_QUEUE
)

logger = logging.getLogger(__name__)

class RabbitMQManager:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.enabled = RABBITMQ_ENABLED
        self._lock = threading.Lock()
        self.queues = [WEBHOOK_QUEUE, MESSAGE_QUEUE, STATUS_QUEUE, ERROR_QUEUE]
        
    def _get_connection_params(self):
        """Retorna os parâmetros de conexão do RabbitMQ"""
        return pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD),
            heartbeat=600,
            blocked_connection_timeout=300
        )
    
    def connect(self, max_retries=3):
        """Estabelece conexão com o RabbitMQ"""
        if not self.enabled:
            logger.info("RabbitMQ desabilitado")
            return False
            
        with self._lock:
            try:
                # Fechar conexão existente se houver
                self.disconnect()
                
                # Criar nova conexão
                params = self._get_connection_params()
                self.connection = pika.BlockingConnection(params)
                self.channel = self.connection.channel()
                
                # Declarar filas
                self._declare_queues()
                
                logger.info("✅ Conectado ao RabbitMQ com sucesso")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erro ao conectar ao RabbitMQ: {e}")
                self.connection = None
                self.channel = None
                return False
    
    def _declare_queues(self):
        """Declara todas as filas necessárias"""
        try:
            for queue_name in self.queues:
                self.channel.queue_declare(
                    queue=queue_name,
                    durable=True  # Fila persistente
                )
                logger.info(f"📝 Fila '{queue_name}' declarada")
        except Exception as e:
            logger.error(f"❌ Erro ao declarar filas: {e}")
            raise
    
    def disconnect(self):
        """Fecha a conexão com o RabbitMQ"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("🔌 Conexão RabbitMQ fechada")
        except Exception as e:
            logger.error(f"❌ Erro ao fechar conexão RabbitMQ: {e}")
        finally:
            self.channel = None
            self.connection = None
    
    def _ensure_connection(self):
        """Garante que há uma conexão ativa"""
        if not self.enabled:
            return False
            
        try:
            # Verifica se a conexão está ativa
            if (self.connection and not self.connection.is_closed and 
                self.channel and not self.channel.is_closed):
                return True
            
            # Reconecta se necessário
            logger.info("🔄 Reconectando ao RabbitMQ...")
            return self.connect()
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar conexão RabbitMQ: {e}")
            return False
    
    def publish_message(self, queue_name: str, message: Dict[Any, Any], 
                       routing_key: str = None) -> bool:
        """Publica uma mensagem na fila especificada"""
        if not self.enabled:
            logger.warning("⚠️ RabbitMQ desabilitado - mensagem não enviada")
            return False
            
        with self._lock:
            try:
                if not self._ensure_connection():
                    logger.error("❌ Não foi possível conectar ao RabbitMQ")
                    return False
                
                # Preparar mensagem
                message_body = json.dumps(message, ensure_ascii=False)
                
                # Publicar mensagem
                self.channel.basic_publish(
                    exchange='',
                    routing_key=routing_key or queue_name,
                    body=message_body,
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Mensagem persistente
                        timestamp=int(time.time()),
                        content_type='application/json'
                    )
                )
                
                logger.info(f"📤 Mensagem enviada para fila '{queue_name}'")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erro ao publicar mensagem: {e}")
                # Tentar reconectar para próxima tentativa
                try:
                    self.disconnect()
                except:
                    pass
                return False
    
    def publish_webhook_event(self, event_type: str, event_data: Dict[Any, Any]) -> bool:
        """Publica um evento do webhook na fila apropriada"""
        message = {
            'event_type': event_type,
            'event_data': event_data,
            'timestamp': time.time(),
            'processed': False
        }
        
        # Escolher fila baseada no tipo de evento
        if event_type in ['message_received', 'webhook_received']:
            queue = WEBHOOK_QUEUE  # Mensagens novas vão para webhook_messages
        elif event_type in ['status_update']:
            queue = STATUS_QUEUE
        elif event_type in ['webhook_error', 'webhook_critical_error']:
            queue = ERROR_QUEUE
        else:
            queue = WEBHOOK_QUEUE
            
        return self.publish_message(queue, message)
    
    def consume_messages(self, queue_name: str, callback: Callable, 
                        auto_ack: bool = False) -> bool:
        """Consome mensagens de uma fila específica"""
        if not self.enabled:
            logger.warning("⚠️ RabbitMQ desabilitado - não é possível consumir")
            return False
            
        try:
            if not self._ensure_connection():
                logger.error("❌ Não foi possível conectar ao RabbitMQ para consumir")
                return False
            
            def wrapper_callback(ch, method, properties, body):
                try:
                    # Decodificar mensagem
                    message = json.loads(body.decode('utf-8'))
                    
                    # Chamar callback do usuário
                    result = callback(message)
                    
                    # Confirmar processamento se auto_ack for False
                    if not auto_ack:
                        if result:
                            ch.basic_ack(delivery_tag=method.delivery_tag)
                            logger.info(f"✅ Mensagem processada com sucesso da fila '{queue_name}'")
                        else:
                            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                            logger.warning(f"⚠️ Mensagem rejeitada e recolocada na fila '{queue_name}'")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao processar mensagem da fila '{queue_name}': {e}")
                    if not auto_ack:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            
            # Configurar consumidor
            self.channel.basic_qos(prefetch_count=1)  # Processar uma mensagem por vez
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=wrapper_callback,
                auto_ack=auto_ack
            )
            
            logger.info(f"🎧 Iniciando consumo da fila '{queue_name}'...")
            self.channel.start_consuming()
            
            return True
            
        except KeyboardInterrupt:
            logger.info("⏹️ Consumo interrompido pelo usuário")
            self.channel.stop_consuming()
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao consumir mensagens da fila '{queue_name}': {e}")
            return False
    
    def get_queue_info(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """Retorna informações sobre uma fila"""
        try:
            if not self._ensure_connection():
                return None
                
            method = self.channel.queue_declare(queue=queue_name, passive=True)
            return {
                'queue': queue_name,
                'message_count': method.method.message_count,
                'consumer_count': method.method.consumer_count
            }
        except Exception as e:
            logger.error(f"❌ Erro ao obter informações da fila '{queue_name}': {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna o status do RabbitMQ e suas filas"""
        if not self.enabled:
            return {'status': 'disabled'}
            
        try:
            if not self._ensure_connection():
                return {'status': 'disconnected'}
            
            status = {
                'status': 'connected',
                'host': RABBITMQ_HOST,
                'port': RABBITMQ_PORT,
                'queues': {}
            }
            
            for queue_name in self.queues:
                queue_info = self.get_queue_info(queue_name)
                if queue_info:
                    status['queues'][queue_name] = queue_info
                    
            return status
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter status do RabbitMQ: {e}")
            return {'status': 'error', 'error': str(e)}

# Instância global do gerenciador RabbitMQ
rabbitmq_manager = RabbitMQManager() 