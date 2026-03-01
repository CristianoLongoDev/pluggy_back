#!/usr/bin/env python3
"""
Partitioned Message Worker - Worker que consome mensagens de uma partição específica
Garante que todas as mensagens de uma conversa sejam processadas em ordem na mesma partição
"""

import json
import logging
import os
import sys
import threading
import time
import signal
from typing import Optional
from rabbitmq_manager import rabbitmq_manager
from webhook_worker import WebhookWorker
from config import LOG_LEVEL

# Configurar logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/partitioned_message_worker.log')
    ]
)
logger = logging.getLogger(__name__)

class PartitionedMessageWorker:
    def __init__(self, partition_id: int = 0):
        """
        Inicializa worker para uma partição específica
        
        Args:
            partition_id: ID da partição (0-3)
        """
        self.partition_id = partition_id
        self.queue_name = f'msg-worker.q.{partition_id}'
        self.running = True
        self.processed_count = 0
        self.error_count = 0
        
        # Reusar a lógica do webhook worker
        self.webhook_worker = WebhookWorker()
        
        # Configurar handlers para interrupção
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"🎯 Worker inicializado para partição {partition_id}")
        logger.info(f"📥 Consumindo fila: {self.queue_name}")
    
    def _signal_handler(self, signum, frame):
        """Handler para sinais de interrupção"""
        logger.info(f"📡 Sinal {signum} recebido. Parando worker partição {self.partition_id}...")
        self.running = False
    
    def start(self):
        """Inicia o consumo da fila particionada"""
        logger.info("🚀 Iniciando Partitioned Message Worker...")
        logger.info("=" * 60)
        logger.info(f"Worker PID: {os.getpid()}")
        logger.info(f"Partição: {self.partition_id}")
        logger.info(f"Fila: {self.queue_name}")
        logger.info("=" * 60)
        
        # Verificar dependências
        if not self._check_dependencies():
            logger.error("❌ Dependências não disponíveis - parando")
            return False
        
        # Iniciar consumo
        try:
            self._start_consuming()
        except KeyboardInterrupt:
            logger.info("🛑 Interrompido pelo usuário")
        except Exception as e:
            logger.error(f"❌ Erro fatal: {e}")
            return False
        
        logger.info(f"🛑 Worker partição {self.partition_id} parado")
        return True
    
    def _check_dependencies(self):
        """Verifica se as dependências estão disponíveis"""
        # Verificar RabbitMQ
        if not rabbitmq_manager or not rabbitmq_manager.enabled:
            logger.error("❌ RabbitMQ não está disponível")
            return False
        
        # Tentar conectar ao RabbitMQ se não estiver conectado
        try:
            if not rabbitmq_manager.connect():
                logger.error("❌ Falha ao conectar ao RabbitMQ")
                return False
            
            logger.info("✅ RabbitMQ conectado com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao RabbitMQ: {e}")
            return False
        
        logger.info("✅ Dependências verificadas")
        return True
    
    def _start_consuming(self):
        """Inicia o consumo da fila particionada"""
        max_retries = 5
        retry_count = 0
        
        while self.running and retry_count < max_retries:
            try:
                logger.info(f"🔄 Tentando conectar ao RabbitMQ (tentativa {retry_count + 1})")
                
                # Conectar ao RabbitMQ
                if not rabbitmq_manager.connect():
                    logger.error("❌ Falha ao conectar ao RabbitMQ")
                    retry_count += 1
                    time.sleep(5)
                    continue
                
                # Configurar consumidor
                logger.info(f"📥 Configurando consumidor para fila: {self.queue_name}")
                
                # Verificar se a fila existe
                try:
                    rabbitmq_manager.channel.queue_declare(queue=self.queue_name, passive=True)
                except Exception as e:
                    logger.error(f"❌ Fila {self.queue_name} não existe: {e}")
                    logger.info("⚠️ Aguardando fila ser criada...")
                    time.sleep(10)
                    retry_count += 1
                    continue
                
                # Configurar QoS (prefetch)
                rabbitmq_manager.channel.basic_qos(prefetch_count=3)
                
                # Iniciar consumo
                rabbitmq_manager.channel.basic_consume(
                    queue=self.queue_name,
                    on_message_callback=self._process_partitioned_message,
                    auto_ack=False
                )
                
                logger.info(f"✅ Consumindo mensagens da partição {self.partition_id}")
                
                # Loop de consumo
                while self.running:
                    try:
                        rabbitmq_manager.connection.process_data_events(time_limit=1)
                        self._health_check()
                    except Exception as e:
                        logger.error(f"❌ Erro no processamento de eventos: {e}")
                        break
                
                break  # Sair do loop de retry se chegou até aqui
                
            except Exception as e:
                logger.error(f"❌ Erro ao iniciar consumo: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"🔄 Tentando novamente em 10 segundos...")
                    time.sleep(10)
                else:
                    logger.error(f"❌ Falha permanente após {max_retries} tentativas")
                    break
        
        # Cleanup
        try:
            if rabbitmq_manager.connection and not rabbitmq_manager.connection.is_closed:
                rabbitmq_manager.connection.close()
        except:
            pass
    
    def _process_partitioned_message(self, channel, method, properties, body):
        """
        Processa mensagem da fila particionada
        
        Args:
            channel: Canal RabbitMQ
            method: Método de entrega
            properties: Propriedades da mensagem
            body: Corpo da mensagem
        """
        try:
            # Parse da mensagem
            try:
                message_data = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"❌ Mensagem inválida na partição {self.partition_id}: {e}")
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return
            
            conversation_id = message_data.get('conversation_id')
            event_type = message_data.get('event_type')
            event_data = message_data.get('event_data')
            
            logger.info(f"🔍 PARTITIONED-DEBUG: message_data.keys() = {list(message_data.keys())}")
            logger.info(f"🔍 PARTITIONED-DEBUG: conversation_id={conversation_id}, event_type={event_type}")
            logger.info(f"🔍 PARTITIONED-DEBUG: event_data type={type(event_data)}, has_data={bool(event_data)}")
            
            logger.info(f"🎯 Processando mensagem particionada: conversation_id={conversation_id}, type={event_type}")
            
            # Verificar dados essenciais
            if not conversation_id or not event_data:
                logger.error(f"❌ Dados incompletos: conversation_id={conversation_id}, event_data={bool(event_data)}")
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return
            
            # Processar usando a lógica do webhook worker
            success = False
            try:
                if event_type == 'webhook_received':
                    # Processar webhook normalmente - montar estrutura correta
                    webhook_message = {
                        'event_type': event_type,
                        'event_data': event_data,
                        'timestamp': message_data.get('timestamp', time.time())
                    }
                    logger.info(f"🔧 PARTITIONED-DEBUG: Passando para webhook_worker: {list(webhook_message.keys())}")
                    success = self.webhook_worker.process_webhook_message(webhook_message)
                else:
                    logger.warning(f"⚠️ Tipo de evento não suportado: {event_type}")
                    success = True  # Ack para evitar reprocessamento
                
            except Exception as process_error:
                logger.error(f"❌ Erro ao processar mensagem: {process_error}")
                success = False
            
            # ACK/NACK baseado no resultado
            if success:
                channel.basic_ack(delivery_tag=method.delivery_tag)
                self.processed_count += 1
                logger.debug(f"✅ Mensagem processada com sucesso (partição {self.partition_id})")
            else:
                # Rejeitar sem requeue para evitar loops infinitos
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                self.error_count += 1
                logger.warning(f"⚠️ Mensagem rejeitada (partição {self.partition_id})")
            
        except Exception as e:
            logger.error(f"❌ Erro crítico ao processar mensagem: {e}")
            try:
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except:
                pass
            self.error_count += 1
    
    def _health_check(self):
        """Verifica saúde do worker e faz log de estatísticas"""
        current_time = time.time()
        
        # Log de estatísticas a cada 60 segundos
        if hasattr(self, '_last_stats_log'):
            if current_time - self._last_stats_log > 60:
                self._log_statistics()
                self._last_stats_log = current_time
        else:
            self._last_stats_log = current_time
    
    def _log_statistics(self):
        """Log das estatísticas do worker"""
        logger.info("📊 PARTITIONED WORKER STATS:")
        logger.info(f"   🎯 Partição: {self.partition_id}")
        logger.info(f"   📥 Fila: {self.queue_name}")
        logger.info(f"   ✅ Processadas: {self.processed_count}")
        logger.info(f"   ❌ Erros: {self.error_count}")
        
        # Reset counters
        self.processed_count = 0
        self.error_count = 0

def main():
    """Função principal"""
    # Obter partition_id de variável de ambiente
    partition_id = int(os.environ.get('PARTITION_ID', '0'))
    
    logger.info(f"🎯 Iniciando Partitioned Message Worker - Partição {partition_id}")
    
    # Criar e iniciar worker
    worker = PartitionedMessageWorker(partition_id=partition_id)
    
    try:
        worker.start()
    except KeyboardInterrupt:
        logger.info("🛑 Interrompido pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
