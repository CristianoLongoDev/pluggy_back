#!/usr/bin/env python3
"""
Outbox Publisher - Serviço assíncrono que processa eventos da tabela outbox
Garante que eventos salvos no banco sejam publicados no RabbitMQ de forma confiável
"""

import json
import logging
import os
import time
import threading
import signal
import sys
from datetime import datetime
from database import db_manager
from rabbitmq_manager import rabbitmq_manager
from config import LOG_LEVEL

# Configurar logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/outbox_publisher.log')
    ]
)
logger = logging.getLogger(__name__)

class OutboxPublisher:
    def __init__(self):
        self.running = True
        self.processed_count = 0
        self.error_count = 0
        self.batch_size = 50  # Processar até 50 eventos por batch
        self.poll_interval = 5  # Verificar outbox a cada 5 segundos
        self.max_retries = 3  # Máximo de tentativas por evento
        
        # Configurar handler para interrupção
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Estatísticas
        self.last_process_time = time.time()
        self.total_events_processed = 0
        
        # Controle de conexão melhorado
        self.consecutive_connection_errors = 0
        self.last_connection_error = 0
        self.connection_backoff_seconds = 1  # Backoff inicial
        
    def _signal_handler(self, signum, frame):
        """Handler para sinais de interrupção"""
        logger.info(f"📡 Sinal {signum} recebido. Parando outbox publisher...")
        self.running = False

    def start(self):
        """Inicia o processamento contínuo do outbox"""
        logger.info("🚀 Iniciando Outbox Publisher...")
        logger.info("=" * 60)
        logger.info(f"Publisher PID: {os.getpid()}")
        logger.info(f"Batch Size: {self.batch_size}")
        logger.info(f"Poll Interval: {self.poll_interval}s")
        logger.info("=" * 60)
        
        # Verificar dependências
        if not self._check_dependencies():
            logger.error("❌ Dependências não disponíveis - parando")
            return False
        
        # Loop principal
        while self.running:
            try:
                # Check preventivo de conexão com backoff por problemas persistentes
                if self.consecutive_connection_errors > 0:
                    current_time = time.time()
                    if current_time - self.last_connection_error < self.connection_backoff_seconds:
                        logger.debug(f"⏸️ Aguardando {self.connection_backoff_seconds}s por problema de conexão")
                        time.sleep(min(self.connection_backoff_seconds, self.poll_interval))
                        continue
                
                # Check proativo de conexão a cada 2 minutos durante idle (mais frequente)
                if hasattr(self, '_last_proactive_check'):
                    if time.time() - self._last_proactive_check > 120:  # 2 min
                        if not self._proactive_connection_check():
                            logger.info("🔄 Check proativo detectou problema - forçando reconexão")
                            self._handle_connection_error()
                        self._last_proactive_check = time.time()
                else:
                    self._last_proactive_check = time.time()
                
                self._process_outbox_batch()
                self._health_check()
                self._sleep_with_interruption_check()
                
            except Exception as e:
                logger.error(f"❌ Erro no loop principal: {e}")
                self.error_count += 1
                time.sleep(self.poll_interval)
        
        logger.info("🛑 Outbox Publisher parado")
        return True
    
    def _check_dependencies(self):
        """Verifica se as dependências estão disponíveis"""
        # Verificar banco de dados
        if not db_manager or not db_manager.enabled:
            logger.error("❌ Database não está disponível")
            return False
        
        # Verificar RabbitMQ
        if not rabbitmq_manager or not rabbitmq_manager.enabled:
            logger.error("❌ RabbitMQ não está disponível")
            return False
        
        # Testar conexões
        try:
            db_status = db_manager.get_connection_status()
            if db_status != 'connected':
                logger.error(f"❌ Database não conectado: {db_status}")
                return False
        except Exception as e:
            logger.error(f"❌ Erro ao verificar database: {e}")
            return False
        
        try:
            rabbitmq_status = rabbitmq_manager.get_status()
            if rabbitmq_status.get('status') != 'connected':
                logger.error(f"❌ RabbitMQ não conectado: {rabbitmq_status.get('status')}")
                return False
        except Exception as e:
            logger.error(f"❌ Erro ao verificar RabbitMQ: {e}")
            return False
        
        logger.info("✅ Todas as dependências verificadas")
        return True
    
    def _process_outbox_batch(self):
        """Processa um batch de eventos do outbox"""
        try:
            batch_start_time = time.time()
            
            # CORREÇÃO: Adicionar timeout na busca de eventos para evitar travamento
            import threading
            
            events_container = {'events': None, 'error': None, 'completed': False}
            
            def get_events():
                try:
                    logger.info(f"🔍 GET-EVENTS-DEBUG: Buscando eventos pendentes no outbox (limit={self.batch_size})")
                    events_container['events'] = db_manager.get_pending_outbox_events(limit=self.batch_size)
                    event_count = len(events_container['events']) if events_container['events'] else 0
                    logger.info(f"🔍 GET-EVENTS-DEBUG: Encontrados {event_count} eventos pendentes")
                    events_container['completed'] = True
                except Exception as e:
                    logger.error(f"🔍 GET-EVENTS-ERROR: {str(e)}")
                    events_container['error'] = str(e)
                    events_container['completed'] = True
            
            # Executar busca de eventos com timeout
            events_thread = threading.Thread(target=get_events)
            events_thread.daemon = True
            events_thread.start()
            events_thread.join(timeout=10)  # 10 segundos timeout
            
            if not events_container['completed']:
                logger.warning("⚠️ Timeout ao buscar eventos do outbox - possível problema de conexão")
                return
            
            if events_container['error']:
                logger.error(f"❌ Erro ao buscar eventos: {events_container['error']}")
                return
            
            events = events_container['events']
            
            if not events:
                return  # Nenhum evento pendente
            
            logger.info(f"📦 Processando batch com {len(events)} eventos")
            
            # Log de performance se há muitos eventos
            if len(events) > 10:
                logger.warning(f"⚠️ BATCH GRANDE detectado: {len(events)} eventos - pode indicar acúmulo")
            
            processed_ids = []
            failed_events = []
            
            for event in events:
                success = self._process_single_event(event)
                if success:
                    processed_ids.append(event['id'])
                    self.processed_count += 1
                else:
                    failed_events.append(event)
                    self.error_count += 1
            
            # Marcar eventos processados como concluídos
            if processed_ids:
                marked = db_manager.mark_outbox_as_processed(processed_ids)
                if marked:
                    logger.info(f"✅ {len(processed_ids)} eventos marcados como processados")
                else:
                    logger.warning(f"⚠️ Falha ao marcar {len(processed_ids)} eventos")
            
            # Log de eventos falhos
            if failed_events:
                logger.warning(f"⚠️ {len(failed_events)} eventos falharam no processamento")
            
            # Log de performance do batch
            batch_duration = time.time() - batch_start_time
            if batch_duration > 10:  # Se demorou mais de 10s
                logger.warning(f"⏱️ BATCH LENTO: {batch_duration:.1f}s para processar {len(events)} eventos")
            else:
                logger.debug(f"⏱️ Batch processado em {batch_duration:.1f}s")
            
            # Detalhar eventos falhos
            if failed_events:
                for event in failed_events:
                    logger.warning(f"   - Event ID: {event['id']}, Type: {event['event_type']}")
            
            self.total_events_processed += len(processed_ids)
            self.last_process_time = time.time()
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar batch do outbox: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
    
    def _process_single_event(self, event):
        """Processa um único evento do outbox"""
        try:
            event_id = event['id']
            event_type = event['event_type']
            payload_str = event['payload']
            logger.info(f"🔍 SINGLE-EVENT-DEBUG: Processando event_id={event_id}, event_type={event_type}")
            
            logger.debug(f"🔄 Processando evento {event_id} (tipo: {event_type})")
            
            # Parse do payload
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError as e:
                logger.error(f"❌ Payload inválido para evento {event_id}: {e}")
                return False
            
            # Verificar se é evento do RabbitMQ
            if not event_type.startswith('rabbitmq.'):
                logger.warning(f"⚠️ Tipo de evento não suportado: {event_type}")
                return False
            
            # Extrair tipo original do evento
            original_event_type = event_type.replace('rabbitmq.', '')
            event_data = payload.get('event_data')
            
            if not event_data:
                logger.error(f"❌ Event data ausente para evento {event_id}")
                return False
            
            # === FASE 2: USAR PARTICIONAMENTO SE POSSÍVEL ===
            
            # Tentar extrair conversation_id para particionamento
            conversation_id = self._extract_conversation_id(event_data)
            logger.info(f"🔍 PARTITION-DEBUG: event_type={original_event_type}, conversation_id={conversation_id}")
            
            # Publicar no RabbitMQ com retry inteligente
            for attempt in range(self.max_retries):
                try:
                    # 🎯 PARTICIONAMENTO: webhook_received com conversation_id vai para partições
                    if original_event_type == 'webhook_received' and conversation_id:
                        # Mensagens com conversation_id vão para workers particionados
                        success = rabbitmq_manager.publish_to_partition(
                            conversation_id=conversation_id,
                            message_data={
                                'event_type': original_event_type,
                                'event_data': event_data,
                                'source': 'outbox_publisher'
                            }
                        )
                        logger.info(f"🎯 Webhook particionado enviado para conversation_id={conversation_id}, success={success}")
                    elif original_event_type == 'webhook_received':
                        # Webhooks sem conversation_id vão para webhook_messages (ex: status updates)
                        success = rabbitmq_manager.publish_webhook_event(original_event_type, event_data)
                        logger.info(f"🎯 Webhook não particionado (sem conversation_id) enviado para webhook_messages")
                    # Se temos conversation_id E não é webhook, usar particionamento
                    elif conversation_id:
                        success = rabbitmq_manager.publish_to_partition(
                            conversation_id=conversation_id,
                            message_data={
                                'event_type': original_event_type,
                                'event_data': event_data,
                                'source': 'outbox_publisher'
                            }
                        )
                        logger.debug(f"🎯 Tentativa particionada: conversation_id={conversation_id}")
                    else:
                        # Fallback para método tradicional
                        success = rabbitmq_manager.publish_webhook_event(original_event_type, event_data)
                        logger.debug(f"📤 Tentativa tradicional")
                    
                    if success:
                        logger.debug(f"✅ Evento {event_id} publicado no RabbitMQ (tentativa {attempt + 1})")
                        # Reset completo de erros consecutivos em caso de sucesso
                        self._reset_connection_errors()
                        return True
                    else:
                        logger.warning(f"⚠️ Falha ao publicar evento {event_id} (tentativa {attempt + 1})")
                        
                except Exception as publish_error:
                    error_msg = str(publish_error)
                    logger.error(f"❌ Erro ao publicar evento {event_id} (tentativa {attempt + 1}): {publish_error}")
                    
                    # Detectar problemas de conexão
                    if any(keyword in error_msg.lower() for keyword in 
                           ['connection reset', 'connection lost', 'stream connection lost', 'socket']):
                        logger.error(f"🔥 CONEXÃO PERDIDA detectada: {error_msg[:100]}...")
                        self._handle_connection_error()
                    else:
                        logger.error(f"❌ Erro genérico na publicação: {error_msg[:100]}...")
                
                # Aguardar antes da próxima tentativa com backoff inteligente
                if attempt < self.max_retries - 1:
                    delay = min(2 ** attempt, 30)  # Cap máximo de 30s
                    if self.consecutive_connection_errors > 3:
                        delay = min(delay * 2, 60)  # Delay extra para problemas de conexão
                    time.sleep(delay)
            
            logger.error(f"❌ Falha permanente ao publicar evento {event_id} após {self.max_retries} tentativas")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar evento {event.get('id', 'unknown')}: {e}")
            return False
    
    def _health_check(self):
        """Verifica saúde do serviço e faz limpeza"""
        current_time = time.time()
        
        # Log de estatísticas a cada 60 segundos
        if hasattr(self, '_last_stats_log'):
            if current_time - self._last_stats_log > 60:
                self._log_statistics()
                self._last_stats_log = current_time
        else:
            self._last_stats_log = current_time
        
        # Limpeza do outbox a cada 1 hora
        if hasattr(self, '_last_cleanup'):
            if current_time - self._last_cleanup > 3600:  # 1 hora
                self._cleanup_old_events()
                self._last_cleanup = current_time
        else:
            self._last_cleanup = current_time
    
    def _handle_connection_error(self):
        """Gerencia erros de conexão consecutivos com backoff melhorado"""
        current_time = time.time()
        self.consecutive_connection_errors += 1
        self.last_connection_error = current_time
        
        # Backoff exponencial com limite máximo
        self.connection_backoff_seconds = min(
            self.connection_backoff_seconds * 1.5, 
            60  # Máximo de 60 segundos
        )
        
        logger.warning(f"🔥 Connection error #{self.consecutive_connection_errors} detectado")
        logger.warning(f"⚠️ {self.consecutive_connection_errors} erros consecutivos de conexão - aumentando backoff")
        
        # Forçar reconexão após poucos erros (mais agressivo)
        if self.consecutive_connection_errors > 5:
            logger.info("🔄 Forçando reconexão do RabbitMQ após erro persistente")
            try:
                rabbitmq_manager.disconnect()
                time.sleep(2)
                rabbitmq_manager.connect()
            except Exception as e:
                logger.error(f"❌ Erro ao forçar reconexão: {e}")
    
    def _reset_connection_errors(self):
        """Reseta contadores de erro após sucesso"""
        if self.consecutive_connection_errors > 0:
            logger.info(f"✅ Conexão recuperada após {self.consecutive_connection_errors} erros")
            
        self.consecutive_connection_errors = 0
        self.connection_backoff_seconds = 1
        self.last_connection_error = 0
        
        # Forçar reconexão do RabbitMQ Manager
        try:
            if rabbitmq_manager:
                logger.info("🔄 Forçando reconexão do RabbitMQ após erro persistente")
                rabbitmq_manager._close_connection()
        except Exception as e:
            logger.debug(f"Erro ao forçar reconexão: {e}")
    
    def _proactive_connection_check(self):
        """Verifica proativamente a saúde da conexão com timeout"""
        try:
            if rabbitmq_manager and rabbitmq_manager.enabled:
                # CORREÇÃO: Usar threading.Timer ao invés de signal para evitar deadlock
                import threading
                
                result = {'status': None, 'timed_out': False}
                
                def check_status():
                    try:
                        result['status'] = rabbitmq_manager.get_status()
                    except Exception as e:
                        logger.warning(f"⚠️ Erro na thread de verificação: {e}")
                        result['status'] = {'status': 'error'}
                
                # Criar thread com timeout
                check_thread = threading.Thread(target=check_status)
                check_thread.daemon = True
                check_thread.start()
                check_thread.join(timeout=10)  # 10 segundos timeout
                
                if check_thread.is_alive():
                    logger.warning(f"⚠️ Timeout ao verificar status do RabbitMQ")
                    result['timed_out'] = True
                    return False
                
                if result['status'] and result['status'].get('status') == 'connected':
                    return True
                else:
                    logger.warning(f"⚠️ RabbitMQ status não está 'connected': {result['status'].get('status') if result['status'] else 'None'}")
                    return False
                    
        except Exception as e:
            logger.warning(f"⚠️ Erro ao verificar status do RabbitMQ: {e}")
            return False
        return False
    
    def _log_statistics(self):
        """Log das estatísticas do publisher"""
        uptime = time.time() - self.last_process_time if hasattr(self, 'last_process_time') else 0
        
        logger.info("📊 OUTBOX PUBLISHER STATS:")
        logger.info(f"   📦 Total processados: {self.total_events_processed}")
        logger.info(f"   ✅ Sucessos neste ciclo: {self.processed_count}")
        logger.info(f"   ❌ Erros neste ciclo: {self.error_count}")
        logger.info(f"   ⏰ Último processamento: {uptime:.1f}s atrás")
        if self.consecutive_connection_errors > 0:
            logger.warning(f"   🔥 Erros consecutivos de conexão: {self.consecutive_connection_errors}")
            logger.warning(f"   ⏳ Backoff atual: {self.connection_backoff_seconds}s")
        
        # Reset counters para próximo ciclo
        self.processed_count = 0
        self.error_count = 0
    
    def _cleanup_old_events(self):
        """Remove eventos antigos já processados"""
        try:
            deleted = db_manager.cleanup_old_outbox_events(days_old=7)
            if deleted > 0:
                logger.info(f"🧹 Limpeza: {deleted} eventos antigos removidos do outbox")
        except Exception as e:
            logger.error(f"❌ Erro na limpeza do outbox: {e}")
    
    def _extract_conversation_id(self, event_data):
        """
        Extrai conversation_id dos dados do evento para particionamento
        
        Args:
            event_data: Dados do webhook
            
        Returns:
            conversation_id se encontrado, None caso contrário
        """
        try:
            logger.info(f"🔍 EXTRACT-DEBUG: event_data.keys() = {list(event_data.keys()) if event_data else 'None'}")
            logger.info(f"🔍 EXTRACT-DEBUG: event_data.get('object') = {event_data.get('object') if event_data else 'None'}")
            
            # Estrutura do webhook WhatsApp Business
            if event_data.get('object') == 'whatsapp_business_account':
                for entry in event_data.get('entry', []):
                    for change in entry.get('changes', []):
                        value = change.get('value', {})
                        
                        # Tentar extrair de mensagens
                        logger.info(f"🔍 EXTRACT-DEBUG: Verificando value.keys() = {list(value.keys()) if value else 'None'}")
                        if 'messages' in value and value['messages']:
                            message = value['messages'][0]
                            phone_number = message.get('from')
                            logger.info(f"🔍 EXTRACT-DEBUG: phone_number encontrado = {phone_number}")
                            if phone_number:
                                # Buscar conversation_id real no banco de dados
                                conversation_id = self._find_conversation_id_by_phone(phone_number)
                                if conversation_id:
                                    logger.info(f"🔍 EXTRACT-DEBUG: Conversation_id encontrada para {phone_number}: {conversation_id}")
                                    return conversation_id
                                else:
                                    logger.info(f"🔍 EXTRACT-DEBUG: Conversation_id NÃO encontrada para {phone_number} no banco")
                                    # SOLUÇÃO: Usar hash do phone_number como conversation_id para particionamento
                                    import hashlib
                                    phone_hash = int(hashlib.md5(phone_number.encode()).hexdigest(), 16)
                                    synthetic_conversation_id = phone_hash % 100000  # Limitar a 5 dígitos
                                    logger.info(f"🔍 EXTRACT-DEBUG: Usando conversation_id sintético {synthetic_conversation_id} para {phone_number}")
                                    return synthetic_conversation_id
                        else:
                            logger.info(f"🔍 EXTRACT-DEBUG: Não há 'messages' em value ou messages está vazio")
                        
                        # Tentar extrair de status updates
                        if 'statuses' in value and value['statuses']:
                            status = value['statuses'][0]
                            phone_number = status.get('recipient_id')
                            if phone_number:
                                import hashlib
                                phone_hash = int(hashlib.md5(phone_number.encode()).hexdigest(), 16)
                                return phone_hash % 10000
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao extrair conversation_id: {e}")
            return None
    
    def _find_conversation_id_by_phone(self, phone_number):
        """
        Busca conversation_id real no banco de dados pelo número do telefone
        
        Args:
            phone_number: Número do telefone WhatsApp
            
        Returns:
            conversation_id se encontrado, None caso contrário
        """
        try:
            if not db_manager or not db_manager.enabled:
                return None
            
            def _find_conversation_operation(connection):
                cursor = connection.cursor(dictionary=True)
                
                # CORREÇÃO: Adicionar timeout na query para evitar travamento
                import threading
                import time
                
                result_container = {'result': None, 'error': None, 'completed': False}
                
                def execute_query():
                    try:
                        query = """
                            SELECT c.id as conversation_id, c.status_attendance
                            FROM conversation c
                            JOIN contacts ct ON c.contact_id = ct.id
                            WHERE ct.whatsapp_phone_number = %s
                            AND c.status_attendance IN ('ai', 'human', 'waiting')
                            ORDER BY c.started_at DESC
                            LIMIT 1
                        """
                        logger.info(f"🔍 DB-DEBUG: Executando query para phone_number={phone_number}")
                        cursor.execute(query, (phone_number,))
                        result_container['result'] = cursor.fetchone()
                        result_container['completed'] = True
                    except Exception as e:
                        result_container['error'] = str(e)
                        result_container['completed'] = True
                    finally:
                        try:
                            cursor.close()
                        except:
                            pass
                
                # Executar query em thread separada com timeout
                query_thread = threading.Thread(target=execute_query)
                query_thread.daemon = True
                query_thread.start()
                query_thread.join(timeout=5)  # 5 segundos timeout
                
                if not result_container['completed']:
                    logger.warning(f"⚠️ Timeout na query de conversation_id para {phone_number}")
                    try:
                        cursor.close()
                    except:
                        pass
                    return None
                
                if result_container['error']:
                    logger.warning(f"⚠️ Erro na query: {result_container['error']}")
                    return None
                
                result = result_container['result']
                if result:
                    logger.info(f"🔍 DB-DEBUG: Conversa encontrada para {phone_number}: ID={result['conversation_id']}, status={result['status_attendance']}")
                    return result['conversation_id']
                else:
                    logger.info(f"🔍 DB-DEBUG: Nenhuma conversa encontrada para {phone_number}")
                    return None
            
            return db_manager._execute_with_fresh_connection(_find_conversation_operation)
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao buscar conversation_id para {phone_number}: {e}")
            return None
    
    def _sleep_with_interruption_check(self):
        """Dorme respeitando sinais de interrupção"""
        for _ in range(self.poll_interval):
            if not self.running:
                break
            time.sleep(1)

def main():
    """Função principal"""
    import os
    
    logger.info("🎯 Iniciando Outbox Publisher Service")
    
    # Criar instância do publisher
    publisher = OutboxPublisher()
    
    # Iniciar processamento
    try:
        publisher.start()
    except KeyboardInterrupt:
        logger.info("🛑 Interrompido pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
