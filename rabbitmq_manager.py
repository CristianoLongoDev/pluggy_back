import pika
import json
import logging
import threading
import time
from typing import Optional, Dict, Any, Callable
from config import (
    RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_ENABLED,
    WEBHOOK_QUEUE, MESSAGE_QUEUE, STATUS_QUEUE, ERROR_QUEUE, CHATGPT_DELAY_QUEUE
)

logger = logging.getLogger(__name__)

class RabbitMQManager:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.enabled = RABBITMQ_ENABLED
        self._lock = threading.Lock()
        self.queues = [WEBHOOK_QUEUE, MESSAGE_QUEUE, STATUS_QUEUE, ERROR_QUEUE, CHATGPT_DELAY_QUEUE]
        self._last_status_check = 0
        self._status_cache = None
        self._status_cache_duration = 5  # Cache por 5 segundos
        self._last_health_check = 0  # Para monitoramento de saúde
        
    def _get_connection_params(self):
        """Retorna os parâmetros de conexão do RabbitMQ com configurações otimizadas"""
        return pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD),
            heartbeat=60,  # Reduzido para 60s para detectar problemas mais rápido
            blocked_connection_timeout=15,  # Reduzido para 15s
            connection_attempts=3,  # Reduzido para 3 tentativas (mais rápido)
            retry_delay=2,  # Reduzido para 2s entre tentativas
            socket_timeout=15,  # Aumentado para 15s
            tcp_options={
                'TCP_KEEPIDLE': 30,   # Reduzido para 30s
                'TCP_KEEPINTVL': 5,   # Reduzido para 5s
                'TCP_KEEPCNT': 3      # Reduzido para 3 tentativas
            }
        )
    
    def connect(self, max_retries=3):
        """Estabelece conexão com o RabbitMQ com retry automático"""
        if not self.enabled:
            logger.info("RabbitMQ desabilitado")
            return False
            
        with self._lock:
            for attempt in range(max_retries):
                try:
                    # Fechar conexão existente se houver
                    self.disconnect()
                    
                    # Criar nova conexão
                    params = self._get_connection_params()
                    logger.info(f"🔄 Tentativa {attempt + 1}/{max_retries} de conexão ao RabbitMQ...")
                    self.connection = pika.BlockingConnection(params)
                    self.channel = self.connection.channel()
                    
                    # Declarar filas
                    self._declare_queues()
                    
                    logger.info("✅ Conectado ao RabbitMQ com sucesso")
                    return True
                    
                except Exception as e:
                    logger.warning(f"⚠️ Tentativa {attempt + 1}/{max_retries} falhou: {e}")
                    self.disconnect()
                    
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # Backoff exponencial: 2s, 4s, 6s
                        logger.info(f"🔄 Aguardando {wait_time}s antes da próxima tentativa...")
                        time.sleep(wait_time)
                        
            logger.error(f"❌ Falha ao conectar ao RabbitMQ após {max_retries} tentativas")
            return False
    
    def _declare_queues(self):
        """Declara todas as filas necessárias com particionamento"""
        try:
            # === FASE 1: EXCHANGES DELAYED (compatibilidade) ===
            try:
                self.channel.exchange_declare(
                    exchange='chatgpt_delayed',
                    exchange_type='x-delayed-message',
                    arguments={'x-delayed-type': 'direct'},
                    durable=True
                )
                logger.info("📝 Exchange delayed 'chatgpt_delayed' declarado")
                self.delayed_exchange_available = True
            except Exception as e:
                logger.warning(f"⚠️ Plugin delayed exchange não disponível: {e}")
                self.delayed_exchange_available = False
            
            # === FASE 2: EXCHANGES PARA PARTICIONAMENTO ===
            
            # Exchange principal para incoming messages com consistent hash
            try:
                self.channel.exchange_declare(
                    exchange='incoming.messages',
                    exchange_type='x-consistent-hash',
                    durable=True,
                    arguments={
                        'hash-header': 'conversation_id'  # Hash baseado no conversation_id
                    }
                )
                logger.info("📝 Exchange 'incoming.messages' (x-consistent-hash) declarado")
                self.consistent_hash_available = True
            except Exception as e:
                logger.warning(f"⚠️ Plugin consistent hash não disponível: {e}")
                self.consistent_hash_available = False
            
            # Exchange para outgoing messages
            self.channel.exchange_declare(
                exchange='outgoing.whatsapp',
                exchange_type='topic',
                durable=True
            )
            logger.info("📝 Exchange 'outgoing.whatsapp' (topic) declarado")
            
            # Exchange para notificações websocket
            self.channel.exchange_declare(
                exchange='notify.websocket',
                exchange_type='fanout',
                durable=True
            )
            logger.info("📝 Exchange 'notify.websocket' (fanout) declarado")
            
            # === FILAS TRADICIONAIS (compatibilidade) ===
            
            # Declarar filas normais
            for queue_name in self.queues:
                self.channel.queue_declare(
                    queue=queue_name,
                    durable=True  # Fila persistente
                )
                logger.info(f"📝 Fila '{queue_name}' declarada")
                
            # Declarar fila para delayed messages
            self.channel.queue_declare(
                queue='chatgpt_process',
                durable=True
            )
            logger.info("📝 Fila 'chatgpt_process' declarada")
            
            # Bind fila ao exchange delayed (só se exchange disponível)
            if hasattr(self, 'delayed_exchange_available') and self.delayed_exchange_available:
                try:
                    self.channel.queue_bind(
                        exchange='chatgpt_delayed',
                        queue='chatgpt_process',
                        routing_key='process'
                    )
                    logger.info("📝 Bind fila 'chatgpt_process' ao exchange delayed")
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao fazer bind delayed: {e}")
            
            # === FILAS PARTICIONADAS PARA MESSAGE WORKERS ===
            
            if hasattr(self, 'consistent_hash_available') and self.consistent_hash_available:
                # Criar 4 partições para distribuir conversas conforme deployment
                num_partitions = 4
                
                for partition in range(num_partitions):
                    # Fila particionada para message workers
                    queue_name = f'msg-worker.q.{partition}'
                    try:
                        self.channel.queue_declare(
                            queue=queue_name,
                            durable=True,
                            arguments={
                                'x-queue-type': 'quorum',  # Quorum queue para alta disponibilidade
                                'x-max-length': 10000,     # Limite de mensagens
                                'x-overflow': 'reject-publish-dlx'
                            }
                        )
                        
                        # Bind da fila particionada ao exchange de consistent hash
                        # IMPORTANT: Consistent hash usa peso no binding, não routing key específica
                        self.channel.queue_bind(
                            exchange='incoming.messages',
                            queue=queue_name,
                            routing_key=str(partition + 1)  # Routing key deve ser > 0 (1,2,3,4)
                        )
                        
                        logger.info(f"✅ Partição {partition} criada: {queue_name}")
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Fallback para fila normal - Quorum não suportado: {e}")
                        # Fallback para fila normal se quorum não suportado
                        self.channel.queue_declare(
                            queue=queue_name,
                            durable=True
                        )
                        
                        self.channel.queue_bind(
                            exchange='incoming.messages',
                            queue=queue_name,
                            routing_key=str(partition)
                        )
                        
                        logger.info(f"✅ Partição {partition} criada (fila normal): {queue_name}")
                
                logger.info(f"🎯 {num_partitions} partições criadas para message workers")
            
            # === FILAS PARA OUTGOING MESSAGES ===
            
            # Fila para envio de mensagens WhatsApp
            try:
                self.channel.queue_declare(
                    queue='whatsapp_sender',
                    durable=True,
                    arguments={'x-queue-type': 'quorum'}
                )
            except:
                # Fallback para fila normal
                self.channel.queue_declare(
                    queue='whatsapp_sender',
                    durable=True
                )
            
            self.channel.queue_bind(
                exchange='outgoing.whatsapp',
                queue='whatsapp_sender',
                routing_key='send.whatsapp'
            )
            logger.info("📝 Fila 'whatsapp_sender' declarada e vinculada")
            
            # Fila para notificações websocket
            self.channel.queue_declare(
                queue='websocket_notifications',
                durable=True
            )
            
            self.channel.queue_bind(
                exchange='notify.websocket',
                queue='websocket_notifications',
                routing_key=''  # Fanout não usa routing key
            )
            logger.info("📝 Fila 'websocket_notifications' declarada e vinculada")
                
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
        """Garante que há uma conexão ativa com verificação aprimorada"""
        if not self.enabled:
            return False
            
        try:
            # Verificação mais robusta da conexão
            if self._is_connection_healthy():
                return True
            
            # Reconecta se necessário
            logger.info("🔄 Reconectando ao RabbitMQ...")
            return self.connect()
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar conexão RabbitMQ: {e}")
            return False
    
    def _is_connection_healthy(self):
        """Verifica se a conexão está realmente saudável"""
        try:
            # Verificações básicas
            if not self.connection or self.connection.is_closed:
                return False
            if not self.channel or self.channel.is_closed:
                return False
            
            # Teste de ping para verificar se a conexão está realmente ativa
            # Usando uma operação leve que força comunicação com o servidor
            self.connection.process_data_events(time_limit=0.1)
            return True
            
        except Exception as e:
            logger.debug(f"🔍 Conexão não está saudável: {e}")
            return False
    
    def publish_message(self, queue_name: str, message: Dict[Any, Any], 
                       routing_key: str = None) -> bool:
        """Publica uma mensagem na fila especificada"""
        if not self.enabled:
            logger.warning("⚠️ RabbitMQ desabilitado - mensagem não enviada")
            return False
            
        # Verificar conexão com lock mínimo
        if not self._ensure_connection():
            logger.error("❌ Não foi possível conectar ao RabbitMQ")
            return False
        
        try:
            # Preparar mensagem
            message_body = json.dumps(message, ensure_ascii=False)
            
            # Publicar mensagem (operação atômica do pika, sem lock)
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
            # Invalidar conexão com lock apenas para thread safety
            with self._lock:
                self.connection = None
                self.channel = None
            return False
    
    def publish_with_delay(self, message: Dict[Any, Any], delay_seconds: int = 10) -> bool:
        """Publica uma mensagem com delay usando RabbitMQ delayed exchange"""
        if not self.enabled:
            logger.warning("⚠️ RabbitMQ desabilitado - mensagem delayed não enviada")
            return False
            
        with self._lock:
            try:
                if not self._ensure_connection():
                    logger.error("❌ Não foi possível conectar ao RabbitMQ")
                    return False
                
                # Preparar mensagem
                message_body = json.dumps(message, ensure_ascii=False)
                delay_ms = delay_seconds * 1000  # Converter para milissegundos
                
                # Verificar se delayed exchange está disponível
                if hasattr(self, 'delayed_exchange_available') and self.delayed_exchange_available:
                    try:
                        # Validar connection e channel antes de enviar
                        if not self.connection or self.connection.is_closed:
                            logger.warning("⚠️ Conexão RabbitMQ fechada, reconectando...")
                            if not self._ensure_connection():
                                raise Exception("Falha ao reconectar")
                        
                        if not self.channel or self.channel.is_closed:
                            logger.warning("⚠️ Canal RabbitMQ fechado, reconectando...")
                            if not self._ensure_connection():
                                raise Exception("Falha ao recriar canal")
                        
                        self.channel.basic_publish(
                            exchange='chatgpt_delayed',
                            routing_key='process',
                            body=message_body,
                            properties=pika.BasicProperties(
                                delivery_mode=2,  # Mensagem persistente
                                timestamp=int(time.time()),
                                content_type='application/json',
                                headers={'x-delay': delay_ms}  # Delay em milissegundos
                            )
                        )
                        logger.info(f"📤 Mensagem delayed enviada ({delay_seconds}s) para exchange 'chatgpt_delayed'")
                        return True
                        
                    except Exception as delayed_error:
                        logger.warning(f"⚠️ Delayed exchange falhou: {delayed_error}")
                        self.delayed_exchange_available = False
                        # Forçar reconexão na próxima tentativa
                        try:
                            if self.connection and not self.connection.is_closed:
                                self.connection.close()
                        except:
                            pass
                        self.connection = None
                        self.channel = None
                
                # Fallback: processar imediatamente sem delay
                logger.warning(f"🚀 Plugin delayed não disponível, enviando para processamento direto")
                return self.publish_message('chatgpt_process', message)
                
            except Exception as e:
                logger.error(f"❌ Erro ao publicar mensagem delayed: {e}")
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
            queue = WEBHOOK_QUEUE  # Mensagens vão para webhook_messages
        elif event_type in ['status_update']:
            queue = STATUS_QUEUE
        elif event_type in ['webhook_error', 'webhook_critical_error']:
            queue = ERROR_QUEUE
        else:
            queue = WEBHOOK_QUEUE  # Padrão para webhook_messages
            
        return self.publish_message(queue, message)
    
    # === MÉTODOS PARA PARTICIONAMENTO - FASE 2 ===
    
    def publish_to_partition(self, conversation_id: int, message_data: Dict, exchange: str = 'incoming.messages') -> bool:
        """
        Publica mensagem usando particionamento por conversation_id
        
        Args:
            conversation_id: ID da conversa para determinar partição
            message_data: Dados da mensagem
            exchange: Exchange a ser usado (padrão: incoming.messages)
        """
        if not self.enabled:
            logger.warning("⚠️ RabbitMQ desabilitado - mensagem particionada não enviada")
            return False
        
        with self._lock:
            try:
                if not self._ensure_connection():
                    logger.error("❌ Conexão RabbitMQ indisponível")
                    return False
                
                # Verificar se consistent hash está disponível
                if not hasattr(self, 'consistent_hash_available') or not self.consistent_hash_available:
                    logger.warning("⚠️ Consistent hash não disponível - usando distribuição manual para partições")
                    # Usar distribuição manual para filas particionadas
                    queue_name = self.get_partition_queue_name(conversation_id)
                    message = {
                        'conversation_id': conversation_id,
                        'timestamp': time.time(),
                        **message_data
                    }
                    return self.publish_message(queue_name, message)
                
                # Preparar mensagem com conversation_id no header
                message = {
                    'conversation_id': conversation_id,
                    'timestamp': time.time(),
                    **message_data
                }
                
                # Headers para o consistent hash
                headers = {
                    'conversation_id': str(conversation_id)  # Header usado para particionamento
                }
                
                # Publicar no exchange de consistent hash
                # IMPORTANT: Usar routing key baseada no hash para distribuição (4 partições)
                routing_key = str(conversation_id % 4)  # 0, 1, 2, ou 3 (4 partições)
                
                self.channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,  # Routing key baseada no hash
                    body=json.dumps(message, ensure_ascii=False),
                    properties=pika.BasicProperties(
                        headers=headers,
                        delivery_mode=2,  # Mensagem persistente
                        timestamp=int(time.time()),
                        content_type='application/json'
                    )
                )
                
                logger.info(f"📤 Mensagem particionada publicada: conversation_id={conversation_id}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erro ao publicar mensagem particionada: {e}")
                return False
    
    def publish_outgoing_message(self, routing_key: str, message_data: Dict) -> bool:
        """
        Publica mensagem de saída (WhatsApp, WebSocket, etc.)
        
        Args:
            routing_key: Chave de roteamento (ex: 'send.whatsapp', 'notify.websocket')
            message_data: Dados da mensagem
        """
        if not self.enabled:
            logger.warning("⚠️ RabbitMQ desabilitado - mensagem de saída não enviada")
            return False
        
        with self._lock:
            try:
                if not self._ensure_connection():
                    logger.error("❌ Conexão RabbitMQ indisponível")
                    return False
                
                message = {
                    'timestamp': time.time(),
                    **message_data
                }
                
                # Determinar exchange baseado no routing key
                if routing_key.startswith('send.'):
                    exchange = 'outgoing.whatsapp'
                elif routing_key.startswith('notify.'):
                    exchange = 'notify.websocket'
                else:
                    exchange = 'outgoing.whatsapp'  # Fallback
                
                self.channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=json.dumps(message, ensure_ascii=False),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Mensagem persistente
                        timestamp=int(time.time()),
                        content_type='application/json'
                    )
                )
                
                logger.info(f"📤 Mensagem de saída publicada: {routing_key}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erro ao publicar mensagem de saída: {e}")
                return False
    
    def get_partition_queue_name(self, conversation_id: int, num_partitions: int = 4) -> str:
        """
        Calcula o nome da fila baseado no conversation_id
        
        Args:
            conversation_id: ID da conversa
            num_partitions: Número total de partições
            
        Returns:
            Nome da fila da partição correspondente
        """
        partition = conversation_id % num_partitions
        return f'msg-worker.q.{partition}'
    
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
            self.channel.basic_qos(prefetch_count=3)  # Processar até 3 mensagens simultaneamente
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
    
    def get_queue_info(self, queue_name: str, max_retries=2) -> Optional[Dict[str, Any]]:
        """Retorna informações sobre uma fila com retry logic"""
        for attempt in range(max_retries + 1):
            try:
                # CORREÇÃO: Usar timeout para evitar deadlock
                try:
                    if not self._lock.acquire(timeout=5):  # Timeout de 5s
                        logger.warning(f"⚠️ Timeout ao aguardar lock - tentativa {attempt + 1}/{max_retries + 1}")
                        if attempt == max_retries:
                            return None
                        time.sleep(0.1)
                        continue
                    
                    if not self._ensure_connection():
                        logger.warning(f"⚠️ Sem conexão RabbitMQ - tentativa {attempt + 1}/{max_retries + 1}")
                        if attempt == max_retries:
                            return None
                        time.sleep(0.1)  # Pequena pausa antes de tentar novamente
                        continue
                finally:
                    try:
                        self._lock.release()
                    except:
                        pass  # Lock já foi liberado
                
                # Verificar se o canal ainda está aberto
                if self.channel.is_closed:
                    logger.warning(f"⚠️ Canal fechado - tentativa {attempt + 1}/{max_retries + 1}")
                    if attempt == max_retries:
                        return None
                    # Tentar reconectar
                    if not self.connect():
                        continue
            
                # Tentar obter info da fila
                method = self.channel.queue_declare(queue=queue_name, passive=True)
                return {
                    'queue': queue_name,
                    'message_count': method.method.message_count,
                    'consumer_count': method.method.consumer_count
                }
                    
            except Exception as e:
                error_msg = str(e)
                if "Channel is closing" in error_msg or "Connection is closed" in error_msg:
                    logger.warning(f"⚠️ Canal/conexão fechada - tentativa {attempt + 1}/{max_retries + 1}")
                    # Forçar reconexão
                    try:
                        self.disconnect()
                    except:
                        pass
                    if attempt < max_retries:
                        time.sleep(0.2)  # Pausa maior para reconexão
                        continue
                else:
                    logger.error(f"❌ Erro ao obter informações da fila '{queue_name}': {e}")
                
                if attempt == max_retries:
                    return None
        
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna o status do RabbitMQ e suas filas com cache"""
        if not self.enabled:
            return {'status': 'disabled'}
            
        # Verificar cache
        current_time = time.time()
        if (self._status_cache and 
            current_time - self._last_status_check < self._status_cache_duration):
            return self._status_cache
            
        try:
            # Verificação básica de conectividade
            if not self._ensure_connection():
                self._status_cache = {'status': 'disconnected'}
                self._last_status_check = current_time
                return self._status_cache
            
            status = {
                'status': 'connected',
                'host': RABBITMQ_HOST,
                'port': RABBITMQ_PORT,
                'queues': {}
            }
            
            # Obter informações das filas de forma resiliente
            for queue_name in self.queues:
                try:
                    queue_info = self.get_queue_info(queue_name)
                    if queue_info:
                        status['queues'][queue_name] = queue_info
                    else:
                        status['queues'][queue_name] = {
                            'queue': queue_name,
                            'message_count': 'unknown',
                            'consumer_count': 'unknown',
                            'status': 'error'
                        }
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao obter info da fila '{queue_name}': {e}")
                    status['queues'][queue_name] = {
                        'queue': queue_name,
                        'message_count': 'error',
                        'consumer_count': 'error',
                        'status': 'error'
                    }
            
            # Cache do resultado
            self._status_cache = status
            self._last_status_check = current_time
            return status
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter status do RabbitMQ: {e}")
            self._status_cache = {'status': 'error', 'error': str(e)}
            self._last_status_check = current_time
            return self._status_cache

# Instância global do gerenciador RabbitMQ
rabbitmq_manager = RabbitMQManager() 