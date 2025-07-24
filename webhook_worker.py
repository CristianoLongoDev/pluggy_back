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
        start_time = time.time()
        
        try:
            event_type = message.get('event_type', 'unknown')
            event_data = message.get('event_data', {})
            timestamp = message.get('timestamp', time.time())
            
            logger.info(f"📨 Processando evento: {event_type}")
            
            # Timeout para operações críticas (evita travamento total)
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Timeout no processamento de {event_type}")
            
            # Configurar timeout geral de 30 segundos (mais agressivo para detectar travamentos)
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)
            
            try:
                # Salvar no banco de dados se disponível (logs antigos)
                if db_manager.enabled:
                    try:
                        success = db_manager.save_webhook_event(event_type, event_data)
                        if success:
                            logger.info(f"💾 Evento {event_type} salvo no banco")
                        else:
                            logger.warning(f"⚠️ Falha ao salvar evento {event_type} no banco")
                    except Exception as db_error:
                        logger.warning(f"⚠️ Erro não crítico ao salvar no banco: {db_error}")

                # NOVO: Gravar na estrutura de conversa (com tratamento robusto)
                if event_type in ('message_received', 'message_sent'):
                    try:
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
                            
                            # Filtrar reações - não criar conversa para reações
                            if message_type == 'reaction':
                                logger.info(f"🔇 Mensagem do tipo 'reaction' de {contact_id} ignorada - não criando conversa")
                                return True  # Retorna sucesso mas sem processar
                            
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
                            elif message_type == 'audio':
                                audio = event_data.get('audio', {})
                                media_id = audio.get('id')
                                media_type = audio.get('mime_type')
                                file_name = audio.get('filename') if 'filename' in audio else f"audio.{media_type.split('/')[-1] if media_type else 'ogg'}"
                                message_text = None  # Será preenchido com transcrição depois
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
                            
                        # Buscar ou criar conversa ativa (com retry)
                        conversation = None
                        conversation_id = None
                        
                        for conv_attempt in range(3):
                            try:
                                conversation = db_manager.get_active_conversation(contact_id)
                                if not conversation:
                                    logger.info(f"📝 Criando nova conversa para {contact_id}")
                                    conversation_id = db_manager.create_conversation(contact_id)
                                else:
                                    conversation_id = conversation['id']
                                    logger.info(f"📝 Usando conversa existente {conversation_id} para {contact_id}")
                                break
                            except Exception as conv_error:
                                logger.warning(f"Erro ao obter/criar conversa (tentativa {conv_attempt + 1}): {conv_error}")
                                time.sleep(1)
                        
                        # Inserir mensagem se tiver dados válidos
                        if conversation_id:
                            logger.info(f"🔍 DEBUG - conversation_id={conversation_id}, message_type='{message_type}', sender='{sender}', message_text='{message_text}'")
                            
                            # REGRA ESPECIAL: Imagens, Documentos e Áudios  
                            if message_type in ['image', 'document', 'audio'] and sender == 'user':
                                logger.info(f"📎 Processando {message_type} de {sender}")
                                
                                # 1. Salvar caption se existir (como mensagem de texto)
                                if message_text and message_text.strip():
                                    logger.info(f"💾 Salvando caption como mensagem de texto: {message_text[:50]}...")
                                    for msg_attempt in range(3):
                                        try:
                                            success = db_manager.insert_conversation_message(
                                                conversation_id=conversation_id,
                                                message_text=message_text,
                                                sender=sender,
                                                message_type='text',  # Caption é salvo como text
                                                timestamp=dt_timestamp
                                            )
                                            if success:
                                                logger.info(f"✅ Caption salvo como mensagem de texto")
                                                break
                                            else:
                                                logger.error(f"❌ Falha ao salvar caption (tentativa {msg_attempt + 1})")
                                        except Exception as msg_error:
                                            logger.warning(f"Erro ao salvar caption (tentativa {msg_attempt + 1}): {msg_error}")
                                            time.sleep(1)
                                else:
                                    logger.info(f"📎 {message_type.capitalize()} sem caption - apenas salvando contexto")
                                
                                # REGRA ESPECIAL PARA ÁUDIO: Transcrever antes de salvar anexo
                                transcricao_audio = None
                                if message_type == 'audio' and media_id:
                                    logger.info(f"🎙️ Processando transcrição de áudio...")
                                    try:
                                        from audio_transcription_service import audio_transcription_service
                                        from whatsapp_service import whatsapp_service
                                        
                                        # Obter URL do áudio primeiro
                                        media_info = whatsapp_service.get_media_url(media_id)
                                        if media_info and media_info.get('success'):
                                            audio_url = media_info['download_url']
                                            logger.info(f"✅ URL de áudio obtida: {audio_url[:50]}...")
                                            
                                            # Obter token de acesso para download autenticado
                                            access_token = whatsapp_service.get_access_token()
                                            
                                            # Transcrever áudio (com autenticação)
                                            transcription_result = audio_transcription_service.process_audio_message(audio_url, access_token)
                                            if transcription_result and transcription_result.get('success'):
                                                transcricao_audio = transcription_result['transcription']
                                                logger.info(f"🎉 Transcrição: {transcricao_audio[:100]}...")
                                                
                                                # Salvar transcrição como mensagem de texto
                                                success = db_manager.insert_conversation_message(
                                                    conversation_id=conversation_id,
                                                    message_text=transcricao_audio,
                                                    sender=sender,
                                                    message_type='text',
                                                    timestamp=dt_timestamp
                                                )
                                                if success:
                                                    logger.info(f"✅ Transcrição salva como texto")
                                            else:
                                                logger.error(f"❌ Falha na transcrição")
                                        else:
                                            logger.error(f"❌ Falha ao obter URL do áudio")
                                    except Exception as transcription_error:
                                        logger.error(f"❌ Erro na transcrição: {transcription_error}")
                                
                                # 2. Salvar anexo na tabela conversation_attach
                                if media_id:
                                    logger.info(f"💾 Obtendo URL de download para media_id={media_id}")
                                    
                                    # Obter URL de download real da API do WhatsApp (com timeout robusto)
                                    try:
                                        import signal
                                        
                                        def url_timeout_handler(signum, frame):
                                            raise TimeoutError("Timeout ao obter URL de mídia")
                                        
                                        # Timeout de 15 segundos para operação completa
                                        signal.signal(signal.SIGALRM, url_timeout_handler)
                                        signal.alarm(15)
                                        
                                        try:
                                            from whatsapp_service import whatsapp_service
                                            media_info = whatsapp_service.get_media_url(media_id)
                                            
                                            if media_info and media_info.get('success'):
                                                download_url = media_info['download_url']
                                                logger.info(f"✅ URL de download obtida: {download_url[:50]}...")
                                            else:
                                                logger.warning(f"⚠️ Falha ao obter URL, usando media_id como fallback")
                                                download_url = media_id  # Fallback para media_id
                                        finally:
                                            signal.alarm(0)  # Cancelar timeout
                                            
                                    except TimeoutError:
                                        logger.error(f"⏰ Timeout ao obter URL de mídia - usando media_id como fallback")
                                        download_url = media_id  # Fallback para media_id
                                    except Exception as url_error:
                                        logger.error(f"❌ Erro ao obter URL de mídia: {url_error}")
                                        download_url = media_id  # Fallback para media_id
                                    
                                    # Salvar anexo com URL real
                                    logger.info(f"💾 Salvando anexo na conversation_attach: url={download_url[:50]}..., tipo={message_type}")
                                    for attach_attempt in range(3):
                                        try:
                                            success = db_manager.insert_conversation_attach(
                                                conversation_id=conversation_id,
                                                file_url=download_url,  # URL real de download
                                                file_type=message_type,
                                                file_name=file_name
                                            )
                                            if success:
                                                logger.info(f"✅ Anexo salvo na conversation_attach")
                                                break
                                            else:
                                                logger.error(f"❌ Falha ao salvar anexo (tentativa {attach_attempt + 1})")
                                        except Exception as attach_error:
                                            logger.warning(f"Erro ao salvar anexo (tentativa {attach_attempt + 1}): {attach_error}")
                                            time.sleep(1)
                                else:
                                    logger.warning(f"⚠️ media_id não encontrado para {message_type}")
                                
                                # 3. SEMPRE salvar mensagem de contexto sobre o arquivo anexado
                                arquivo_nome = file_name if file_name else f"arquivo.{message_type}"
                                
                                # Mensagem específica por tipo
                                if message_type == 'image':
                                    contexto_mensagem = f"Usuário anexou imagem {arquivo_nome}"
                                elif message_type == 'document':
                                    contexto_mensagem = f"Usuário anexou documento {arquivo_nome}"
                                elif message_type == 'audio':
                                    if transcricao_audio:
                                        contexto_mensagem = f"Usuário enviou áudio {arquivo_nome} (transcrito acima)"
                                    else:
                                        contexto_mensagem = f"Usuário enviou áudio {arquivo_nome} (transcrição falhou)"
                                else:
                                    contexto_mensagem = f"Usuário anexou {message_type} {arquivo_nome}"
                                
                                logger.info(f"💾 Salvando mensagem de contexto: {contexto_mensagem}")
                                logger.info(f"🔍 CONTEXTO-DEBUG: conversation_id={conversation_id}, sender='{sender}', message_type='text'")
                                for ctx_attempt in range(3):
                                    try:
                                        success = db_manager.insert_conversation_message(
                                            conversation_id=conversation_id,
                                            message_text=contexto_mensagem,
                                            sender=sender,
                                            message_type='text',  # Contexto como text para contar no delay
                                            timestamp=dt_timestamp
                                        )
                                        if success:
                                            logger.info(f"✅ Mensagem de contexto salva com sucesso")
                                            break
                                        else:
                                            logger.error(f"❌ Falha ao salvar contexto (tentativa {ctx_attempt + 1})")
                                    except Exception as ctx_error:
                                        logger.warning(f"Erro ao salvar contexto (tentativa {ctx_attempt + 1}): {ctx_error}")
                                        time.sleep(1)
                            
                            # REGRA NORMAL: Mensagens de texto e outras (não imagem/documento)
                            elif message_text and message_text.strip():
                                logger.info(f"💾 Salvando mensagem na conversation_message: conversa_id={conversation_id}, sender={sender}")
                                for msg_attempt in range(3):
                                    try:
                                        success = db_manager.insert_conversation_message(
                                            conversation_id=conversation_id,
                                            message_text=message_text,
                                            sender=sender,
                                            message_type=message_type,
                                            timestamp=dt_timestamp
                                        )
                                        if success:
                                            logger.info(f"✅ Mensagem salva com sucesso na conversation_message")
                                            break
                                        else:
                                            logger.error(f"❌ Falha ao salvar mensagem na conversation_message (tentativa {msg_attempt + 1})")
                                    except Exception as msg_error:
                                        logger.warning(f"Erro ao salvar mensagem (tentativa {msg_attempt + 1}): {msg_error}")
                                        time.sleep(1)
                            else:
                                logger.warning(f"⚠️ Mensagem sem texto válido (tipo: {message_type}) - não é imagem/documento, não salvando")
                        else:
                            logger.warning(f"⚠️ conversation_id inválido, não salvando mensagem")
                            
                    except Exception as conv_error:
                        logger.error(f"❌ Erro não crítico ao processar estrutura de conversa: {conv_error}")
                
                # Processar lógica específica baseada no tipo (com proteção)
                try:
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
                except Exception as process_error:
                    logger.error(f"❌ Erro ao processar lógica específica de {event_type}: {process_error}")
                    # Não deixa falhar o processamento geral
                
            finally:
                signal.alarm(0)  # Cancelar timeout
            
            # Calcular tempo de processamento
            processing_time = time.time() - start_time
            self.processed_count += 1
            logger.info(f"✅ Evento processado com sucesso em {processing_time:.2f}s. Total: {self.processed_count}")
            return True
            
        except TimeoutError as timeout_error:
            processing_time = time.time() - start_time
            logger.error(f"⏰ Timeout ao processar mensagem após {processing_time:.2f}s: {timeout_error}")
            self.error_count += 1
            return False  # Marcar como erro mas não quebrar o worker
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Erro ao processar mensagem após {processing_time:.2f}s: {e}")
            # Log detalhado para debug
            logger.error(f"❌ Dados da mensagem: {message}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            
            self.error_count += 1
            return False  # Retornar False para rejeitar mensagem mas manter worker rodando
    
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
            
            # LOG DETALHADO: Início do debounce
            logger.info(f"📊 INÍCIO - Verificando debounce para conversation_id={conversation_id}")
            
            # Debounce simples: verificar se há mensagens mais novas que a criação desta tarefa
            # Buscar a última mensagem do usuário
            logger.info(f"📊 ETAPA 1 - Buscando últimas mensagens do usuário...")
            try:
                ultimas_msgs = db_manager.get_last_user_messages(conversation_id, limit=1)
                logger.info(f"📊 ETAPA 1 - SUCESSO: Encontradas {len(ultimas_msgs) if ultimas_msgs else 0} mensagens")
            except Exception as e:
                logger.error(f"📊 ETAPA 1 - ERRO: {e}")
                raise
            
            if ultimas_msgs:
                logger.info(f"📊 ETAPA 2 - Processando timestamp da última mensagem...")
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
                
                logger.info(f"📊 ETAPA 2 - SUCESSO: Timestamp convertido: {ultima_timestamp}")
                
                # Verificar se a mensagem é mais nova que a tarefa
                diff_task = ultima_timestamp.timestamp() - task_created_timestamp
                logger.info(f"📊 ETAPA 3 - Verificando se mensagem é mais nova: diff={diff_task:.2f}s")
                
                if diff_task > 0:
                    logger.info(f"⏭️ Mensagem mais nova detectada (+{diff_task:.1f}s), cancelando tarefa")
                    return
                else:
                    logger.info(f"✅ Mensagem anterior à tarefa (-{abs(diff_task):.1f}s), continuando processamento")
            else:
                logger.warning(f"📊 ETAPA 2 - Nenhuma mensagem do usuário encontrada na conversa {conversation_id}")

            # LOG DETALHADO: Buscar conversa ativa
            logger.info(f"📊 ETAPA 4 - Buscando conversa ativa para {contact_id}...")
            try:
                conversation = db_manager.get_active_conversation(contact_id)
                logger.info(f"📊 ETAPA 4 - SUCESSO: Conversa encontrada: {conversation['id'] if conversation else 'None'}")
            except Exception as e:
                logger.error(f"📊 ETAPA 4 - ERRO: {e}")
                raise
                
            if not conversation:
                logger.warning(f"📊 ETAPA 4 - Nenhuma conversa ativa encontrada para {contact_id}")
                return
                
            conversation_id = conversation['id']
            
            # LOG DETALHADO: Verificar mensagens recentes
            logger.info(f"📊 ETAPA 5 - Verificando se houve mensagens recentes (últimos 10s)...")
            try:
                ultimas_msgs_user = db_manager.get_last_user_messages(conversation_id, limit=1)
                logger.info(f"📊 ETAPA 5 - SUCESSO: {len(ultimas_msgs_user) if ultimas_msgs_user else 0} mensagens encontradas")
            except Exception as e:
                logger.error(f"📊 ETAPA 5 - ERRO: {e}")
                raise
                
            if not ultimas_msgs_user:
                logger.warning(f"📊 ETAPA 5 - Nenhuma mensagem do usuário encontrada na conversa {conversation_id}")
                return
                
            ultima_user = ultimas_msgs_user[0]
            agora = datetime.now(timezone.utc)
            ts = ultima_user['timestamp']
            
            logger.info(f"📊 ETAPA 6 - Convertendo timestamp para verificação de delay...")
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
            logger.info(f"📊 ETAPA 6 - SUCESSO: Última mensagem há {diff:.1f}s")
            logger.info(f"🔍 DEBUG - Agora: {agora}, Timestamp msg: {ts}, Diff: {diff:.1f}s")
            
            if diff >= 10:
                # Já se passaram 10s, processar com ChatGPT
                logger.info(f"📊 ETAPA 7 - ✅ 10s aguardados, enviando para ChatGPT...")
                try:
                    self._process_chatgpt_response(contact_id, None)
                    logger.info(f"📊 ETAPA 7 - SUCESSO: ChatGPT processado com sucesso")
                except Exception as e:
                    logger.error(f"📊 ETAPA 7 - ERRO no ChatGPT: {e}")
                    raise
            else:
                # Ainda há mensagens recentes, aguardar mais
                tempo_espera = 10 - diff + 0.5  # +0.5s para margem de segurança
                logger.info(f"⏰ Última mensagem há apenas {diff:.1f}s, aguardando mais {tempo_espera:.1f}s...")
                
                # Aguardar o tempo necessário
                logger.info(f"⏳ Aguardando {tempo_espera:.1f}s antes de verificar novamente...")
                time.sleep(tempo_espera)
                
                # IMPORTANTE: Verificar novamente após o delay
                logger.info(f"🔄 Verificando novamente para ver se chegaram novas mensagens...")
                
                # Buscar novamente as últimas mensagens
                logger.info(f"📊 ETAPA 8 - Nova verificação após espera...")
                try:
                    ultimas_msgs_nova_check = db_manager.get_last_user_messages(conversation_id, limit=1)
                    logger.info(f"📊 ETAPA 8 - SUCESSO: {len(ultimas_msgs_nova_check) if ultimas_msgs_nova_check else 0} mensagens na nova verificação")
                except Exception as e:
                    logger.error(f"📊 ETAPA 8 - ERRO: {e}")
                    raise
                
                if ultimas_msgs_nova_check:
                    nova_ultima = ultimas_msgs_nova_check[0]
                    nova_ts = nova_ultima['timestamp']
                    
                    # Converter para comparação
                    if isinstance(nova_ts, str):
                        try:
                            nova_ts = datetime.fromisoformat(nova_ts.replace('Z', '+00:00'))
                        except ValueError:
                            try:
                                nova_ts = datetime.strptime(nova_ts, "%Y-%m-%d %H:%M:%S.%f")
                            except ValueError:
                                nova_ts = datetime.strptime(nova_ts, "%Y-%m-%d %H:%M:%S")
                    if nova_ts.tzinfo is None:
                        nova_ts = nova_ts.replace(tzinfo=timezone.utc)
                    
                    # Verificar se chegou mensagem nova
                    if nova_ts > ts:
                        logger.info(f"📊 ETAPA 9 - Nova mensagem detectada após espera, cancelando processamento")
                        return
                    else:
                        logger.info(f"📊 ETAPA 9 - Nenhuma mensagem nova, processando com ChatGPT...")
                        try:
                            self._process_chatgpt_response(contact_id, None)
                            logger.info(f"📊 ETAPA 9 - SUCESSO: ChatGPT processado com sucesso")
                        except Exception as e:
                            logger.error(f"📊 ETAPA 9 - ERRO no ChatGPT: {e}")
                            raise
                else:
                    logger.warning(f"📊 ETAPA 9 - Nenhuma mensagem encontrada na nova verificação")
            
            logger.info(f"📊 FIM - Delay check concluído com sucesso para {contact_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro no processamento ChatGPT para {contact_id}: {e}")
            import traceback
            logger.error(f"❌ Traceback completo: {traceback.format_exc()}")
            raise

    def _process_chatgpt_response(self, contact_id, message_text):
        """Processa mensagem com ChatGPT e envia resposta"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"🤖 Processando mensagem com ChatGPT para {contact_id} (tentativa {retry_count + 1}/{max_retries})")
                
                # Importar serviços com timeout e tratamento de erro
                try:
                    import importlib
                    import sys
                    
                    # Recarregar módulos se necessário (evita cache corrompido)
                    if 'chatgpt_service' in sys.modules:
                        importlib.reload(sys.modules['chatgpt_service'])
                    if 'whatsapp_service' in sys.modules:
                        importlib.reload(sys.modules['whatsapp_service'])
                    
                    from chatgpt_service import chatgpt_service
                    from whatsapp_service import whatsapp_service
                    
                except ImportError as e:
                    logger.error(f"❌ Erro ao importar serviços: {e}")
                    retry_count += 1
                    time.sleep(2 ** retry_count)  # Backoff exponencial
                    continue
                
                # Se message_text é None, o ChatGPT service buscará automaticamente
                # o contexto completo da conversa (últimas 10 mensagens)
                if message_text is None:
                    logger.info(f"📚 ChatGPT service buscará contexto completo da conversa para {contact_id}")
                
                # Gerar resposta com ChatGPT com timeout
                try:
                    import signal
                    
                    def timeout_handler(signum, frame):
                        raise TimeoutError("ChatGPT timeout")
                    
                    # Configurar timeout de 45 segundos
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(45)
                    
                    try:
                        chatgpt_response = chatgpt_service.process_message(contact_id, message_text)
                    finally:
                        signal.alarm(0)  # Cancelar timeout
                        
                except TimeoutError:
                    logger.error(f"⏰ Timeout no ChatGPT para {contact_id}")
                    retry_count += 1
                    time.sleep(2 ** retry_count)
                    continue
                
                if chatgpt_response:
                    logger.info(f"✅ ChatGPT respondeu: {chatgpt_response[:50]}...")
                    
                    # Salvar resposta do ChatGPT na conversa (sender=agent) com retry
                    conversation_saved = False
                    for save_attempt in range(3):
                        try:
                            conversation = db_manager.get_active_conversation(contact_id)
                            if conversation:
                                conversation_id = conversation['id']
                                success = db_manager.insert_conversation_message(
                                    conversation_id=conversation_id,
                                    message_text=chatgpt_response,
                                    sender='agent',
                                    message_type='text',
                                    timestamp=datetime.now()
                                )
                                if success:
                                    conversation_saved = True
                                    break
                                else:
                                    logger.warning(f"Tentativa {save_attempt + 1} de salvar conversa falhou")
                            else:
                                logger.warning(f"Não encontrou conversa ativa para {contact_id} ao salvar resposta do ChatGPT.")
                                conversation_saved = True  # Não bloquear por isso
                                break
                        except Exception as save_error:
                            logger.warning(f"Erro ao salvar conversa (tentativa {save_attempt + 1}): {save_error}")
                            time.sleep(1)
                    
                    if not conversation_saved:
                        logger.error(f"❌ Falha ao salvar conversa após 3 tentativas para {contact_id}")
                    
                    # Enviar resposta via WhatsApp com retry
                    send_success = False
                    for send_attempt in range(3):
                        try:
                            sent = whatsapp_service.process_outgoing_message(contact_id, chatgpt_response)
                            if sent:
                                logger.info(f"📤 Resposta enviada com sucesso para {contact_id}")
                                send_success = True
                                break
                            else:
                                logger.warning(f"⚠️ Tentativa {send_attempt + 1} de envio falhou para {contact_id}")
                        except Exception as send_error:
                            logger.warning(f"Erro no envio (tentativa {send_attempt + 1}): {send_error}")
                            time.sleep(1)
                    
                    if not send_success:
                        logger.error(f"❌ Falha ao enviar mensagem após 3 tentativas para {contact_id}")
                    
                    # Sucesso - sair do loop de retry
                    return
                    
                else:
                    logger.warning(f"⚠️ ChatGPT não gerou resposta para {contact_id}")
                    retry_count += 1
                    time.sleep(2 ** retry_count)
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Erro no processamento ChatGPT para {contact_id} (tentativa {retry_count + 1}): {e}")
                retry_count += 1
                
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)  # Backoff exponencial
                else:
                    # Última tentativa - enviar mensagem de erro
                    try:
                        from whatsapp_service import whatsapp_service
                        whatsapp_service.process_outgoing_message(
                            contact_id, 
                            "Desculpe, estou com dificuldades técnicas no momento. Tente novamente em alguns minutos."
                        )
                        logger.info(f"📤 Mensagem de erro enviada para {contact_id}")
                    except Exception as fallback_error:
                        logger.error(f"❌ Falha até no envio de mensagem de erro: {fallback_error}")
        
        logger.error(f"❌ Falha total no processamento para {contact_id} após {max_retries} tentativas")
    
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

        # Variáveis de monitoramento de saúde
        last_message_time = time.time()
        health_check_interval = 60  # 1 minuto
        max_idle_time = 300  # 5 minutos sem mensagens
        consecutive_failures = 0
        max_consecutive_failures = 10

        try:
            # Conectar ao RabbitMQ
            if not rabbitmq_manager.connect():
                logger.error("❌ Falha ao conectar ao RabbitMQ")
                return False

            # Consumir mensagens com sistema de monitoramento
            def callback(message):
                nonlocal last_message_time, consecutive_failures
                
                if not self.running:
                    logger.info("🛑 Worker marcado para parar, rejeitando mensagem")
                    return False
                
                try:
                    # Registrar recebimento de mensagem
                    last_message_time = time.time()
                    
                    # Log de saúde a cada 50 mensagens
                    if self.processed_count % 50 == 0:
                        logger.info(f"💊 Health check: Processadas={self.processed_count}, Erros={self.error_count}, Falhas consecutivas={consecutive_failures}")
                    
                    # Processar mensagem
                    result = self.process_webhook_message(message)
                    
                    if result:
                        consecutive_failures = 0  # Reset contador de falhas
                        return True
                    else:
                        consecutive_failures += 1
                        logger.warning(f"⚠️ Falha consecutiva #{consecutive_failures}")
                        
                        # Se muitas falhas consecutivas, tentar recovery
                        if consecutive_failures >= max_consecutive_failures:
                            logger.error(f"💀 Muitas falhas consecutivas ({consecutive_failures}), tentando recovery...")
                            self._attempt_recovery()
                            consecutive_failures = 0  # Reset após recovery
                        
                        return False
                        
                except Exception as callback_error:
                    consecutive_failures += 1
                    logger.error(f"❌ Erro crítico no callback (falha #{consecutive_failures}): {callback_error}")
                    
                    # Recovery em caso de erro crítico
                    if consecutive_failures >= max_consecutive_failures // 2:  # Recovery mais agressivo
                        logger.error("💀 Muitos erros críticos, tentando recovery...")
                        self._attempt_recovery()
                        consecutive_failures = 0
                    
                    return False

            logger.info(f"🎧 Aguardando mensagens da fila '{queue_name}'...")
            
            # Iniciar thread de monitoramento de saúde
            import threading
            def health_monitor():
                nonlocal last_message_time  # Importante: acessar variável do escopo externo
                while self.running:
                    try:
                        time.sleep(health_check_interval)
                        current_time = time.time()
                        
                        # Verificar se não está processando há muito tempo (apenas para logging)
                        idle_time = current_time - last_message_time
                        if idle_time > max_idle_time:
                            logger.warning(f"⚠️ Worker idle há {idle_time:.0f}s (>{max_idle_time}s)")
                            
                            # REMOVIDO: Recovery automático por idle time (estava causando crashes)
                            # Idle é comportamento normal quando não há mensagens
                            # Recovery será feito apenas por falhas consecutivas de processamento
                            logger.info(f"✅ Idle é normal quando não há mensagens - worker aguardando...")
                        
                        # Log de estatísticas a cada 5 minutos
                        if self.processed_count > 0 and self.processed_count % 100 == 0:
                            error_rate = (self.error_count / (self.processed_count + self.error_count)) * 100
                            logger.info(f"📊 Estatísticas: {self.processed_count} processadas, {self.error_count} erros ({error_rate:.1f}% erro)")
                            
                    except Exception as monitor_error:
                        logger.error(f"❌ Erro no monitor de saúde: {monitor_error}")
                        # Aguardar um pouco antes da próxima verificação
                        time.sleep(health_check_interval)
            
            health_thread = threading.Thread(target=health_monitor, daemon=True)
            health_thread.start()
            logger.info("💊 Monitor de saúde iniciado")
            
            # Consumir mensagens
            rabbitmq_manager.consume_messages(queue_name, callback, auto_ack=False)

        except KeyboardInterrupt:
            logger.info("⏹️ Parando worker por interrupção do usuário")
        except Exception as e:
            logger.error(f"❌ Erro no worker: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
        finally:
            self._cleanup()

        return True
    
    def _attempt_recovery(self):
        """Tenta recuperar o worker de problemas"""
        try:
            logger.info("🔄 Iniciando tentativa de recovery...")
            
            # Fechar conexões existentes
            try:
                if rabbitmq_manager.channel:
                    rabbitmq_manager.channel.stop_consuming()
                if rabbitmq_manager.connection:
                    rabbitmq_manager.connection.close()
                logger.info("✅ Conexões RabbitMQ fechadas")
            except Exception as close_error:
                logger.warning(f"⚠️ Erro ao fechar conexões: {close_error}")
            
            # Aguardar um pouco
            time.sleep(5)
            
            # Tentar reconectar
            if rabbitmq_manager.connect():
                logger.info("✅ Recovery bem-sucedido - reconectado ao RabbitMQ")
            else:
                logger.error("❌ Recovery falhou - não conseguiu reconectar")
                
        except Exception as recovery_error:
            logger.error(f"❌ Erro durante recovery: {recovery_error}")
    
    def _cleanup(self):
        """Limpeza final do worker"""
        try:
            logger.info("🧹 Fazendo limpeza final do worker...")
            
            # Parar consumo
            self.running = False
            
            # Fechar conexões
            if rabbitmq_manager:
                rabbitmq_manager.disconnect()
            
            # Log de estatísticas finais
            total_messages = self.processed_count + self.error_count
            if total_messages > 0:
                success_rate = (self.processed_count / total_messages) * 100
                logger.info(f"📊 Estatísticas finais: {self.processed_count} sucessos, {self.error_count} erros ({success_rate:.1f}% sucesso)")
            
            logger.info("✅ Cleanup concluído")
            
        except Exception as cleanup_error:
            logger.error(f"❌ Erro durante cleanup: {cleanup_error}")

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