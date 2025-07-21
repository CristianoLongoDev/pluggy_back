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
from datetime import datetime, timezone
from config import (
    WEBHOOK_QUEUE, MESSAGE_QUEUE, STATUS_QUEUE, ERROR_QUEUE,
    LOG_LEVEL, RABBITMQ_ENABLED
)
from rabbitmq_manager import rabbitmq_manager
from database import db_manager
import requests

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
            
            # Salvar no banco de dados se disponível (logs antigos)
            if db_manager.enabled:
                success = db_manager.save_webhook_event(event_type, event_data)
                if success:
                    logger.info(f"💾 Evento {event_type} salvo no banco")
                else:
                    logger.warning(f"⚠️ Falha ao salvar evento {event_type} no banco")

            # NOVO: Gravar na estrutura de conversa
            if event_type in ('message_received', 'message_sent'):
                logger.info(f"🔄 Processando {event_type} para gravar na estrutura de conversa...")
                contact_id = None
                message_text = None
                message_type = None
                sender = None
                msg_timestamp = None
                media_id = None
                media_type = None
                file_name = None
                if event_type == 'message_received':
                    contact_id = event_data.get('from')
                    sender = 'user'
                    message_type = event_data.get('type', 'unknown')
                    if message_type == 'text':
                        message_text = event_data.get('text', {}).get('body')
                    elif message_type == 'document':
                        doc = event_data.get('document', {})
                        media_id = doc.get('id')
                        media_type = doc.get('mime_type')
                        file_name = doc.get('filename')
                        # Só usar caption se existir e não for vazio
                        caption = doc.get('caption')
                        message_text = caption if caption and caption.strip() else None
                    elif message_type == 'image':
                        img = event_data.get('image', {})
                        media_id = img.get('id')
                        media_type = img.get('mime_type')
                        file_name = img.get('filename') if 'filename' in img else None
                        # Só usar caption se existir e não for vazio
                        caption = img.get('caption')
                        message_text = caption if caption and caption.strip() else None
                    msg_timestamp = event_data.get('timestamp')
                elif event_type == 'message_sent':
                    contact_id = event_data.get('to')
                    sender = 'agent'
                    message_type = event_data.get('type', 'unknown')
                    if message_type == 'text':
                        message_text = event_data.get('text')
                    msg_timestamp = event_data.get('timestamp')
                
                logger.info(f"📝 Extraído: contact_id={contact_id}, sender={sender}, message_text='{message_text[:50] if message_text else None}...'")
                
                # Converter timestamp se necessário
                dt_timestamp = None
                if msg_timestamp:
                    try:
                        if isinstance(msg_timestamp, (int, float)):
                            dt_timestamp = datetime.fromtimestamp(float(msg_timestamp))
                        elif isinstance(msg_timestamp, str) and msg_timestamp.isdigit():
                            dt_timestamp = datetime.fromtimestamp(float(msg_timestamp))
                        else:
                            dt_timestamp = datetime.now()
                    except Exception:
                        dt_timestamp = datetime.now()
                else:
                    dt_timestamp = datetime.now()
                # Buscar ou criar conversa ativa
                conversation = db_manager.get_active_conversation(contact_id)
                if not conversation:
                    logger.info(f"📝 Criando nova conversa para {contact_id}")
                    conversation_id = db_manager.create_conversation(contact_id)
                else:
                    conversation_id = conversation['id']
                    logger.info(f"📝 Usando conversa existente {conversation_id} para {contact_id}")
                
                # Inserir mensagem
                if message_text:
                    logger.info(f"💾 Salvando mensagem na conversation_message: conversa_id={conversation_id}, sender={sender}")
                    success = db_manager.insert_conversation_message(
                        conversation_id=conversation_id,
                        message_text=message_text,
                        sender=sender,
                        message_type=message_type,
                        timestamp=dt_timestamp
                    )
                    if success:
                        logger.info(f"✅ Mensagem salva com sucesso na conversation_message")
                    else:
                        logger.error(f"❌ Falha ao salvar mensagem na conversation_message")
                else:
                    logger.warning(f"⚠️ message_text está vazio, não salvando na conversation_message")
                # Se for document ou image, buscar url do arquivo e salvar na conversation_attach
                if message_type in ('document', 'image') and media_id:
                    try:
                        from whatsapp_service import whatsapp_service
                        access_token = whatsapp_service.get_access_token()
                        if access_token:
                            url = f"https://graph.facebook.com/v21.0/{media_id}"
                            headers = {"Authorization": f"Bearer {access_token}"}
                            response = requests.get(url, headers=headers, timeout=30)
                            if response.status_code == 200:
                                media_json = response.json()
                                file_url = media_json.get('url')
                                file_type = media_json.get('mime_type')
                                # Gravar file_name na conversation_attach
                                db_manager.insert_conversation_attach(
                                    conversation_id=conversation_id,
                                    file_url=file_url,
                                    file_type=file_type,
                                    file_name=file_name
                                )
                                logger.info(f"Anexo salvo na conversa: {file_url}")
                                
                                # Adicionar mensagem contextual sobre o anexo
                                if message_type == 'document':
                                    attach_message = f"usuário anexou o documento de nome {file_name or 'sem nome'}"
                                else:  # image
                                    attach_message = f"usuário anexou a imagem de nome {file_name or 'sem nome'}"
                                
                                db_manager.insert_conversation_message(
                                    conversation_id=conversation_id,
                                    message_text=attach_message,
                                    sender='user',
                                    message_type='attachment_info',
                                    timestamp=dt_timestamp
                                )
                                logger.info(f"Mensagem contextual do anexo salva: {attach_message}")
                            else:
                                logger.error(f"Erro ao buscar media do Graph API: {response.status_code} - {response.text}")
                        else:
                            logger.error("Access token do WhatsApp não disponível para buscar media.")
                    except Exception as e:
                        logger.error(f"Erro ao buscar/salvar anexo da conversa: {e}")
            # Processar lógica específica baseada no tipo
            if event_type == 'webhook_received':
                self._process_webhook_received(event_data)
            elif event_type == 'message_received':
                self._process_message_received(event_data)
            elif event_type == 'chatgpt_delay_check':
                self._process_chatgpt_delay_check(event_data)
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
        
        # Só processa ChatGPT para o número autorizado em desenvolvimento
        if from_number != '555496598592':
            logger.info(f"Mensagem recebida de {from_number}, mas ChatGPT está restrito para desenvolvimento. Nenhuma ação tomada.")
            return
        
        # Remover verificação de cache local - deixar o delay worker gerenciar as duplicatas
        # O delay worker tem melhor controle sobre quais tarefas estão realmente ativas
        
        # Implementar debounce usando timestamp da última mensagem
        conversation = db_manager.get_active_conversation(from_number)
        if conversation:
            conversation_id = conversation['id']
            current_time = time.time()
            
            delay_task = {
                'task_type': 'chatgpt_delay_check',
                'contact_id': from_number,
                'conversation_id': conversation_id,
                'created_at': current_time,
                'task_created_timestamp': current_time  # Timestamp de quando a tarefa foi criada
            }
            
            from rabbitmq_manager import rabbitmq_manager
            success = rabbitmq_manager.publish_with_delay(delay_task, delay_seconds=10)
            if success:
                logger.info(f"⏰ Tarefa de delay criada para {from_number} - aguardará 10s (timestamp: {current_time})")
            else:
                logger.error(f"❌ Falha ao enviar tarefa de delay para {from_number}")
        else:
            logger.warning(f"Nenhuma conversa ativa encontrada para {from_number}")
    
    def _process_chatgpt_delay_check(self, event_data):
        """Processa verificação de delay do ChatGPT"""
        try:
            contact_id = event_data.get('contact_id')
            conversation_id = event_data.get('conversation_id')
            created_at = event_data.get('created_at', 0)
            task_created_timestamp = event_data.get('task_created_timestamp', created_at)
            
            logger.info(f"🔍 Processando delay check para {contact_id} (task criada em: {task_created_timestamp})")
            
            # Debounce simples: verificar se há mensagens mais novas que a criação desta tarefa
            # Buscar a última mensagem do usuário
            ultimas_msgs = db_manager.get_last_user_messages(conversation_id, limit=1)
            if ultimas_msgs:
                ultima_msg = ultimas_msgs[0]
                ultima_timestamp = ultima_msg['timestamp']
                
                # Converter timestamp para comparação
                if isinstance(ultima_timestamp, str):
                    try:
                        ultima_timestamp = datetime.fromisoformat(ultima_timestamp.replace('Z', '+00:00'))
                    except ValueError:
                        try:
                            ultima_timestamp = datetime.strptime(ultima_timestamp, "%Y-%m-%d %H:%M:%S.%f")
                        except ValueError:
                            ultima_timestamp = datetime.strptime(ultima_timestamp, "%Y-%m-%d %H:%M:%S")
                if ultima_timestamp.tzinfo is None:
                    ultima_timestamp = ultima_timestamp.replace(tzinfo=timezone.utc)
                
                ultima_timestamp_float = ultima_timestamp.timestamp()
                
                # Se há uma mensagem mais nova que a criação desta tarefa, ignorar
                if ultima_timestamp_float > task_created_timestamp + 0.5:  # +0.5s para margem
                    logger.info(f"🚫 Tarefa obsoleta: task criada em {task_created_timestamp}, última msg em {ultima_timestamp_float}. Ignorando...")
                    return
                
                logger.info(f"✅ Tarefa válida: task criada em {task_created_timestamp}, última msg em {ultima_timestamp_float}")
            
            # Contador de tentativas para evitar loop infinito
            retry_count = event_data.get('retry_count', 0)
            max_retries = 10  # Máximo de 10 reagendamentos (cerca de 100s total)
            
            # Verificar se excedeu o número máximo de tentativas
            if retry_count >= max_retries:
                logger.warning(f"⚠️ Máximo de tentativas excedido para {contact_id}, processando mesmo assim...")
                self._process_chatgpt_response(contact_id, None)
                return
            
            # Buscar conversa ativa para verificar mensagens
            conversation = db_manager.get_active_conversation(contact_id)
            if not conversation:
                logger.warning(f"Nenhuma conversa ativa encontrada para {contact_id}")
                return
                
            conversation_id = conversation['id']
            
            # Verificar se houve mensagens recentes (últimos 10s)
            ultimas_msgs_user = db_manager.get_last_user_messages(conversation_id, limit=1)
            if not ultimas_msgs_user:
                logger.warning(f"Nenhuma mensagem do usuário encontrada na conversa {conversation_id}")
                return
                
            ultima_user = ultimas_msgs_user[0]
            agora = datetime.now(timezone.utc)
            ts = ultima_user['timestamp']
            
            # Converter timestamp para datetime
            if isinstance(ts, str):
                try:
                    # Tentar primeiro com microssegundos
                    ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except ValueError:
                    try:
                        # Tentar formato com microssegundos explícito
                        ts = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        # Fallback para formato sem microssegundos
                        ts = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
                
            diff = (agora - ts).total_seconds()
            logger.info(f"⏱️ Verificando delay para {contact_id}: última mensagem há {diff:.1f}s (tentativa {retry_count + 1}/{max_retries})")
            logger.info(f"🔍 DEBUG - Agora: {agora}, Timestamp msg: {ts}, Diff: {diff:.1f}s")
            
            if diff >= 10:
                # Já se passaram 10s, processar com ChatGPT
                logger.info(f"✅ 10s aguardados desde a última mensagem, enviando para ChatGPT...")
                self._process_chatgpt_response(contact_id, None)
            else:
                # Ainda há mensagens recentes, precisa aguardar mais
                tempo_espera = 10 - diff + 0.5  # +0.5s para margem de segurança
                logger.info(f"⏰ Última mensagem há apenas {diff:.1f}s, aguardando mais {tempo_espera:.1f}s...")
                
                # Incrementar contador de tentativas
                event_data['retry_count'] = retry_count + 1
                
                # Aguardar o tempo necessário
                logger.info(f"⏳ Aguardando {tempo_espera:.1f}s antes de verificar novamente...")
                time.sleep(tempo_espera)
                
                # IMPORTANTE: Verificar novamente após o delay para pegar mensagens que podem ter chegado
                logger.info(f"🔄 Verificando novamente para ver se chegaram novas mensagens...")
                
                # Buscar novamente as últimas mensagens para ver se chegou algo novo
                ultimas_msgs_nova_check = db_manager.get_last_user_messages(conversation_id, limit=1)
                if ultimas_msgs_nova_check:
                    ultima_nova = ultimas_msgs_nova_check[0]
                    ts_nova = ultima_nova['timestamp']
                    
                    # Converter timestamp para datetime
                    if isinstance(ts_nova, str):
                        try:
                            ts_nova = datetime.fromisoformat(ts_nova.replace('Z', '+00:00'))
                        except ValueError:
                            try:
                                ts_nova = datetime.strptime(ts_nova, "%Y-%m-%d %H:%M:%S.%f")
                            except ValueError:
                                ts_nova = datetime.strptime(ts_nova, "%Y-%m-%d %H:%M:%S")
                    if ts_nova.tzinfo is None:
                        ts_nova = ts_nova.replace(tzinfo=timezone.utc)
                    
                    # Se chegou uma mensagem mais nova, recalcular
                    if ts_nova > ts:
                        logger.info(f"🆕 Nova mensagem detectada durante espera! Última agora é de {ts_nova}")
                        # Atualizar o event_data com o novo timestamp e resetar contador
                        event_data['created_at'] = ts_nova.timestamp()
                        event_data['retry_count'] = 0  # Resetar contador pois é uma nova mensagem
                        logger.info(f"🔄 Resetando contador de tentativas pois nova mensagem foi detectada")
                        
                # Verificar novamente recursivamente
                self._process_chatgpt_delay_check(event_data)
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar delay check: {e}")

    def _process_chatgpt_response(self, contact_id, message_text):
        """Processa mensagem com ChatGPT e envia resposta"""
        try:
            # Importar serviços aqui para evitar problemas de inicialização
            from chatgpt_service import chatgpt_service
            from whatsapp_service import whatsapp_service
            
            logger.info(f"🤖 Processando mensagem com ChatGPT para {contact_id}")
            
            # Se message_text é None, o ChatGPT service buscará automaticamente
            # o contexto completo da conversa (últimas 10 mensagens)
            if message_text is None:
                logger.info(f"📚 ChatGPT service buscará contexto completo da conversa para {contact_id}")
            
            # Gerar resposta com ChatGPT
            chatgpt_response = chatgpt_service.process_message(contact_id, message_text)
            
            if chatgpt_response:
                logger.info(f"✅ ChatGPT respondeu: {chatgpt_response[:50]}...")
                
                # Salvar resposta do ChatGPT na conversa (sender=agent)
                conversation = db_manager.get_active_conversation(contact_id)
                if conversation:
                    conversation_id = conversation['id']
                    db_manager.insert_conversation_message(
                        conversation_id=conversation_id,
                        message_text=chatgpt_response,
                        sender='agent',
                        message_type='text',
                        timestamp=datetime.now()
                    )
                else:
                    logger.warning(f"Não encontrou conversa ativa para {contact_id} ao salvar resposta do ChatGPT.")
                
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