#!/usr/bin/env python3
"""
Worker para processar mensagens do webhook via RabbitMQ
Este worker consome mensagens das filas e processa de forma assíncrona
"""

import json
import logging
import os
import signal
import uuid
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
                            from_phone_number = event_data.get('from')
                            sender = 'user'
                            message_type = event_data.get('type', 'unknown')
                            logger.info(f"📎 WEBHOOK-DEBUG: Processando {message_type} - dados completos: {event_data}")
                            
                            # Filtrar reações - não criar conversa para reações
                            if message_type == 'reaction':
                                logger.info(f"🔇 Mensagem do tipo 'reaction' de {from_phone_number} ignorada - não criando conversa")
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
                                logger.info(f"📎 CAPTION-DEBUG: document - caption extraído: '{caption}', message_text final: '{message_text}'")
                            elif message_type == 'image':
                                img = event_data.get('image', {})
                                media_id = img.get('id')
                                media_type = img.get('mime_type')
                                file_name = img.get('filename') if 'filename' in img else None
                                # Só usar caption se existir e não for vazio
                                caption = img.get('caption')
                                message_text = caption if caption and caption.strip() else None
                                logger.info(f"📎 CAPTION-DEBUG: image - caption extraído: '{caption}', message_text final: '{message_text}'")
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
                        
                        # Buscar contato UUID pelo número de telefone (só para message_received)
                        if event_type == 'message_received' and from_phone_number:
                            logger.info(f"📞 Buscando UUID do contato para número: {from_phone_number}")
                            try:
                                def _get_contact_by_phone_operation(connection):
                                    cursor = connection.cursor(dictionary=True)
                                    query = """
                                        SELECT id, name, account_id, whatsapp_phone_number 
                                        FROM contacts 
                                        WHERE whatsapp_phone_number = %s
                                        LIMIT 1
                                    """
                                    cursor.execute(query, (from_phone_number,))
                                    result = cursor.fetchone()
                                    cursor.close()
                                    return result
                                
                                contact = db_manager._execute_with_fresh_connection(_get_contact_by_phone_operation)
                                if contact:
                                    contact_id = contact['id']
                                    logger.info(f"✅ Contato encontrado: {contact_id} para {from_phone_number}")
                                else:
                                    logger.warning(f"❌ Contato não encontrado para {from_phone_number}")
                                    logger.info("💡 Recomendação: Processar via webhook_received completo primeiro")
                                    return True
                            except Exception as contact_error:
                                logger.error(f"❌ Erro ao buscar contato: {contact_error}")
                                return True
                        elif event_type == 'message_sent':
                            # Para message_sent, contact_id já foi definido na linha 133
                            pass
                        
                        if not contact_id:
                            logger.warning(f"⚠️ contact_id inválido, não processando mensagem")
                            return True
                        
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
                            logger.info(f"📎 WEBHOOK-DEBUG: Dados processados - media_id={media_id}, file_name={file_name}, message_text_length={len(message_text) if message_text else 0}")
                            
                            # DEBUG ESPECÍFICO: Verificar condição de anexo
                            logger.info(f"🔍 CONDIÇÃO-DEBUG: message_type='{message_type}' in ['image', 'document', 'audio'] = {message_type in ['image', 'document', 'audio']}")
                            logger.info(f"🔍 CONDIÇÃO-DEBUG: sender='{sender}' == 'user' = {sender == 'user'}")
                            logger.info(f"🔍 CONDIÇÃO-DEBUG: Condição completa = {message_type in ['image', 'document', 'audio'] and sender == 'user'}")
                            
                            # REGRA ESPECIAL: Imagens, Documentos e Áudios  
                            if message_type in ['image', 'document', 'audio'] and sender == 'user':
                                logger.info(f"📎 ATTACHMENT-DEBUG: Processando {message_type} de {sender}")
                                logger.info(f"📎 ATTACHMENT-DEBUG: media_id={media_id}, media_type={media_type}, file_name={file_name}")
                                
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
                                                timestamp=dt_timestamp,
                                                notify_websocket=True  # NOTIFICAR WEBSOCKET
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
                                                    timestamp=dt_timestamp,
                                                    notify_websocket=True  # NOTIFICAR WEBSOCKET
                                                )
                                                if success:
                                                    logger.info(f"✅ Transcrição salva como texto")
                                            else:
                                                logger.error(f"❌ Falha na transcrição")
                                        else:
                                            logger.error(f"❌ Falha ao obter URL do áudio")
                                    except Exception as transcription_error:
                                        logger.error(f"❌ Erro na transcrição: {transcription_error}")
                                
                                # 2. Salvar anexo na tabela conversation_attach (EXCETO áudio - já foi transcrito)
                                if media_id and message_type != 'audio':
                                    logger.info(f"📎 ATTACHMENT-DEBUG: Iniciando salvamento de anexo ({message_type})")
                                    logger.info(f"💾 Obtendo URL de download para media_id={media_id}")
                                    
                                    # Preparar file_extension baseado no mime_type (apenas a extensão, não o mime_type completo)
                                    file_extension = None
                                    if media_type:
                                        if message_type == 'image':
                                            # Para imagens, extrair extensão do mime_type (ex: image/jpeg -> .jpeg)
                                            mime_base = media_type.split(';')[0].strip()  # Remove codecs
                                            file_extension = f".{mime_base.split('/')[-1]}" if '/' in mime_base else None
                                        elif message_type == 'document':
                                            # Para documentos, extrair extensão do mime_type ou usar o nome do arquivo
                                            if file_name and '.' in file_name:
                                                file_extension = '.' + file_name.split('.')[-1]
                                            else:
                                                mime_base = media_type.split(';')[0].strip()
                                                file_extension = f".{mime_base.split('/')[-1]}" if '/' in mime_base else None
                                        elif message_type == 'audio':
                                            # Para áudios, extrair extensão do mime_type (ex: audio/ogg; codecs=opus -> .ogg)
                                            mime_base = media_type.split(';')[0].strip()  # Remove codecs
                                            file_extension = f".{mime_base.split('/')[-1]}" if '/' in mime_base else '.ogg'
                                    
                                    logger.info(f"📎 Dados do anexo - Tipo: {message_type}, Mime: {media_type}, Extensão: {file_extension}, Nome: {file_name}")
                                    
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
                                    
                                    # Salvar anexo com URL real e file_extension
                                    logger.info(f"💾 Salvando anexo na conversation_attach: url={download_url[:50]}..., tipo={message_type}")
                                    for attach_attempt in range(3):
                                        try:
                                            success = db_manager.insert_conversation_attach(
                                                conversation_id=conversation_id,
                                                file_url=download_url,  # URL real de download
                                                file_type=message_type,
                                                file_name=file_name,
                                                file_extension=file_extension  # Novo campo
                                            )
                                            if success:
                                                logger.info(f"✅ Anexo salvo na conversation_attach (extensão: {file_extension})")
                                                break
                                            else:
                                                logger.error(f"❌ Falha ao salvar anexo (tentativa {attach_attempt + 1})")
                                        except Exception as attach_error:
                                            logger.warning(f"Erro ao salvar anexo (tentativa {attach_attempt + 1}): {attach_error}")
                                            time.sleep(1)
                                else:
                                    logger.warning(f"📎 ATTACHMENT-DEBUG: ❌ media_id não encontrado para {message_type}")
                                    logger.warning(f"📎 ATTACHMENT-DEBUG: event_data completo: {event_data}")
                                
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
                                            timestamp=dt_timestamp,
                                            notify_websocket=True  # NOTIFICAR WEBSOCKET
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
                                            timestamp=dt_timestamp,
                                            notify_websocket=True  # NOTIFICAR WEBSOCKET
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
                    elif event_type == 'conversation_timeout':
                        self._process_conversation_timeout(event_data)
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
                    
                    # TAREFA 1: Processar apenas webhooks com messages, ignorar statuses
                    if 'messages' in value:
                        logger.info(f"📱 WEBHOOK-DEBUG: Recebido webhook com messages: {len(value['messages'])} mensagem(ns)")
                        logger.info(f"📱 WEBHOOK-DEBUG: Conteúdo completo do webhook: {json.dumps(value, indent=2)}")
                        logger.info(f"📱 Processando webhook com {len(value['messages'])} mensagens")
                        self._process_whatsapp_messages(value, entry)
                    elif 'statuses' in value:
                        logger.info(f"📊 WEBHOOK-DEBUG: Recebido webhook com statuses: {len(value['statuses'])} status(es)")
                        logger.info(f"📊 WEBHOOK-DEBUG: Conteúdo completo do webhook: {json.dumps(value, indent=2)}")
                        logger.info(f"📊 Ignorando webhook com statuses: {len(value['statuses'])} status(es)")
                    else:
                        logger.warning(f"⚠️ Webhook sem messages nem statuses: {list(value.keys())}")
    
    def _process_whatsapp_messages(self, value, entry):
        """Processa mensagens do webhook WhatsApp"""
        try:
            # Extrair dados do webhook
            metadata = value.get('metadata', {})
            display_phone_number = metadata.get('display_phone_number')
            
            if not display_phone_number:
                logger.error("❌ display_phone_number não encontrado no webhook")
                return
            
            logger.info(f"📞 Display phone number: {display_phone_number}")
            
            # TAREFA 2: Buscar canal pelo display_phone_number
            channel = self._get_channel_by_phone(display_phone_number)
            if not channel:
                logger.error(f"❌ Canal não encontrado para o número: {display_phone_number}")
                return
            
            logger.info(f"📋 Canal encontrado: {channel['id']} (Account: {channel['account_id']}, Bot: {channel['bot_id']})")
            
            # Buscar bot para obter system_prompt
            bot = None
            if channel.get('bot_id'):
                bot = self._get_bot_by_id(channel['bot_id'])
                if bot:
                    logger.info(f"🤖 Bot encontrado: {bot['name']}, system_prompt presente: {bool(bot.get('system_prompt'))}")
                else:
                    logger.warning(f"🚫 Bot não encontrado para bot_id: {channel['bot_id']}")
            
            # Processar cada mensagem
            for message in value.get('messages', []):
                self._process_single_message(message, value, channel, bot)
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagens do WhatsApp: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _get_channel_by_phone(self, display_phone_number):
        """Busca canal pelo display_phone_number"""
        if not db_manager.enabled:
            return None
        
        def _get_channel_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, account_id, bot_id, name, phone_number
                FROM channels 
                WHERE phone_number = %s AND active = 1
                LIMIT 1
            """
            cursor.execute(query, (display_phone_number,))
            result = cursor.fetchone()
            cursor.close()
            return result
        
        return db_manager._execute_with_fresh_connection(_get_channel_operation)
    
    def _get_bot_by_id(self, bot_id):
        """Busca bot pelo ID"""
        if not db_manager.enabled:
            return None
        
        def _get_bot_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, account_id, name, system_prompt
                FROM bots 
                WHERE id = %s
                LIMIT 1
            """
            cursor.execute(query, (bot_id,))
            result = cursor.fetchone()
            cursor.close()
            return result
        
        return db_manager._execute_with_fresh_connection(_get_bot_operation)
    
    def _process_single_message(self, message, value, channel, bot=None):
        """Processa uma mensagem individual"""
        try:
            from_number = message.get('from')
            message_type = message.get('type', 'unknown')
            
            # FILTRO: Ignorar reações - não devem criar conversa nem ser processadas
            if message_type == 'reaction':
                logger.info(f"🔇 Reação de {from_number} ignorada - tipo 'reaction' não é processado")
                return
            
            message_text = self._extract_message_text(message)
            
            if not from_number:
                logger.error("❌ Número do remetente não encontrado na mensagem")
                return
            
            logger.info(f"💬 Processando mensagem {message_type} de {from_number}: {message_text[:50]}...")
            
            # TAREFA 2: Buscar/criar contato
            contact = self._get_or_create_contact(from_number, value, channel['account_id'])
            if not contact:
                logger.error(f"❌ Falha ao obter/criar contato para {from_number}")
                return
            
            # ADICIONAR PROCESSAMENTO DE ANEXOS AQUI ANTES DE PROCESSAR CONVERSA
            self._process_message_attachments(message, contact['id'], channel['id'])
            
            # AGENDAR TIMEOUT DE 1H SE É MENSAGEM DO USUÁRIO
            if from_number and message_text:  # Só para mensagens válidas do usuário
                self._schedule_conversation_timeout(contact['id'])
            
            # TAREFA 3: Processar conversa com novos parâmetros
            self._process_conversation_with_channel(contact, channel, message, message_text, bot)
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem individual: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _process_message_attachments(self, message, contact_id, channel_id):
        """Processa anexos da mensagem (imagens, documentos, áudios)"""
        try:
            message_type = message.get('type', 'unknown')
            sender = 'user'  # No contexto atual, sempre é o usuário enviando
            
            # Extrair dados de mídia baseado no tipo
            media_id = None
            media_type = None
            file_name = None
            message_text = None
            
            logger.info(f"📎 WEBHOOK-DEBUG: Processando {message_type} - dados completos: {message}")
            
            if message_type == 'document':
                doc = message.get('document', {})
                media_id = doc.get('id')
                media_type = doc.get('mime_type')
                file_name = doc.get('filename')
                caption = doc.get('caption')
                message_text = caption if caption and caption.strip() else None
                logger.info(f"📎 CAPTION-DEBUG: document - caption extraído: '{caption}', message_text final: '{message_text}'")
            elif message_type == 'image':
                img = message.get('image', {})
                media_id = img.get('id')
                media_type = img.get('mime_type')
                file_name = img.get('filename') if 'filename' in img else None
                caption = img.get('caption')
                message_text = caption if caption and caption.strip() else None
                logger.info(f"📎 CAPTION-DEBUG: image - caption extraído: '{caption}', message_text final: '{message_text}'")
            elif message_type == 'audio':
                audio = message.get('audio', {})
                media_id = audio.get('id')
                media_type = audio.get('mime_type')
                file_name = audio.get('filename') if 'filename' in audio else f"audio.{media_type.split('/')[-1] if media_type else 'ogg'}"
                message_text = None  # Será preenchido com transcrição se possível
            
            # Debug das condições
            logger.info(f"🔍 CONDIÇÃO-DEBUG: message_type='{message_type}' in ['image', 'document', 'audio'] = {message_type in ['image', 'document', 'audio']}")
            logger.info(f"🔍 CONDIÇÃO-DEBUG: sender='{sender}' == 'user' = {sender == 'user'}")
            logger.info(f"🔍 CONDIÇÃO-DEBUG: Condição completa = {message_type in ['image', 'document', 'audio'] and sender == 'user'}")
            logger.info(f"📎 WEBHOOK-DEBUG: Dados processados - media_id={media_id}, file_name={file_name}, message_text_length={len(message_text) if message_text else 0}")
            
            # REGRA ESPECIAL: Imagens, Documentos e Áudios  
            if message_type in ['image', 'document', 'audio'] and sender == 'user':
                logger.info(f"📎 ATTACHMENT-DEBUG: Processando {message_type} de {sender}")
                logger.info(f"📎 ATTACHMENT-DEBUG: media_id={media_id}, media_type={media_type}, file_name={file_name}")
                
                # Buscar conversa para obter conversation_id
                conversation_id = None
                try:
                    # Buscar conversa existente ou criar nova (seguindo padrão do código)
                    conversation = db_manager.get_active_conversation(contact_id)
                    if not conversation:
                        logger.info(f"📝 Criando nova conversa para anexo do contato {contact_id}")
                        conversation_id = self._create_conversation_with_channel(contact_id, channel_id)
                    else:
                        conversation_id = conversation['id']
                        logger.info(f"📝 Usando conversa existente {conversation_id} para anexo")
                except Exception as conv_error:
                    logger.error(f"❌ Erro ao obter conversa para anexo: {conv_error}")
                
                if not conversation_id:
                    logger.error(f"❌ Não foi possível obter conversation_id para salvar anexo")
                    return
                
                # ESPECIAL PARA ÁUDIO: Transcrever antes de processar
                transcricao_audio = None
                if message_type == 'audio' and media_id:
                    logger.info(f"🎙️ Processando transcrição de áudio em _process_message_attachments...")
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
                                logger.info(f"🎉 Transcrição obtida: {transcricao_audio[:100]}...")
                                
                                # Salvar transcrição como mensagem de texto ANTES do anexo (limitando tamanho)
                                # Limitar a 2000 caracteres para evitar erro de "Data too long"
                                texto_limitado = transcricao_audio[:2000] if len(transcricao_audio) > 2000 else transcricao_audio
                                if len(transcricao_audio) > 2000:
                                    texto_limitado += "... [texto truncado]"
                                    logger.warning(f"⚠️ Transcrição truncada: {len(transcricao_audio)} -> {len(texto_limitado)} caracteres")
                                
                                success = db_manager.insert_conversation_message(
                                    conversation_id=conversation_id,
                                    message_text=texto_limitado,
                                    sender='user',
                                    message_type='text',
                                    timestamp=datetime.now(),
                                    notify_websocket=True  # NOTIFICAR WEBSOCKET
                                )
                                if success:
                                    logger.info(f"✅ Transcrição salva como mensagem de texto")
                                else:
                                    logger.error(f"❌ Falha ao salvar transcrição")
                            else:
                                logger.error(f"❌ Falha na transcrição: {transcription_result}")
                        else:
                            logger.error(f"❌ Falha ao obter URL do áudio: {media_info}")
                    except Exception as transcription_error:
                        logger.error(f"❌ Erro na transcrição: {transcription_error}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exc()}")
                
                # 1. Salvar caption se existir (como mensagem de texto)
                if message_text and message_text.strip():
                    logger.info(f"💾 Salvando caption como mensagem de texto: {message_text[:50]}...")
                    try:
                        success = db_manager.insert_conversation_message(
                            conversation_id=conversation_id,
                            message_text=message_text,
                            sender='user',
                            message_type='text',  # Caption é sempre texto
                            timestamp=datetime.now()
                        )
                        if success:
                            logger.info(f"✅ Caption salvo como mensagem de texto")
                        else:
                            logger.error(f"❌ Falha ao salvar caption")
                    except Exception as caption_error:
                        logger.error(f"❌ Erro ao salvar caption: {caption_error}")
                
                # 2. Salvar anexo na tabela conversation_attach (EXCETO áudio - já foi transcrito)
                if media_id and message_type != 'audio':
                    logger.info(f"📎 ATTACHMENT-DEBUG: Iniciando salvamento de anexo ({message_type})")
                    logger.info(f"💾 Obtendo URL de download para media_id={media_id}")
                    
                    # Preparar file_extension baseado no mime_type (apenas a extensão, não o mime_type completo)
                    file_extension = None
                    if media_type:
                        if message_type == 'image':
                            # Para imagens, extrair extensão do mime_type (ex: image/jpeg -> .jpeg)
                            mime_base = media_type.split(';')[0].strip()  # Remove codecs
                            file_extension = f".{mime_base.split('/')[-1]}" if '/' in mime_base else None
                        elif message_type == 'document':
                            # Para documentos, extrair extensão do mime_type ou usar o nome do arquivo
                            if file_name and '.' in file_name:
                                file_extension = '.' + file_name.split('.')[-1]
                            else:
                                mime_base = media_type.split(';')[0].strip()
                                file_extension = f".{mime_base.split('/')[-1]}" if '/' in mime_base else None
                    
                    logger.info(f"📎 Dados do anexo - Tipo: {message_type}, Mime: {media_type}, Extensão: {file_extension}, Nome: {file_name}")
                    
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
                    
                    # Salvar anexo com URL real e file_extension
                    logger.info(f"💾 Salvando anexo na conversation_attach: url={download_url[:50]}..., tipo={message_type}")
                    for attach_attempt in range(3):
                        try:
                            success = db_manager.insert_conversation_attach(
                                conversation_id=conversation_id,
                                file_url=download_url,  # URL real de download
                                file_type=message_type,
                                file_name=file_name,
                                file_extension=file_extension
                            )
                            if success:
                                logger.info(f"✅ Anexo salvo na conversation_attach (tentativa {attach_attempt + 1})")
                                break
                            else:
                                logger.warning(f"⚠️ Falha ao salvar anexo (tentativa {attach_attempt + 1})")
                        except Exception as attach_error:
                            logger.error(f"❌ Erro ao salvar anexo (tentativa {attach_attempt + 1}): {attach_error}")
                        
                        if attach_attempt == 2:  # Última tentativa falhou
                            logger.error(f"❌ Falha definitiva ao salvar anexo após 3 tentativas")
                elif media_id and message_type == 'audio':
                    logger.info(f"🎙️ ATTACHMENT-DEBUG: Áudio processado com transcrição - anexo não salvo propositalmente")
                else:
                    logger.warning(f"📎 ATTACHMENT-DEBUG: ❌ media_id não encontrado para {message_type}")
                    logger.warning(f"📎 ATTACHMENT-DEBUG: dados da mensagem: {message}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar anexos da mensagem: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    
    def _extract_message_text(self, message):
        """Extrai o texto da mensagem baseado no tipo"""
        message_type = message.get('type', 'unknown')
        
        if message_type == 'text':
            return message.get('text', {}).get('body', '')
        elif message_type == 'reaction':
            # Reações não devem ser processadas - retornar identificador especial
            emoji = message.get('reaction', {}).get('emoji', '👍')
            return f'[Reação: {emoji}]'
        elif message_type == 'image':
            # Extrair caption da imagem se existir
            caption = message.get('image', {}).get('caption')
            if caption and caption.strip():
                return caption
            return '[Imagem enviada]'
        elif message_type == 'document':
            # Extrair caption do documento se existir
            caption = message.get('document', {}).get('caption')
            if caption and caption.strip():
                return caption
            return '[Documento enviado]'
        elif message_type == 'audio':
            # Para áudio, não retornar texto - a transcrição será salva separadamente
            return ''
        elif message_type == 'video':
            # Extrair caption do vídeo se existir
            caption = message.get('video', {}).get('caption')
            if caption and caption.strip():
                return caption
            return '[Vídeo enviado]'
        else:
            return f'[Mensagem do tipo {message_type}]'
    
    def _get_or_create_contact(self, from_number, value, account_id):
        """Busca ou cria contato"""
        if not db_manager.enabled:
            return None
        
        # Primeiro, buscar se já existe
        def _get_contact_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, name, email, whatsapp_phone_number, account_id
                FROM contacts 
                WHERE whatsapp_phone_number = %s AND account_id = %s
                LIMIT 1
            """
            cursor.execute(query, (from_number, account_id))
            result = cursor.fetchone()
            cursor.close()
            return result
        
        contact = db_manager._execute_with_fresh_connection(_get_contact_operation)
        
        if contact:
            logger.info(f"✅ Contato existente encontrado: {contact['id']}")
            return contact
        
        # Criar novo contato
        contact_name = self._extract_contact_name(value)
        contact_id = str(uuid.uuid4())
        
        def _create_contact_operation(connection):
            cursor = connection.cursor()
            query = """
                INSERT INTO contacts (id, name, account_id, whatsapp_phone_number)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (contact_id, contact_name, account_id, from_number))
            connection.commit()
            cursor.close()
            return True
        
        success = db_manager._execute_with_fresh_connection(_create_contact_operation)
        
        if success:
            logger.info(f"✅ Novo contato criado: {contact_id} - {contact_name}")
            return {
                'id': contact_id,
                'name': contact_name,
                'email': None,
                'whatsapp_phone_number': from_number,
                'account_id': account_id
            }
        else:
            logger.error(f"❌ Falha ao criar contato para {from_number}")
            return None
    
    def _extract_contact_name(self, value):
        """Extrai o nome do contato do webhook"""
        contacts = value.get('contacts', [])
        if contacts and len(contacts) > 0:
            profile = contacts[0].get('profile', {})
            return profile.get('name', 'Usuário sem nome')
        return 'Usuário sem nome'
    
    def _process_conversation_with_channel(self, contact, channel, message, message_text, bot=None):
        """Processa conversa com novos parâmetros (channel_id e status_attendance)"""
        try:
            # Buscar conversa ativa
            conversation = db_manager.get_active_conversation(contact['id'])
            
            if not conversation:
                # Criar nova conversa com channel_id e status_attendance
                conversation_id = self._create_conversation_with_channel(contact['id'], channel['id'])
                if not conversation_id:
                    logger.error(f"❌ Falha ao criar conversa para contato {contact['id']}")
                    return
            else:
                conversation_id = conversation['id']
                logger.info(f"💬 Usando conversa existente: {conversation_id}")
            
            # Salvar mensagem na conversa (exceto áudio - que é processado separadamente com transcrição)
            message_type = message.get('type', 'text')
            if message_type != 'audio':
                success = db_manager.insert_conversation_message(
                    conversation_id=conversation_id,
                    message_text=message_text,
                    sender='user',
                    message_type=message_type,
                    timestamp=datetime.now(),
                    notify_websocket=True  # NOTIFICAR WEBSOCKET
                )
            else:
                # Para áudio, apenas log - transcrição será salva em _process_message_attachments
                logger.info(f"🎙️ Mensagem de áudio não salva diretamente - aguardando transcrição")
                success = True  # Considerar como sucesso para continuar o fluxo
            
            if success:
                logger.info(f"✅ Mensagem salva na conversa {conversation_id}")
                
                # TAREFA 3: Processar ChatGPT com system_prompt do bot
                self._process_chatgpt_with_bot_prompt(contact, channel, conversation_id, message_text, bot)
            else:
                logger.error(f"❌ Falha ao salvar mensagem na conversa")
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar conversa: {e}")
    
    def _create_conversation_with_channel(self, contact_id, channel_id):
        """Cria nova conversa com channel_id, status_attendance='bot' e system_prompt"""
        if not db_manager.enabled:
            return None
        
        def _create_conversation_operation(connection):
            cursor = connection.cursor(dictionary=True)
            
            # Buscar bot_id e system_prompt em uma única query com JOIN
            channel_bot_query = """
                SELECT bots.system_prompt, channels.bot_id 
                FROM channels 
                JOIN bots ON (channels.bot_id = bots.id)
                WHERE channels.id = %s AND channels.active = 1
                LIMIT 1
            """
            cursor.execute(channel_bot_query, (channel_id,))
            bot_result = cursor.fetchone()
            
            system_prompt = None
            if bot_result and bot_result['system_prompt']:
                bot_id = bot_result['bot_id']
                logger.info(f"Bot ID encontrado: {bot_id} (tipo: {type(bot_id)}) para channel {channel_id}")
                
                # Buscar funções do bot
                logger.info(f"🚀 Iniciando busca de funções para bot_id: {bot_id}")
                bot_functions = self._get_bot_functions_for_conversation(bot_id, cursor)
                logger.info(f"🚀 Busca de funções finalizada. Encontradas {len(bot_functions)} funções")
                
                # Formatar system_prompt no formato JSON do ChatGPT com tools
                import json
                conversation_data = {
                    "messages": [
                        {
                            "role": "system",
                            "content": bot_result['system_prompt']
                        }
                    ],
                    "tools": bot_functions,
                    "tool_choice": "auto"
                }
                system_prompt = json.dumps(conversation_data, ensure_ascii=False)
                logger.info(f"System prompt + {len(bot_functions)} funções formatados para ChatGPT - bot {bot_id}")
            else:
                logger.warning(f"Bot ou system_prompt não encontrado para channel {channel_id}")
            
            # Criar conversa com system_prompt formatado
            insert_query = """
                INSERT INTO conversation (contact_id, channel_id, status, status_attendance, system_prompt, started_at)
                VALUES (%s, %s, 'active', 'bot', %s, NOW())
            """
            cursor.execute(insert_query, (contact_id, channel_id, system_prompt))
            conversation_id = cursor.lastrowid
            connection.commit()
            cursor.close()
            logger.info(f"Conversa criada: {conversation_id} com system_prompt gravado")
            return conversation_id
        
        return db_manager._execute_with_fresh_connection(_create_conversation_operation)
    
    def _get_bot_functions_for_conversation(self, bot_id, cursor):
        """Busca e formata funções do bot para usar no ChatGPT"""
        try:
            logger.info(f"🔍 Buscando funções para bot_id: {bot_id}")
                    
            # Buscar funções do bot onde prompt_id IS NULL  
            functions_query = """
                SELECT bpf.function_id
                FROM bots_prompts_functions bpf
                WHERE bpf.bot_id = %s AND bpf.prompt_id IS NULL
            """
            cursor.execute(functions_query, (bot_id,))
            function_ids = cursor.fetchall()
            
            logger.info(f"🔍 Encontradas {len(function_ids)} funções para bot {bot_id} com prompt_id IS NULL")
            if function_ids:
                logger.info(f"🔍 IDs das funções encontradas: {[f['function_id'] for f in function_ids]}")
            
            if not function_ids:
                logger.warning(f"❌ Nenhuma função encontrada para bot {bot_id} com prompt_id IS NULL")
                
                # Fallback: tentar buscar todas as funções do bot (ignorando prompt_id)
                fallback_query = """
                    SELECT DISTINCT bpf.function_id
                    FROM bots_prompts_functions bpf
                    WHERE bpf.bot_id = %s
                """
                cursor.execute(fallback_query, (bot_id,))
                fallback_function_ids = cursor.fetchall()
                
                if fallback_function_ids:
                    logger.info(f"🔧 FALLBACK: Encontradas {len(fallback_function_ids)} funções totais para bot {bot_id}")
                    logger.info(f"🔧 FALLBACK: IDs das funções: {[f['function_id'] for f in fallback_function_ids]}")
                    function_ids = fallback_function_ids
                else:
                    logger.error(f"❌ Nenhuma função encontrada para bot {bot_id} em qualquer cenário")
                    return []
                                     
            bot_functions = []
            for func_row in function_ids:
                function_id = func_row['function_id']
                logger.info(f"🔧 Processando função: {function_id}")
                
                # Primeiro buscar dados da função
                function_query = """
                    SELECT function_id, description
                    FROM bots_functions
                    WHERE function_id = %s AND bot_id = %s
                """
                try:
                    logger.info(f"🔧 Buscando dados da função {function_id} para bot {bot_id}")
                    cursor.execute(function_query, (function_id, bot_id))
                    function_data = cursor.fetchone()
                    
                    if not function_data:
                        logger.warning(f"❌ Função {function_id} não encontrada para bot {bot_id}")
                        continue
                        
                    function_description = function_data['description']
                    logger.info(f"✅ Função {function_id} encontrada: {function_description}")
                    
                    # Agora buscar parâmetros da função filtrados por bot_id
                    params_query = """
                        SELECT parameter_id, description, permited_values, default_value
                        FROM bots_functions_parameters
                        WHERE function_id = %s AND bot_id = %s
                    """
                    logger.info(f"🔧 Buscando parâmetros para função {function_id} e bot {bot_id}")
                    cursor.execute(params_query, (function_id, bot_id))
                    parameters_data = cursor.fetchall()
                    
                    logger.info(f"🔧 Encontrados {len(parameters_data)} parâmetros para função {function_id}")
                    
                    # Extrair parâmetros
                    parameters = []
                    for param_row in parameters_data:
                        parameters.append({
                            'parameter_id': param_row['parameter_id'],
                            'description': param_row['description'],
                            'permitted_values': param_row['permited_values'],
                            'default_value': param_row['default_value']
                        })
                    
                    logger.info(f"✅ Função {function_id} processada com {len(parameters)} parâmetros")
                    
                except Exception as query_error:
                    logger.error(f"❌ Erro ao buscar função {function_id}: {query_error}")
                    logger.error(f"❌ Detalhes do erro: {str(query_error)}")
                    continue
                
                # Montar estrutura da função no formato tools do ChatGPT
                function_obj = {
                    "type": "function",
                    "function": {
                        "name": function_id,
                        "description": function_description,
                        "parameters": {
                            "type": "object",
                            "required": [],
                            "properties": {}
                        }
                    }
                }
                
                # Processar parâmetros
                for param in parameters:
                    param_id = param['parameter_id']
                    param_desc = param['description']
                    permitted_values = param.get('permitted_values')
                    default_value = param.get('default_value')
                    
                    # Adicionar às propriedades obrigatórias
                    function_obj["function"]["parameters"]["required"].append(param_id)
                    
                    # Montar propriedade do parâmetro
                    param_property = {
                        "type": "string",
                        "description": param_desc
                    }
                    
                    # Adicionar enum se tiver valores permitidos
                    if permitted_values:
                        param_property["enum"] = permitted_values.split(',') if isinstance(permitted_values, str) else permitted_values
                    
                    # Adicionar valor padrão se tiver
                    if default_value:
                        param_property["default"] = default_value
                    
                    function_obj["function"]["parameters"]["properties"][param_id] = param_property
                
                bot_functions.append(function_obj)
                logger.info(f"✅ Função {function_id} adicionada com {len(parameters)} parâmetros")
                
                # Log da estrutura da função (com import local)
                import json
                logger.info(f"🔧 Estrutura da função: {json.dumps(function_obj, ensure_ascii=False)[:200]}...")
            
            logger.info(f"🎯 Total de {len(bot_functions)} funções formatadas para bot {bot_id}")
            return bot_functions
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar funções do bot {bot_id}: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return []
    
    def _get_conversation_system_prompt(self, conversation_id):
        """Busca system_prompt da conversa"""
        if not db_manager.enabled:
            return None
        
        def _get_system_prompt_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT system_prompt FROM conversation 
                WHERE id = %s
                LIMIT 1
            """
            cursor.execute(query, (conversation_id,))
            result = cursor.fetchone()
            cursor.close()
            return result['system_prompt'] if result else None
        
        return db_manager._execute_with_fresh_connection(_get_system_prompt_operation)
    
    def _get_conversation_by_id(self, conversation_id):
        """Busca dados de uma conversa pelo ID"""
        if not db_manager.enabled:
            return None
        
        def _get_conversation_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, contact_id, channel_id, status, status_attendance, system_prompt, started_at
                FROM conversation 
                WHERE id = %s
                LIMIT 1
            """
            cursor.execute(query, (conversation_id,))
            result = cursor.fetchone()
            cursor.close()
            return result
        
        return db_manager._execute_with_fresh_connection(_get_conversation_operation)
    
    def _process_chatgpt_with_bot_prompt(self, contact, channel, conversation_id, message_text, bot=None):
        """Processa ChatGPT usando system_prompt da conversa"""
        try:
            logger.info(f"🤖 Iniciando processamento ChatGPT para conversa {conversation_id}")
            
            # Verificar se o atendimento está em modo humano
            conversation = self._get_conversation_by_id(conversation_id)
            if conversation and conversation.get('status_attendance') == 'human':
                logger.info(f"🙋‍♂️ Conversa {conversation_id} está em modo humano - IA não vai responder")
                return
            
            # Buscar system_prompt da conversa (já formatado para ChatGPT)
            system_prompt_json = self._get_conversation_system_prompt(conversation_id)
            if not system_prompt_json:
                logger.error(f"❌ System prompt não encontrado na conversa {conversation_id}")
                return
            
            # System prompt e funções já estão formatados, usar diretamente
            import json
            try:
                conversation_data = json.loads(system_prompt_json)
                
                # Extrair system_prompt e tools (novo formato ChatGPT)
                if 'messages' in conversation_data and 'tools' in conversation_data:
                    # Novo formato ChatGPT com messages + tools
                    system_prompt_obj = conversation_data['messages'][0]  # Primeira mensagem é o system
                    bot_functions = conversation_data['tools']
                    system_prompt_content = system_prompt_obj.get('content', '')
                    logger.info(f"🎯 System prompt + {len(bot_functions)} tools carregados da conversa (novo formato)")
                elif 'system_prompt' in conversation_data and 'functions' in conversation_data:
                    # Formato intermediário com system_prompt + functions
                    system_prompt_obj = conversation_data['system_prompt']
                    bot_functions = conversation_data['functions']
                    system_prompt_content = system_prompt_obj.get('content', '')
                    logger.info(f"🎯 System prompt + {len(bot_functions)} funções carregados da conversa (formato intermediário)")
                else:
                    # Formato antigo (só system_prompt)
                    system_prompt_obj = conversation_data
                    bot_functions = []
                    system_prompt_content = conversation_data.get('content', '')
                    logger.info(f"🎯 System prompt carregado da conversa (formato antigo)")
                
                # TAREFA 4: Aplicar prompts dinâmicos baseados em eventos
                dynamic_prompts, prompt_functions = self._get_dynamic_prompts_and_functions(contact, channel['bot_id'])
                if dynamic_prompts:
                    # Atualizar o conteúdo com prompts dinâmicos
                    system_prompt_content = f"{system_prompt_content}\n\n{dynamic_prompts}"
                    system_prompt_obj['content'] = system_prompt_content
                    logger.info(f"📝 Prompts dinâmicos aplicados: {len(dynamic_prompts)} caracteres")
                
                # NOVA FUNCIONALIDADE: Identificação de intenções e aplicação de prompts/funções específicas
                logger.info(f"🚀 Iniciando identificação de intenção para conversation {conversation_id}")
                
                # Identificar intenção do usuário
                identified_intent, clarification_question = self._identify_user_intent(
                    contact['id'], conversation_id, system_prompt_content, channel['bot_id']
                )
                
                intent_functions = []
                if identified_intent:
                    # Aplicar prompt e funções específicas da intenção
                    intent_prompt, intent_functions = self._apply_intent_based_prompts_and_functions(
                        identified_intent, channel['bot_id']
                    )
                    
                    if intent_prompt:
                        system_prompt_content = f"{system_prompt_content}\n\n{intent_prompt}"
                        system_prompt_obj['content'] = system_prompt_content
                        logger.info(f"🎯 Prompt específico da intenção aplicado: {len(intent_prompt)} caracteres")
                
                elif clarification_question:
                    # Se precisar esclarecer a intenção, enviar pergunta diretamente
                    logger.info(f"🤔 Pergunta de esclarecimento gerada: {clarification_question}")
                    # Por enquanto, continua processamento normal. Futuramente pode implementar envio direto da pergunta
                
                else:
                    # Nenhuma intenção identificada (confiança < 30% ou 'none')
                    logger.info(f"🏃 Continuando sem aplicar intenções específicas - usando apenas prompts base e de eventos")
                
                # Combinar todas as funções: conversa + prompts dinâmicos + intenção
                all_functions = bot_functions + prompt_functions + intent_functions
                
                # Reformatar dados para envio
                final_system_prompt_content = system_prompt_content
                
            except json.JSONDecodeError:
                # Fallback para formato muito antigo (texto puro)
                system_prompt_content = system_prompt_json
                logger.warning(f"⚠️ System prompt em formato muito antigo, convertendo")
                
                # TAREFA 4: Aplicar prompts dinâmicos baseados em eventos  
                dynamic_prompts, prompt_functions = self._get_dynamic_prompts_and_functions(contact, channel['bot_id'])
                if dynamic_prompts:
                    system_prompt_content = f"{system_prompt_content}\n\n{dynamic_prompts}"
                    logger.info(f"📝 Prompts dinâmicos aplicados: {len(dynamic_prompts)} caracteres")
                
                # NOVA FUNCIONALIDADE: Identificação de intenções e aplicação de prompts/funções específicas
                logger.info(f"🚀 Iniciando identificação de intenção para conversation {conversation_id}")
                
                # Identificar intenção do usuário
                identified_intent, clarification_question = self._identify_user_intent(
                    contact['id'], conversation_id, system_prompt_content, channel['bot_id']
                )
                
                intent_functions = []
                if identified_intent:
                    # Aplicar prompt e funções específicas da intenção
                    intent_prompt, intent_functions = self._apply_intent_based_prompts_and_functions(
                        identified_intent, channel['bot_id']
                    )
                    
                    if intent_prompt:
                        system_prompt_content = f"{system_prompt_content}\n\n{intent_prompt}"
                        logger.info(f"🎯 Prompt específico da intenção aplicado: {len(intent_prompt)} caracteres")
                
                elif clarification_question:
                    # Se precisar esclarecer a intenção, enviar pergunta diretamente
                    logger.info(f"🤔 Pergunta de esclarecimento gerada: {clarification_question}")
                    # Por enquanto, continua processamento normal. Futuramente pode implementar envio direto da pergunta
                
                else:
                    # Nenhuma intenção identificada (confiança < 30% ou 'none')
                    logger.info(f"🏃 Continuando sem aplicar intenções específicas - usando apenas prompts base e de eventos")
                
                # Converter para formato JSON
                system_prompt_obj = {
                    "role": "system", 
                    "content": system_prompt_content
                }
                all_functions = prompt_functions + intent_functions
                final_system_prompt_content = system_prompt_content
            
            logger.info(f"🔧 Total de {len(all_functions)} funções preparadas para ChatGPT")
            
            # Continuar com processamento ChatGPT usando delay worker
            current_time = time.time()
            delay_task = {
                'task_type': 'chatgpt_delay_check',
                'contact_id': contact['id'],
                'conversation_id': conversation_id,
                'created_at': current_time,
                'task_created_timestamp': current_time,
                'channel_id': channel['id'],
                'bot_id': channel['bot_id'],
                'system_prompt_json': json.dumps(system_prompt_obj, ensure_ascii=False),
                'chatgpt_functions': all_functions
            }
            
            from rabbitmq_manager import rabbitmq_manager
            success = rabbitmq_manager.publish_with_delay(delay_task, delay_seconds=10)
            if success:
                logger.info(f"⏰ Tarefa ChatGPT criada para conversa {conversation_id}")
            else:
                logger.error(f"❌ Falha ao enviar tarefa ChatGPT")
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar ChatGPT: {e}")
    
    def _process_chatgpt_with_conversation_config(self, contact_id, conversation_id):
        """Processa ChatGPT usando system_prompt salvo na conversa + contexto dinâmico"""
        try:
            logger.info(f"🤖 Processando ChatGPT com conversation config para conversa {conversation_id}")
            
            # Buscar dados da conversa
            conversation = self._get_conversation_by_id(conversation_id)
            if not conversation:
                logger.error(f"❌ Conversa {conversation_id} não encontrada")
                return
            
            # Verificar se o atendimento está em modo humano
            if conversation.get('status_attendance') == 'human':
                logger.info(f"🙋‍♂️ Conversa {conversation_id} está em modo humano - IA não vai responder")
                return
            
            # Buscar system_prompt da conversa (já formatado para ChatGPT com functions)
            system_prompt_json = self._get_conversation_system_prompt(conversation_id)
            if not system_prompt_json:
                logger.error(f"❌ System prompt não encontrado na conversa {conversation_id}")
                return
            
            # Buscar dados do contact e channel
            contact = db_manager.get_contact(contact_id)
            if not contact:
                logger.error(f"❌ Contato {contact_id} não encontrado")
                return
                
            channel = db_manager.get_channel(conversation['channel_id'])
            if not channel:
                logger.error(f"❌ Canal {conversation['channel_id']} não encontrado")
                return
            
            # Processar o JSON do system_prompt
            try:
                import json
                conversation_data = json.loads(system_prompt_json)
                
                # Extrair system_prompt e tools (novo formato ChatGPT)
                if 'messages' in conversation_data and 'tools' in conversation_data:
                    # Novo formato ChatGPT com messages + tools
                    system_prompt_obj = conversation_data['messages'][0]  # Primeira mensagem é o system
                    bot_functions = conversation_data['tools']
                    system_prompt_content = system_prompt_obj.get('content', '')
                    logger.info(f"🎯 System prompt + {len(bot_functions)} tools carregados da conversa (novo formato)")
                elif 'system_prompt' in conversation_data and 'functions' in conversation_data:
                    # Formato intermediário com system_prompt + functions
                    system_prompt_obj = conversation_data['system_prompt']
                    bot_functions = conversation_data['functions']
                    system_prompt_content = system_prompt_obj.get('content', '')
                    logger.info(f"🎯 System prompt + {len(bot_functions)} funções carregados da conversa (formato intermediário)")
                else:
                    # Formato antigo (só system_prompt)
                    system_prompt_obj = conversation_data
                    bot_functions = []
                    system_prompt_content = conversation_data.get('content', '')
                    logger.info(f"🎯 System prompt carregado da conversa (formato antigo)")
                
                # Aplicar prompts dinâmicos baseados em eventos
                dynamic_prompts, prompt_functions = self._get_dynamic_prompts_and_functions(contact, channel['bot_id'])
                if dynamic_prompts:
                    # Atualizar o conteúdo com prompts dinâmicos
                    system_prompt_content = f"{system_prompt_content}\n\n{dynamic_prompts}"
                    system_prompt_obj['content'] = system_prompt_content
                    logger.info(f"📝 Prompts dinâmicos aplicados: {len(dynamic_prompts)} caracteres")
                
                # NOVA FUNCIONALIDADE: Identificação de intenções e aplicação de prompts/funções específicas
                logger.info(f"🚀 INTENT-DEBUG: Iniciando identificação de intenção para conversation {conversation_id}")
                logger.info(f"🚀 INTENT-DEBUG: Contact ID: {contact_id}, Bot ID: {channel['bot_id']}")
                
                intent_functions = []
                try:
                    # Identificar intenção do usuário
                    logger.info(f"🔍 INTENT-DEBUG: Chamando _identify_user_intent...")
                    identified_intent, clarification_question = self._identify_user_intent(
                        contact_id, conversation_id, system_prompt_content, channel['bot_id']
                    )
                    logger.info(f"✅ INTENT-DEBUG: _identify_user_intent executado - Intent: {identified_intent}, Question: {clarification_question}")
                    
                    if identified_intent:
                        # Aplicar prompt e funções específicas da intenção
                        logger.info(f"🎯 INTENT-DEBUG: Aplicando intent {identified_intent}")
                        intent_prompt, intent_functions = self._apply_intent_based_prompts_and_functions(
                            identified_intent, channel['bot_id']
                        )
                        
                        if intent_prompt:
                            system_prompt_content = f"{system_prompt_content}\n\n{intent_prompt}"
                            system_prompt_obj['content'] = system_prompt_content
                            logger.info(f"🎯 Prompt específico da intenção aplicado: {len(intent_prompt)} caracteres")
                    
                    elif clarification_question:
                        # Se precisar esclarecer a intenção, enviar pergunta diretamente
                        logger.info(f"🤔 Pergunta de esclarecimento gerada: {clarification_question}")
                        # Por enquanto, continua processamento normal. Futuramente pode implementar envio direto da pergunta
                    
                    else:
                        # Nenhuma intenção identificada (confiança < 30% ou 'none')
                        logger.info(f"🏃 Continuando sem aplicar intenções específicas - usando apenas prompts base e de eventos")
                        
                except Exception as e:
                    logger.error(f"❌ INTENT-DEBUG: Erro ao identificar intenção: {e}")
                    intent_functions = []
                
                # Combinar funções: conversa + prompts dinâmicos + intenção
                all_functions = bot_functions + prompt_functions + intent_functions
                
                # Reformatar dados para envio
                final_system_prompt_content = system_prompt_content
                
            except json.JSONDecodeError:
                logger.error(f"❌ Erro ao decodificar system_prompt JSON da conversa {conversation_id}")
                return
            
            logger.info(f"🔧 Total de {len(all_functions)} funções preparadas para ChatGPT")
            logger.info(f"🎯 Enviando para ChatGPT: system_prompt={len(final_system_prompt_content)} chars, functions={len(all_functions)}")
            
            # Buscar informações do bot para agent_name
            bot_info = None
            if channel.get('bot_id'):
                bot_info = self._get_bot_data(channel['bot_id'])
            
            # Chamar ChatGPT com configuração otimizada
            return self._process_chatgpt_response_internal(contact_id, None, final_system_prompt_content, all_functions, bot_info)
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar ChatGPT com conversation config: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
    
    def _get_bot_data(self, bot_id):
        """Busca dados do bot"""
        if not db_manager.enabled:
            return None
        
        def _get_bot_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, name, system_prompt, integration_id
                FROM bots
                WHERE id = %s
            """
            cursor.execute(query, (bot_id,))
            result = cursor.fetchone()
            cursor.close()
            return result
        
        return db_manager._execute_with_fresh_connection(_get_bot_operation)
    
    
    def _get_dynamic_prompts_and_functions(self, contact, bot_id):
        """TAREFA 4: Busca prompts dinâmicos baseados em eventos e suas funções"""
        try:
            prompts = []
            all_prompt_functions = []
            
            # Buscar contato fresh do banco para garantir dados atualizados
            fresh_contact = db_manager.get_contact(contact['id'])
            if not fresh_contact:
                logger.error(f"❌ Contato {contact['id']} não encontrado para verificação de prompts dinâmicos")
                return '', []
            
            # Evento: 'email not informed'
            if not fresh_contact.get('email'):
                email_prompts_data = self._get_prompts_and_functions_by_rule(bot_id, 'email not informed')
                for prompt_data in email_prompts_data:
                    prompts.append(prompt_data['prompt'])
                    prompt_functions_data = self._get_bot_functions(bot_id, prompt_data['id'])
                    prompt_functions = self._build_chatgpt_functions_with_tools_format(prompt_functions_data, bot_id)
                    all_prompt_functions.extend(prompt_functions)
                logger.info(f"📧 Evento 'email not informed' disparado")
            else:
                logger.info(f"📧 Email já registrado ({fresh_contact.get('email')}) - não aplicando prompt 'email not informed'")
            
            # Evento: 'first contact'
            if self._is_first_contact(fresh_contact['id']):
                first_contact_prompts_data = self._get_prompts_and_functions_by_rule(bot_id, 'first contact')
                for prompt_data in first_contact_prompts_data:
                    prompts.append(prompt_data['prompt'])
                    prompt_functions_data = self._get_bot_functions(bot_id, prompt_data['id'])
                    prompt_functions = self._build_chatgpt_functions_with_tools_format(prompt_functions_data, bot_id)
                    all_prompt_functions.extend(prompt_functions)
                logger.info(f"👋 Evento 'first contact' disparado")
            
            return '\n'.join(prompts) if prompts else '', all_prompt_functions
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar prompts dinâmicos: {e}")
            return '', []
    
    def _get_prompts_and_functions_by_rule(self, bot_id, rule_display):
        """Busca prompts completos por rule_display"""
        if not db_manager.enabled:
            return []
        
        def _get_prompts_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, prompt, description
                FROM bots_prompts
                WHERE bot_id = %s AND rule_display = %s
            """
            cursor.execute(query, (bot_id, rule_display))
            results = cursor.fetchall()
            cursor.close()
            return results
        
        result = db_manager._execute_with_fresh_connection(_get_prompts_operation)
        return result or []
    
    def _is_first_contact(self, contact_id):
        """Verifica se é o primeiro contato do usuário (histórico geral)"""
        if not db_manager.enabled:
            return False
        
        def _check_first_contact_operation(connection):
            cursor = connection.cursor()
            query = """
                SELECT COUNT(*) as total
                FROM conversation_message cm
                JOIN conversation c ON c.id = cm.conversation_id
                WHERE c.contact_id = %s AND cm.sender = 'user'
            """
            cursor.execute(query, (contact_id,))
            result = cursor.fetchone()
            cursor.close()
            return result[0] <= 1  # Primeira mensagem ou menos
        
        return db_manager._execute_with_fresh_connection(_check_first_contact_operation)
    
    def _get_bot_functions(self, bot_id, prompt_id=None):
        """Busca funções associadas ao bot (e opcionalmente ao prompt)"""
        if not db_manager.enabled:
            return []
        
        def _get_bot_functions_operation(connection):
            cursor = connection.cursor(dictionary=True)
            
            if prompt_id:
                # Buscar funções específicas do prompt
                query = """
                    SELECT DISTINCT bf.function_id, bf.description
                    FROM bots_functions bf
                    JOIN bots_prompts_functions bpf ON bf.function_id = bpf.function_id 
                        AND bf.bot_id = bpf.bot_id
                    WHERE bf.bot_id = %s AND bpf.prompt_id = %s
                """
                cursor.execute(query, (bot_id, prompt_id))
            else:
                # Buscar funções gerais do bot (prompt_id NULL)
                query = """
                    SELECT DISTINCT bf.function_id, bf.description
                    FROM bots_functions bf
                    JOIN bots_prompts_functions bpf ON bf.function_id = bpf.function_id 
                        AND bf.bot_id = bpf.bot_id
                    WHERE bf.bot_id = %s AND bpf.prompt_id IS NULL
                """
                cursor.execute(query, (bot_id,))
            
            functions = cursor.fetchall()
            cursor.close()
            return functions
        
        result = db_manager._execute_with_fresh_connection(_get_bot_functions_operation)
        return result or []
    
    def _get_function_parameters(self, function_id, bot_id=None):
        """Busca parâmetros de uma função"""
        if not db_manager.enabled:
            return []
        
        def _get_function_parameters_operation(connection):
            cursor = connection.cursor(dictionary=True)
            if bot_id:
                query = """
                    SELECT parameter_id, type, description, permited_values, default_value, format
                    FROM bots_functions_parameters
                    WHERE function_id = %s AND bot_id = %s
                """
                cursor.execute(query, (function_id, bot_id))
            else:
                query = """
                    SELECT parameter_id, type, description, permited_values, default_value, format
                    FROM bots_functions_parameters
                    WHERE function_id = %s
                """
                cursor.execute(query, (function_id,))
            parameters = cursor.fetchall()
            cursor.close()
            return parameters
        
        result = db_manager._execute_with_fresh_connection(_get_function_parameters_operation)
        return result or []
    
    def _build_chatgpt_functions(self, functions_data, bot_id=None):
        """Constrói o array de funções no formato do ChatGPT"""
        chatgpt_functions = []
        
        for function in functions_data:
            function_id = function['function_id']
            description = function['description']
            
            # Buscar parâmetros da função
            parameters = self._get_function_parameters(function_id, bot_id)
            
            # Construir properties e required
            properties = {}
            required = []
            
            for param in parameters:
                param_name = param['parameter_id']
                param_type = param['type']
                param_description = param['description']
                
                required.append(param_name)
                
                property_def = {
                    "type": param_type,
                    "description": param_description
                }
                
                # Adicionar enum se tiver valores permitidos
                if param['permited_values']:
                    try:
                        permitted_values = json.loads(param['permited_values'])
                        property_def["enum"] = permitted_values
                    except:
                        pass
                
                # Adicionar default se tiver
                if param['default_value']:
                    property_def["default"] = param['default_value']
                
                # Adicionar format se tiver
                if param['format']:
                    property_def["format"] = param['format']
                
                properties[param_name] = property_def
            
            # Construir função no formato ChatGPT
            chatgpt_function = {
                "name": function_id,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
            
            chatgpt_functions.append(chatgpt_function)
        
        return chatgpt_functions
    
    def _build_chatgpt_functions_with_tools_format(self, functions_data, bot_id=None):
        """Constrói o array de funções no formato tools do ChatGPT"""
        chatgpt_tools = []
        
        for function in functions_data:
            function_id = function['function_id']
            description = function['description']
            
            # Buscar parâmetros da função
            parameters = self._get_function_parameters(function_id, bot_id)
            logger.info(f"🔍 INTENT-DEBUG: Parâmetros encontrados para {function_id}: {parameters}")
            
            # Construir properties e required
            properties = {}
            required = []
            
            for param in parameters:
                param_name = param['parameter_id']
                param_type = param['type']
                param_description = param['description']
                
                required.append(param_name)
                
                property_def = {
                    "type": param_type,
                    "description": param_description
                }
                
                # Adicionar enum se tiver valores permitidos
                if param['permited_values']:
                    try:
                        import json
                        permitted_values = json.loads(param['permited_values'])
                        property_def["enum"] = permitted_values
                    except:
                        pass
                
                # Adicionar default se tiver
                if param['default_value']:
                    property_def["default"] = param['default_value']
                
                # Adicionar format se tiver
                if param['format']:
                    property_def["format"] = param['format']
                
                properties[param_name] = property_def
            
            # Construir tool no formato ChatGPT
            chatgpt_tool = {
                "type": "function",
                "function": {
                    "name": function_id,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            }
            
            chatgpt_tools.append(chatgpt_tool)
        
        return chatgpt_tools
    
    def _get_intent_identification_function(self, bot_id):
        """Cria a função para identificação de intenção do usuário"""
        try:
            # Buscar todas as intents ativas do bot
            intents = db_manager.get_intents_by_bot(bot_id)
            active_intents = [intent for intent in intents if intent.get('active', True)]
            
            if not active_intents:
                logger.info(f"🤖 Bot {bot_id} não possui intents ativas - pulando identificação de intenção")
                return None
            
            # Construir as opções de enum com ID e descrição
            enum_options = []
            descriptions = []
            
            for intent in active_intents:
                intent_id = intent['id']
                intention_desc = intent.get('intention', f"Intent {intent.get('name', 'Sem nome')}")
                enum_options.append(intent_id)
                descriptions.append(f"{intent_id} ({intention_desc})")
            
            # Adicionar opção 'none' para casos de baixa confiança
            enum_options.append('none')
            descriptions.append('none (nenhuma intenção corresponde adequadamente)')
            
            # Construir descrição da função
            descriptions_text = ", ".join(descriptions)
            function_description = f"A intenção identificada do usuário, as últimas mensagens é que mais representam a intenção. Escolha uma das seguintes opções: {descriptions_text}. REGRAS: Se tiver mais de 70% de certeza, retorne a intenção identificada. Se tiver entre 30% e 70% de certeza, retorne uma pergunta para esclarecer entre as 2 intenções mais prováveis. Se tiver menos de 30% de certeza (nenhuma intenção corresponde bem), retorne 'none' como identified_intent."
            
            # Construir função para ChatGPT
            intent_function = {
                "type": "function",
                "function": {
                    "name": "identify_user_intent",
                    "description": function_description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "identified_intent": {
                                "type": "string",
                                "enum": enum_options,
                                "description": "ID da intenção identificada do usuário"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Nível de confiança na identificação (0-100)"
                            },
                            "clarification_question": {
                                "type": "string",
                                "description": "Pergunta para esclarecer a intenção (usar apenas se confidence < 70)"
                            }
                        },
                        "required": ["identified_intent", "confidence"]
                    }
                }
            }
            
            logger.info(f"🎯 Função de identificação de intenção criada com {len(active_intents)} intents para bot {bot_id}")
            return intent_function
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar função de identificação de intenção: {e}")
            return None
    
    def _identify_user_intent(self, contact_id, conversation_id, system_prompt, bot_id):
        """Identifica a intenção do usuário usando ChatGPT"""
        try:
            logger.info(f"🔍 Iniciando identificação de intenção para contact {contact_id}")
            
            # Criar função de identificação de intenção
            intent_function = self._get_intent_identification_function(bot_id)
            if not intent_function:
                return None, None
            
            # Buscar contexto apenas da conversa ativa atual (não histórico geral do usuário)
            conversation_context = self._get_conversation_context(conversation_id, limit=10)
            newline_char = '\n'
            logger.info(f"🔍 INTENT-DEBUG: Contexto da conversa {conversation_id}: {len(conversation_context.split(newline_char)) if conversation_context else 0} mensagens")
            
            # Criar prompt específico APENAS para identificação de intenção (independente do bot)
            intent_identification_prompt = f"""Você é um identificador de intenções especializado. Sua única tarefa é analisar mensagens de conversas e identificar a intenção principal do usuário.

Contexto da conversa ATIVA atual:
{conversation_context}

INSTRUÇÕES: 
1. Identifique a intenção baseada exclusivamente nas mensagens mostradas acima
2. Você DEVE chamar a função identify_user_intent para retornar a intenção identificada
3. Se a intenção não estiver clara nas mensagens desta conversa, retorne 'none'
"""
            
            # Preparar mensagens para ChatGPT
            messages = [
                {"role": "system", "content": intent_identification_prompt}
            ]
            
            # Usar ChatGPTService mas evitando processamento da função identify_user_intent
            from chatgpt_service import ChatGPTService
            chatgpt_service = ChatGPTService()
            
            logger.info(f"🤖 Enviando para ChatGPT identificação de intenção...")
            
            # Criar um contact_id temporário para identificação de intent 
            temp_contact_id = f"intent_identification_{contact_id}"
            
            try:
                # Usar o contexto da conversa como user message para análise de intenção
                user_message_for_intent = f"Analise esta conversa e identifique a intenção:\n\n{conversation_context}"
                
                response = chatgpt_service.generate_response_with_config(
                    contact_id=temp_contact_id,  # Contact ID diferente para evitar processamento
                    user_message=user_message_for_intent,
                    system_prompt=intent_identification_prompt,
                    chatgpt_functions=[intent_function]
                )
                
                logger.info(f"🔍 INTENT-DEBUG: Resposta do ChatGPT Service: {str(response)[:200]}...")
                
                # Se a resposta contém dados da função, extrair
                if isinstance(response, dict) and response.get('raw_data'):
                    raw_data = response['raw_data']
                    if isinstance(raw_data, dict):
                        choices = raw_data.get('choices', [])
                        if choices:
                            message = choices[0].get('message', {})
                            response = message  # Usar a mensagem como resposta
                        else:
                            logger.warning("❌ Nenhuma choice encontrada nos raw_data")
                    
            except Exception as api_error:
                logger.error(f"❌ Erro ao chamar ChatGPT Service: {api_error}")
                return None, None
            
            if not response:
                logger.error("❌ ChatGPT não retornou resposta para identificação de intenção")
                return None, None
            
            logger.info(f"🔍 INTENT-DEBUG: Resposta do ChatGPT: {str(response)[:200]}...")
            
            # Processar resposta - verificar tool_calls diretamente da API
            function_call = None
            
            # Novo formato (tool_calls) - formato direto da OpenAI API
            if response.get('tool_calls'):
                tool_call = response['tool_calls'][0]
                function_call = tool_call.get('function')
                logger.info(f"🔧 INTENT-DEBUG: Usando tool_calls format direto da API")
                logger.info(f"🔧 INTENT-DEBUG: Tool call completo: {str(tool_call)[:200]}...")
            # Formato antigo (function_call)
            elif response.get('function_call'):
                function_call = response['function_call']
                logger.info(f"🔧 INTENT-DEBUG: Usando function_call format")
            
            if function_call and function_call.get('name') == 'identify_user_intent':
                try:
                    import json
                    arguments = json.loads(function_call['arguments'])
                    intent_id = arguments.get('identified_intent')
                    confidence = arguments.get('confidence', 0)
                    clarification = arguments.get('clarification_question')
                    
                    logger.info(f"🎯 INTENT-DEBUG: Intent identificada com sucesso!")
                    logger.info(f"🎯 INTENT-DEBUG: intent={intent_id}")
                    logger.info(f"🎯 INTENT-DEBUG: confiança={confidence}%")
                    
                    if intent_id == 'none' or confidence < 30:
                        logger.info(f"🚫 Confiança muito baixa ({confidence}%) ou nenhuma intenção corresponde - não aplicando nenhuma intenção")
                        return None, None
                    elif confidence >= 70 and intent_id and intent_id != 'none':
                        logger.info(f"✅ Alta confiança ({confidence}%) - aplicando intenção {intent_id}")
                        return intent_id, None
                    else:
                        logger.info(f"🤔 Confiança média ({confidence}%) - solicitando esclarecimento")
                        return None, clarification
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Erro ao decodificar argumentos da função: {e}")
                    return None, None
            else:
                logger.warning(f"⚠️ ChatGPT não retornou uma function call válida para identificação de intenção")
            
                # Se não chamou função, verificar se há resposta de texto (pergunta de esclarecimento)
                if response.get('content'):
                    logger.info(f"🤔 ChatGPT retornou pergunta de esclarecimento: {response['content']}")
                    return None, response['content']
            
            logger.warning("⚠️ ChatGPT não retornou identificação de intenção válida")
            return None, None
            
        except Exception as e:
            logger.error(f"❌ Erro na identificação de intenção: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return None, None
    
    def _get_conversation_context(self, conversation_id, limit=10):
        """Busca o contexto da conversa (últimas mensagens)"""
        try:
            if not db_manager.enabled:
                return "Contexto não disponível"
            
            def _get_context_operation(connection):
                cursor = connection.cursor(dictionary=True)
                query = """
                    SELECT message_text, sender, timestamp
                    FROM conversation_message 
                    WHERE conversation_id = %s 
                    ORDER BY timestamp DESC 
                    LIMIT %s
                """
                cursor.execute(query, (conversation_id, limit))
                messages = cursor.fetchall()
                cursor.close()
                return messages
            
            messages = db_manager._execute_with_fresh_connection(_get_context_operation)
            if not messages:
                return "Nenhuma mensagem anterior encontrada"
            
            # Formatar contexto
            context_lines = []
            for msg in reversed(messages):  # Inverter para ordem cronológica
                sender = "Usuário" if msg['sender'] == 'user' else "Assistente"
                timestamp = msg['timestamp'].strftime("%H:%M") if msg['timestamp'] else ""
                context_lines.append(f"[{timestamp}] {sender}: {msg['message_text']}")
            
            return "\n".join(context_lines)
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar contexto da conversa: {e}")
            return "Erro ao carregar contexto"
    
    def _apply_intent_based_prompts_and_functions(self, intent_id, bot_id):
        """Aplica prompts e funções baseados na intenção identificada"""
        try:
            logger.info(f"🎯 Aplicando prompts e funções para intenção {intent_id}")
            
            # Buscar dados da intent
            intent = db_manager.get_intent(intent_id, bot_id)
            if not intent:
                logger.error(f"❌ Intent {intent_id} não encontrada para bot {bot_id}")
                return "", []
            
            # Extrair prompt da intent
            intent_prompt = intent.get('prompt', '')
            intent_functions = []
            
            # Se tem function_id, verificar para ajustar prompt
            function_id = intent.get('function_id')
            if function_id:
                # Adicionar instrução obrigatória ao prompt
                if intent_prompt:
                    intent_prompt += f"\n\nIMPORTANTE: Quando identificar esta intenção, você DEVE obrigatoriamente chamar a função '{function_id}' imediatamente. Não apenas responda com texto - execute a função primeiro."
                else:
                    intent_prompt = f"IMPORTANTE: Quando identificar esta intenção, você DEVE obrigatoriamente chamar a função '{function_id}' imediatamente. Não apenas responda com texto - execute a função primeiro."
            
            # Se tem function_id, buscar e preparar a função
            if function_id:
                logger.info(f"🔧 Intent possui function_id: {function_id}")
                
                try:
                    # Buscar função diretamente da tabela bots_functions (sem JOIN com prompts)
                    def _get_intent_function_operation(connection):
                        cursor = connection.cursor(dictionary=True)
                        query = """
                            SELECT function_id, description, action
                            FROM bots_functions 
                            WHERE bot_id = %s AND function_id = %s
                        """
                        cursor.execute(query, (bot_id, function_id))
                        result = cursor.fetchone()
                        cursor.close()
                        return result
                    
                    matching_function = db_manager._execute_with_fresh_connection(_get_intent_function_operation)
                    
                    if matching_function:
                        # Se encontrou função existente, usar ela
                        intent_functions = self._build_chatgpt_functions_with_tools_format([matching_function], bot_id)
                        logger.info(f"🔧 Função existente da intent preparada: {function_id}")
                        logger.info(f"🔍 INTENT-DEBUG: Estrutura da função enviada: {intent_functions}")
                        
                        # Debug: verificar parâmetros específicos
                        if intent_functions and len(intent_functions) > 0:
                            func_params = intent_functions[0].get('function', {}).get('parameters', {})
                            logger.info(f"🔍 INTENT-DEBUG: Parâmetros da função: {func_params}")
                    else:
                        # Se não encontrou, criar função customizada baseada no function_id
                        function_data = [{
                            'function_id': function_id,
                            'description': f"OBRIGATÓRIO: Execute esta função imediatamente quando identificar a intenção '{intent.get('name', function_id)}'. Esta função deve ser chamada automaticamente sempre que o usuário demonstrar esta intenção.",
                            'action': 'intent_specific'
                        }]
                        
                        # Construir função no formato ChatGPT
                        intent_functions = self._build_chatgpt_functions_with_tools_format(function_data, bot_id)
                        logger.info(f"🔧 Função customizada da intent preparada: {function_id}")
                    
                except Exception as func_error:
                    logger.error(f"❌ Erro ao preparar função da intent: {func_error}")
            
            logger.info(f"✅ Intent aplicada - Prompt: {len(intent_prompt)} chars, Funções: {len(intent_functions)}")
            return intent_prompt, intent_functions
            
        except Exception as e:
            logger.error(f"❌ Erro ao aplicar intent: {e}")
            return "", []
    
    def _process_message_received(self, event_data):
        """Processa mensagem individual recebida"""
        message_type = event_data.get('type', 'unknown')
        from_number = event_data.get('from')
        message_id = event_data.get('id')
        
        # FILTRO: Ignorar reações em todos os níveis de processamento
        if message_type == 'reaction':
            logger.info(f"🔇 Reação de {from_number} ignorada no _process_message_received - tipo 'reaction' não é processado")
            return
        
        logger.info(f"💬 Processando mensagem {message_type} de {from_number} (ID: {message_id})")
        
        # Processa mensagens de todos os números (restrição de desenvolvimento removida)
        logger.info(f"Processando mensagem de {from_number} - desenvolvimento ativo para todos os números")
        
        # Remover verificação de cache local - deixar o delay worker gerenciar as duplicatas
        # O delay worker tem melhor controle sobre quais tarefas estão realmente ativas
        
        # Buscar contato UUID pelo número de telefone
        contact_id = None
        logger.info(f"📞 Buscando UUID do contato para número: {from_number}")
        try:
            def _get_contact_by_phone_operation(connection):
                cursor = connection.cursor(dictionary=True)
                query = """
                    SELECT id, name, account_id, whatsapp_phone_number 
                    FROM contacts 
                    WHERE whatsapp_phone_number = %s
                    LIMIT 1
                """
                cursor.execute(query, (from_number,))
                result = cursor.fetchone()
                cursor.close()
                return result
            
            contact = db_manager._execute_with_fresh_connection(_get_contact_by_phone_operation)
            if contact:
                contact_id = contact['id']
                logger.info(f"✅ Contato encontrado: {contact_id} para {from_number}")
            else:
                logger.warning(f"❌ Contato não encontrado para {from_number}")
                logger.info(f"📝 Para criar conversa, é necessário processar via webhook_received completo")
                logger.info(f"💡 Recomendação: Garantir que mensagens venham como webhook_received, não message_received individual")
                return
        except Exception as contact_error:
            logger.error(f"❌ Erro ao buscar contato: {contact_error}")
            return
        
        # Buscar conversa existente
        conversation = db_manager.get_active_conversation(contact_id)
        
        if not conversation:
            logger.warning(f"❌ Nenhuma conversa ativa encontrada para {from_number}")
            logger.info(f"📝 Para criar conversa, é necessário processar via webhook_received completo")
            logger.info(f"💡 Recomendação: Garantir que mensagens venham como webhook_received, não message_received individual")
            return
        
        # Se encontrou conversa, continuar com debounce
            conversation_id = conversation['id']
            current_time = time.time()
            
            delay_task = {
                'task_type': 'chatgpt_delay_check',
            'contact_id': contact_id,
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
    
    def _process_chatgpt_delay_check(self, event_data):
        """Processa verificação de delay do ChatGPT"""
        try:
            contact_id = event_data.get('contact_id')
            conversation_id = event_data.get('conversation_id')
            created_at = event_data.get('created_at', 0)
            task_created_timestamp = event_data.get('task_created_timestamp', created_at)
            
            # NOVOS PARÂMETROS das tarefas 3 e 4
            system_prompt = event_data.get('system_prompt')  # Manter compatibilidade com formato antigo
            system_prompt_json = event_data.get('system_prompt_json')  # Novo formato JSON
            chatgpt_functions = event_data.get('chatgpt_functions', [])
            channel_id = event_data.get('channel_id')
            bot_id = event_data.get('bot_id')
            
            # Usar system_prompt_json se disponível, senão usar system_prompt (fallback)
            final_system_prompt = system_prompt_json if system_prompt_json else system_prompt
            
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
                    # Se a diferença é muito pequena (< 15s), processar imediatamente  
                    # Isso permite processar quando o usuário para de enviar mensagens por mais de 10s
                    if diff_task < 15:
                        logger.info(f"🚀 Mensagem nova detectada (+{diff_task:.1f}s), mas < 15s - processando imediatamente")
                        # Continuar com o processamento
                    else:
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
                # Já se passaram 10s, processar com ChatGPT usando conversation.system_prompt
                logger.info(f"📊 ETAPA 7 - ✅ 10s aguardados, enviando para ChatGPT...")
                try:
                    self._process_chatgpt_with_conversation_config(contact_id, conversation_id)
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
                            self._process_chatgpt_response_with_bot_config(
                                contact_id, None, final_system_prompt, chatgpt_functions, bot_id, channel_id
                            )
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

    def _process_chatgpt_response_with_bot_config(self, contact_id, message_text, system_prompt=None, chatgpt_functions=None, bot_id=None, channel_id=None):
        """Processa mensagem com ChatGPT usando configuração do bot"""
        logger.info(f"🤖 Processando ChatGPT com bot_id={bot_id}, system_prompt={bool(system_prompt)}, funções={len(chatgpt_functions or [])}")
        
        # Fallback para método anterior se não tiver novos parâmetros
        if not system_prompt:
            return self._process_chatgpt_response(contact_id, message_text)
        
        return self._process_chatgpt_response_internal(contact_id, message_text, system_prompt, chatgpt_functions)
    
    def _process_chatgpt_response_internal(self, contact_id, message_text, system_prompt=None, chatgpt_functions=None, bot_info=None):
        """Método interno para processar ChatGPT com parâmetros customizados"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"🤖 Processando com ChatGPT customizado para {contact_id} (tentativa {retry_count + 1}/{max_retries})")
                
                # Importar serviços
                try:
                    from chatgpt_service import chatgpt_service
                    from whatsapp_service import whatsapp_service
                except ImportError as e:
                    logger.error(f"❌ Erro ao importar serviços: {e}")
                    retry_count += 1
                    time.sleep(2 ** retry_count)
                    continue
                
                # Gerar resposta com ChatGPT customizado
                try:
                    import signal
                    
                    def timeout_handler(signum, frame):
                        raise TimeoutError("ChatGPT timeout")
                    
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(45)
                    
                    try:
                        # Usar método customizado com system_prompt e funções
                        if hasattr(chatgpt_service, 'process_message_with_config'):
                            chatgpt_response = chatgpt_service.process_message_with_config(
                                contact_id, message_text, system_prompt, chatgpt_functions
                            )
                        else:
                            # Fallback para método padrão
                            logger.warning("⚠️ process_message_with_config não disponível, usando método padrão")
                            chatgpt_response = chatgpt_service.process_message(contact_id, message_text)
                    finally:
                        signal.alarm(0)
                        
                except TimeoutError:
                    logger.error(f"⏰ Timeout no ChatGPT customizado para {contact_id}")
                    retry_count += 1
                    time.sleep(2 ** retry_count)
                    continue
                
                # Processar resposta (mesmo código do método original)
                if chatgpt_response:
                    logger.info(f"✅ ChatGPT customizado respondeu: {str(chatgpt_response)[:50]}...")
                    
                    # Extrair informações da resposta
                    if isinstance(chatgpt_response, dict):
                        response_text = chatgpt_response.get("response", "")
                        function_executed = chatgpt_response.get("function_executed", False)
                        tokens_used = chatgpt_response.get("tokens_used", 0)
                        request_payload = chatgpt_response.get("request_payload", {})
                    else:
                        response_text = str(chatgpt_response)
                        function_executed = False
                        tokens_used = 0
                        request_payload = {}
                    
                    if response_text:
                        # Buscar número de telefone do contato para envio via WhatsApp
                        contact = db_manager.get_contact(contact_id)
                        if contact and contact.get('whatsapp_phone_number'):
                            phone_number = contact['whatsapp_phone_number']
                            logger.info(f"📞 Enviando via WhatsApp para {phone_number} (contact: {contact_id})")
                            
                        # Enviar resposta via WhatsApp com prefixo do agent_name (se configurado)
                            if bot_info and bot_info.get('agent_name'):
                                agent_name = bot_info['agent_name']
                                chatgpt_message_with_prefix = f"*{agent_name}:*\n{response_text}"
                            else:
                                # Se não tiver agent_name configurado, enviar sem prefixo
                                chatgpt_message_with_prefix = response_text
                            success = whatsapp_service.send_text_message(phone_number, chatgpt_message_with_prefix)
                        else:
                            logger.error(f"❌ Número de telefone não encontrado para contato {contact_id}")
                            success = False
                            
                        if success:
                            logger.info(f"✅ Resposta enviada via WhatsApp para {contact_id}")
                            
                            # Salvar resposta na conversa
                            conversation = db_manager.get_active_conversation(contact_id)
                            if conversation:
                                conversation_id = conversation['id']
                                
                                # Converter request_payload para JSON string
                                import json
                                prompt_json = json.dumps(request_payload, ensure_ascii=False) if request_payload else None
                                
                                # Salvar no banco sem prefixo (já foi enviado com prefixo via WhatsApp)
                                success = db_manager.insert_conversation_message(
                                    conversation_id=conversation_id,
                                    message_text=response_text,
                                    sender='agent',
                                    message_type='text',
                                    timestamp=datetime.now(),
                                    prompt=prompt_json,
                                    tokens=tokens_used,
                                    notify_websocket=True  # NOTIFICAR WEBSOCKET
                                )
                                
                                logger.info(f"💾 Salvando resposta: tokens={tokens_used}, prompt_size={len(prompt_json) if prompt_json else 0} chars")
                                if success:
                                    logger.info(f"✅ Resposta salva na conversa {conversation_id}")
                                else:
                                    logger.warning(f"⚠️ Falha ao salvar resposta na conversa")
                        else:
                            logger.error(f"❌ Falha ao enviar resposta via WhatsApp para {contact_id}")
                    else:
                        # Se function_executed = False e response vazia → função silenciosa, continuar conversa
                        if not function_executed:
                            logger.info(f"🔄 Função silenciosa executada, chamando ChatGPT para continuar conversa...")
                            
                            # Buscar conversation_id antes de continuar
                            conversation = db_manager.get_active_conversation(contact_id)
                            if conversation:
                                conversation_id = conversation['id']
                                
                                # Chamar ChatGPT novamente para continuar a conversa naturalmente
                                try:
                                    self._process_chatgpt_with_conversation_config(contact_id, conversation_id)
                                    logger.info(f"✅ Conversa continuada após função silenciosa")
                                except Exception as continue_error:
                                    logger.error(f"❌ Erro ao continuar conversa: {continue_error}")
                            else:
                                logger.error(f"❌ Conversa não encontrada para continuar após função silenciosa")
                        else:
                            logger.warning(f"⚠️ ChatGPT retornou resposta vazia para {contact_id}")
                    
                    return True
                else:
                    logger.error(f"❌ ChatGPT não retornou resposta para {contact_id}")
                    retry_count += 1
                    time.sleep(2 ** retry_count)
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Erro no processamento ChatGPT customizado (tentativa {retry_count + 1}): {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)
                else:
                    logger.error(f"❌ Falha após {max_retries} tentativas para {contact_id}")
                    raise
        
        return False

    def _process_chatgpt_response(self, contact_id, message_text):
        """Processa mensagem com ChatGPT e envia resposta (método legado)"""
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
                    logger.info(f"✅ ChatGPT respondeu: {str(chatgpt_response)[:50]}...")
                    
                    # Extrair informações da resposta (compatibilidade com retorno object/string)
                    if isinstance(chatgpt_response, dict):
                        response_text = chatgpt_response.get("response", "")
                        function_executed = chatgpt_response.get("function_executed", False)
                        logger.info(f"🔍 Resposta do ChatGPT - function_executed: {function_executed}")
                    else:
                        # Compatibilidade com retorno string (antigo)
                        response_text = chatgpt_response
                        function_executed = False
                        logger.info(f"🔍 Resposta do ChatGPT - formato string (function_executed: False)")
                    
                    # Se uma function foi executada, não precisamos enviar mensagem duplicada
                    if function_executed:
                        logger.info(f"⚠️ Function foi executada - mensagem já enviada pela function, não enviando duplicata")
                        # Apenas salvar na conversa se não foi salva pela function
                        # Não salvar se é função encerrar_conversa (já salva ela mesma) ou outras funções que já salvam
                        skip_save_keywords = ['ticket', 'incluído', 'atendimento finalizado', 'conversa encerrada', 'obrigado pelo contato']
                        should_skip_save = any(keyword in response_text.lower() for keyword in skip_save_keywords) if response_text else False
                        
                        if response_text and not should_skip_save:
                            # Salvar resposta na conversa apenas se não for mensagem de ticket (já salva pela function)
                            conversation_saved = False
                            for save_attempt in range(3):
                                try:
                                    conversation = db_manager.get_active_conversation(contact_id)
                                    if conversation:
                                        conversation_id = conversation['id']
                                        
                                        # Salvar no banco sem prefixo (será enviado com prefixo via WhatsApp)
                                        success = db_manager.insert_conversation_message(
                                            conversation_id=conversation_id,
                                            message_text=response_text,
                                            sender='agent',
                                            message_type='text',
                                            timestamp=datetime.now(),
                                            notify_websocket=True  # NOTIFICAR WEBSOCKET
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
                        
                        # Function já tratou tudo - finalizar aqui
                        return
                    
                    # Fluxo normal - function não foi executada, enviar mensagem
                    if response_text:
                        # Salvar resposta do ChatGPT na conversa (sender=agent) com retry
                        conversation_saved = False
                        for save_attempt in range(3):
                            try:
                                conversation = db_manager.get_active_conversation(contact_id)
                                if conversation:
                                    conversation_id = conversation['id']
                                    
                                    # Salvar no banco sem prefixo (já foi enviado com prefixo via WhatsApp)
                                    success = db_manager.insert_conversation_message(
                                        conversation_id=conversation_id,
                                        message_text=response_text,
                                        sender='agent',
                                        message_type='text',
                                        timestamp=datetime.now(),
                                        notify_websocket=True  # NOTIFICAR WEBSOCKET
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
                                # Buscar agent_name do bot (se disponível)
                                agent_name = None
                                try:
                                    conversation = db_manager.get_active_conversation(contact_id)
                                    if conversation and conversation.get('channel_id'):
                                        channel = db_manager.get_channel(conversation['channel_id'])
                                        if channel and channel.get('bot_id'):
                                            bot_data = self._get_bot_data(channel['bot_id'])
                                            if bot_data and bot_data.get('agent_name'):
                                                agent_name = bot_data['agent_name']
                                except Exception as e:
                                    logger.warning(f"⚠️ Erro ao buscar agent_name do bot: {e}")
                                
                                # Enviar mensagem via WhatsApp (o prefixo será adicionado pelo whatsapp_service)
                                sent = whatsapp_service.process_outgoing_message(contact_id, response_text, agent_name)
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
                        # Buscar agent_name do bot (se disponível) para mensagem de erro
                        agent_name = None
                        try:
                            conversation = db_manager.get_active_conversation(contact_id)
                            if conversation and conversation.get('channel_id'):
                                channel = db_manager.get_channel(conversation['channel_id'])
                                if channel and channel.get('bot_id'):
                                    bot_data = self._get_bot_data(channel['bot_id'])
                                    if bot_data and bot_data.get('agent_name'):
                                        agent_name = bot_data['agent_name']
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao buscar agent_name para mensagem de erro: {e}")
                        
                        from whatsapp_service import whatsapp_service
                        whatsapp_service.process_outgoing_message(
                            contact_id, 
                            "Desculpe, estou com dificuldades técnicas no momento. Tente novamente em alguns minutos.",
                            agent_name
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
    
    def _schedule_conversation_timeout(self, contact_id):
        """Agenda timeout de 1 hora para conversas inativas (cancela timeout anterior)"""
        try:
            # Verificar se já existe conversa ativa para este contato
            conversation = db_manager.get_active_conversation(contact_id)
            if not conversation:
                # Não há conversa ativa, não precisa agendar timeout
                return
            
            conversation_id = conversation['id']
            current_time = time.time()
            
            # IMPORTANTE: Marcar o timeout com um identificador único por conversa
            # Isso permite que timeouts antigos sejam ignorados quando processados
            timeout_id = f"timeout_{conversation_id}_{int(current_time)}"
            
            # Criar tarefa de timeout para 1 hora (3600 segundos)
            timeout_task = {
                'task_type': 'conversation_timeout',
                'timeout_id': timeout_id,  # Identificador único
                'contact_id': contact_id,
                'conversation_id': conversation_id,
                'created_at': current_time,
                'timeout_reason': 'user_inactivity',
                'timeout_duration': 3600  # 1 hora em segundos
            }
            
            # Salvar o timeout_id na memória para referência
            if not hasattr(self, 'active_timeouts'):
                self.active_timeouts = {}
            self.active_timeouts[conversation_id] = timeout_id
            
            # Enviar para fila de delay com 1 hora
            from rabbitmq_manager import rabbitmq_manager
            success = rabbitmq_manager.publish_with_delay(timeout_task, delay_seconds=3600)
            
            if success:
                logger.info(f"⏰ Timeout de 1h agendado para conversa {conversation_id} (ID: {timeout_id})")
            else:
                logger.error(f"❌ Falha ao agendar timeout para conversa {conversation_id}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao agendar timeout de conversa: {e}")
    
    def _process_conversation_timeout(self, event_data):
        """Processa timeout de conversa (1h sem resposta do usuário)"""
        try:
            contact_id = event_data.get('contact_id')
            conversation_id = event_data.get('conversation_id')
            timeout_id = event_data.get('timeout_id')
            timeout_duration = event_data.get('timeout_duration', 3600)
            
            # VERIFICAR SE É O TIMEOUT MAIS RECENTE (evita processar timeouts antigos)
            if timeout_id and hasattr(self, 'active_timeouts'):
                current_timeout = self.active_timeouts.get(conversation_id)
                if current_timeout and current_timeout != timeout_id:
                    logger.info(f"⏭️ Timeout antigo ignorado para conversa {conversation_id} (ID: {timeout_id})")
                    return
            
            logger.info(f"⏰ Processando timeout de conversa {conversation_id} (contato {contact_id}, ID: {timeout_id})")
            
            # Verificar se a conversa ainda está ativa
            conversation = db_manager.get_conversation_by_id(conversation_id)
            if not conversation:
                logger.info(f"❌ Conversa {conversation_id} não encontrada - timeout cancelado")
                return
            
            if conversation.get('status') != 'active':
                logger.info(f"❌ Conversa {conversation_id} não está mais ativa - timeout cancelado")
                return
            
            # Verificar se houve mensagens recentes do usuário (cancelar timeout se sim)
            try:
                latest_messages = db_manager.get_last_user_messages(conversation_id, limit=1)
                if latest_messages:
                    last_message = latest_messages[0]
                    last_message_time = last_message.get('timestamp')
                    
                    if last_message_time:
                        # Converter para timestamp se necessário
                        if hasattr(last_message_time, 'timestamp'):
                            last_timestamp = last_message_time.timestamp()
                        else:
                            last_timestamp = last_message_time
                        
                        # Verificar se a última mensagem foi há menos de 1 hora
                        current_time = time.time()
                        time_diff = current_time - last_timestamp
                        
                        if time_diff < (timeout_duration - 60):  # Margem de 1 minuto
                            logger.info(f"❌ Timeout cancelado - usuário enviou mensagem há {time_diff/60:.1f} min")
                            return
            except Exception as e:
                logger.warning(f"⚠️ Erro ao verificar mensagens recentes: {e}")
            
            # Limpar timeout da memória
            if hasattr(self, 'active_timeouts') and conversation_id in self.active_timeouts:
                del self.active_timeouts[conversation_id]
                logger.info(f"🧹 Timeout limpo da memória para conversa {conversation_id}")
            
            # Salvar mensagem de timeout (SEM enviar para usuário)
            timeout_message = f"Se passaram {timeout_duration//60} minutos sem resposta do usuário. Fica entendido que usuário não tem mais nada a acrescentar."
            
            from datetime import datetime
            message_id = db_manager.insert_conversation_message(
                conversation_id=conversation_id,
                message_text=timeout_message,
                sender='system',  # Mensagem do sistema
                message_type='text',
                timestamp=datetime.now(),
                notify_websocket=False  # Não notificar WebSocket (mensagem interna)
            )
            
            if message_id:
                logger.info(f"💾 Mensagem de timeout salva: ID {message_id}")
            else:
                logger.error(f"❌ Falha ao salvar mensagem de timeout")
                return
            
            # Enviar contexto atualizado para IA dar seguimento
            logger.info(f"🤖 Enviando contexto para IA dar seguimento à conversa {conversation_id}")
            try:
                self._process_chatgpt_with_conversation_config(contact_id, conversation_id)
                logger.info(f"✅ IA processou timeout com sucesso para conversa {conversation_id}")
            except Exception as ai_error:
                logger.error(f"❌ Erro ao processar timeout com IA: {ai_error}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar timeout de conversa: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
    
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