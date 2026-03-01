#!/usr/bin/env python3
"""
WebSocket Notifier Simple - Para uso nos workers
Envia notificações via HTTP para o WebSocket server
"""

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime
from database import db_manager

logger = logging.getLogger(__name__)

def notify_message_saved(conversation_id, message_id, message_text, sender, message_type="text", tokens=0):
    """
    Função para ser chamada quando uma mensagem é salva
    Envia notificação HTTP para o WebSocket server
    """
    try:
        # Buscar dados completos da mensagem
        def _get_message_data_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT 
                    cm.id,
                    cm.conversation_id,
                    cm.message_text,
                    cm.sender,
                    cm.user_id,
                    cm.message_type,
                    cm.timestamp,
                    cm.tokens,
                    c.contact_id,
                    cont.name as contact_name,
                    cont.whatsapp_phone_number,
                    b.name as bot_name,
                    b.agent_name as bot_agent_name
                FROM conversation_message cm
                JOIN conversation c ON cm.conversation_id = c.id
                LEFT JOIN contacts cont ON c.contact_id = cont.id
                LEFT JOIN channels ch ON c.channel_id = ch.id
                LEFT JOIN bots b ON ch.bot_id = b.id
                WHERE cm.id = %s
            """
            cursor.execute(query, (message_id,))
            message = cursor.fetchone()
            cursor.close()
            return message
        
        message_data_db = db_manager._execute_with_fresh_connection(_get_message_data_operation)
        
        if not message_data_db:
            logger.warning(f"⚠️ Mensagem {message_id} não encontrada para notificação WebSocket")
            return
        
        # Preparar dados para o WebSocket
        message_data = {
            "id": message_data_db["id"],
            "conversation_id": message_data_db["conversation_id"],
            "content": message_data_db["message_text"],
            "sender": message_data_db["sender"],
            "user_id": message_data_db.get("user_id"),
            "timestamp": message_data_db["timestamp"].isoformat() if message_data_db["timestamp"] else None,
            "channel": "whatsapp",
            "message_type": message_data_db["message_type"],
            "tokens": message_data_db["tokens"],
            "metadata": {
                "contact": {
                    "id": message_data_db["contact_id"],
                    "name": message_data_db["contact_name"],
                    "phone": message_data_db["whatsapp_phone_number"]
                },
                "bot": {
                    "name": message_data_db.get("bot_name"),
                    "agent_name": message_data_db.get("bot_agent_name")
                }
            }
        }
        
        # Enviar via HTTP para WebSocket server
        _send_http_notification(conversation_id, message_data)
        
        logger.info(f"📤 Mensagem {message_id} notificada via HTTP para WebSocket (conversa {conversation_id})")
        
    except Exception as e:
        logger.error(f"❌ Erro ao notificar mensagem salva {message_id}: {e}")

def _send_http_notification(conversation_id, message_data):
    """Envia notificação HTTP para o WebSocket server"""
    try:
        # URL do WebSocket server (interno do Kubernetes)
        websocket_service_url = "http://websocket-service:8765/api/notify"
        
        # Preparar dados
        notification_data = {
            "conversation_id": conversation_id,
            "message_data": message_data,
            "source": "worker_notification"
        }
        
        # Fazer requisição HTTP
        data = json.dumps(notification_data).encode('utf-8')
        req = urllib.request.Request(
            websocket_service_url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=3) as response:
            response_data = response.read().decode('utf-8')
            logger.debug(f"✅ HTTP notification sent: {response_data}")
            
    except urllib.error.URLError as e:
        logger.warning(f"⚠️ HTTP notification failed: {e}")
    except Exception as e:
        logger.warning(f"⚠️ HTTP notification error: {e}")
