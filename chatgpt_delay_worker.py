#!/usr/bin/env python3
"""
Worker dedicado para processar tarefas de delay do ChatGPT.
Este worker é responsável por verificar se já passou tempo suficiente
desde a última mensagem do usuário antes de enviar para o ChatGPT.
"""

import sys
import logging
import time
import json
from webhook_worker import WebhookWorker
from rabbitmq_manager import rabbitmq_manager
from config import CHATGPT_DELAY_QUEUE

# Adicionar o diretório atual ao sys.path para importações
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Configurar handler de arquivo para health checks
file_handler = logging.FileHandler('/tmp/chatgpt_delay_worker.log')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

logger = logging.getLogger(__name__)
logger.addHandler(file_handler)

class ChatGPTDelayWorker:
    def __init__(self):
        self.webhook_worker = WebhookWorker()
        self.processed_count = 0
        self.error_count = 0
        
    def callback(self, ch, method, properties, body):
        """Callback para processar mensagens da fila de delay"""
        try:
            # Decodificar mensagem
            message_data = json.loads(body.decode('utf-8'))
            
            logger.info(f"🕐 Recebida tarefa de delay: {message_data.get('task_type', 'unknown')}")
            
            # Processar APENAS tarefas de delay do ChatGPT
            task_type = message_data.get('task_type')
            
            # Ignorar timeouts de conversa - só processar ChatGPT
            if task_type == 'conversation_timeout':
                logger.info(f"⏭️ Ignorando timeout de conversa, processando apenas ChatGPT")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            if task_type == 'chatgpt_delay_check':
                # Processar IMEDIATAMENTE - sem delay
                logger.info(f"🚀 Processando imediatamente sem delay")
                
                # Processar com proteção de timeout ROBUSTO
                import signal
                
                def timeout_handler(signum, frame):
                    logger.error("❌ Timeout no processamento de delay check")
                    # Não fazer raise para não interromper o loop
                
                # Configurar timeout de 30 segundos (mais agressivo)
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)
                
                start_time = time.time()
                logger.info(f"🔍 DELAY-DEBUG: Iniciando processamento às {time.strftime('%H:%M:%S')}")
                
                try:
                    # Processar usando o método do webhook worker
                    logger.info(f"🔍 DELAY-DEBUG: Chamando _process_chatgpt_delay_check...")
                    self.webhook_worker._process_chatgpt_delay_check(message_data)
                    processing_time = time.time() - start_time
                    logger.info(f"🔍 DELAY-DEBUG: Processamento concluído em {processing_time:.2f}s")
                    self.processed_count += 1
                    logger.info(f"✅ Tarefa de delay processada. Total: {self.processed_count}")
                except TimeoutError:
                    processing_time = time.time() - start_time
                    logger.error(f"⏰ Timeout ao processar delay check após {processing_time:.2f}s - rejeitando mensagem")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    self.error_count += 1
                    return
                except Exception as process_error:
                    processing_time = time.time() - start_time
                    logger.error(f"❌ Erro ao processar delay check após {processing_time:.2f}s: {process_error}")
                    import traceback
                    logger.error(f"❌ Traceback: {traceback.format_exc()}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)  # Não requeuear para evitar loop
                    self.error_count += 1
                    return
                finally:
                    signal.alarm(0)  # Cancelar timeout
            
            else:
                logger.warning(f"⚠️ Tipo de tarefa desconhecido: {task_type}")
            
            # Confirmar processamento da mensagem
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"✅ Tarefa processada e ACK enviado, voltando ao loop de consumo...")
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erro ao decodificar JSON: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            self.error_count += 1
        except Exception as e:
            logger.error(f"❌ Erro ao processar tarefa de delay: {e}")
            import traceback
            logger.error(f"📊 Stack trace completo: {traceback.format_exc()}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            self.error_count += 1
    
    def start_consuming(self):
        """Inicia o consumo da fila de delay"""
        try:
            logger.info("🚀 Iniciando ChatGPT Delay Worker")
            logger.info("=" * 60)
            logger.info(f"Worker PID: {sys.argv[0] if sys.argv else 'N/A'}")
            logger.info(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 60)
            
            # Conectar ao RabbitMQ
            if not rabbitmq_manager.connect():
                logger.error("❌ Falha ao conectar ao RabbitMQ")
                return False
            
            logger.info(f"🎧 Aguardando tarefas de delay na fila '{CHATGPT_DELAY_QUEUE}'...")
            
            # Configurar consumo
            rabbitmq_manager.channel.basic_qos(prefetch_count=1)
            rabbitmq_manager.channel.basic_consume(
                queue=CHATGPT_DELAY_QUEUE,
                on_message_callback=self.callback
            )
            
            # Iniciar consumo
            logger.info("🎧 Iniciando consumo da fila de delay...")
            rabbitmq_manager.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("⚡ Interrupção recebida, parando o worker...")
            rabbitmq_manager.channel.stop_consuming()
            rabbitmq_manager.disconnect()
            
        except Exception as e:
            logger.error(f"❌ Erro crítico no delay worker: {e}")
            return False
        
        finally:
            logger.info(f"📊 Estatísticas finais - Processadas: {self.processed_count}, Erros: {self.error_count}")

def main():
    """Função principal"""
    worker = ChatGPTDelayWorker()
    worker.start_consuming()

if __name__ == "__main__":
    main() 