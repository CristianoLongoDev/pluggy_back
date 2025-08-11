#!/usr/bin/env python3
"""
WebSocket Notifier - Integração com o sistema atual
Monitora inserções de mensagens e notifica via WebSocket
"""

import asyncio
import threading
import time
import logging
from datetime import datetime
from database import db_manager
from websocket_server import notify_new_message_sync

logger = logging.getLogger(__name__)

class WebSocketNotifier:
    def __init__(self):
        self.running = False
        self.monitor_thread = None
        
    def start_monitoring(self):
        """Inicia monitoramento em thread separada"""
        if self.running:
            logger.warning("⚠️ Notificador já está rodando")
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_database, daemon=True)
        self.monitor_thread.start()
        logger.info("🚀 WebSocket Notifier iniciado")
    
    def stop_monitoring(self):
        """Para o monitoramento"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("🛑 WebSocket Notifier parado")
    
    def _monitor_database(self):
        """Monitora banco de dados por novas mensagens"""
        last_check = datetime.now()
        
        while self.running:
            try:
                # Buscar mensagens novas nos últimos 10 segundos
                current_time = datetime.now()
                new_messages = self._get_new_messages_since(last_check)
                
                for message in new_messages:
                    self._notify_message(message)
                
                last_check = current_time
                time.sleep(2)  # Verificar a cada 2 segundos
                
            except Exception as e:
                logger.error(f"❌ Erro no monitoramento: {e}")
                time.sleep(5)  # Wait longer on error
    
    def _get_new_messages_since(self, since_time):
        """Busca mensagens novas desde um tempo específico"""
        try:
            def _get_new_messages_operation(connection):
                cursor = connection.cursor(dictionary=True)
                query = """
                    SELECT 
                        cm.id,
                        cm.conversation_id,
                        cm.message_text,
                        cm.sender,
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
                    WHERE cm.timestamp > %s
                    ORDER BY cm.timestamp ASC
                """
                cursor.execute(query, (since_time,))
                messages = cursor.fetchall()
                cursor.close()
                return messages
            
            return db_manager._execute_with_fresh_connection(_get_new_messages_operation) or []
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar mensagens novas: {e}")
            return []
    
    def _notify_message(self, message):
        """Notifica uma mensagem via WebSocket"""
        try:
            # Preparar dados da mensagem para o frontend
            message_data = {
                "id": message["id"],
                "conversation_id": message["conversation_id"],
                "message_text": message["message_text"],
                "sender": message["sender"],
                "message_type": message["message_type"],
                "timestamp": message["timestamp"].isoformat() if message["timestamp"] else None,
                "tokens": message["tokens"],
                "contact": {
                    "id": message["contact_id"],
                    "name": message["contact_name"],
                    "phone": message["whatsapp_phone_number"]
                }
            }
            
            # Notificar via WebSocket
            notify_new_message_sync(message["conversation_id"], message_data)
            
            logger.info(f"📤 Mensagem {message['id']} notificada via WebSocket (conversa {message['conversation_id']})")
            
        except Exception as e:
            logger.error(f"❌ Erro ao notificar mensagem {message.get('id', 'unknown')}: {e}")

# Instância global
websocket_notifier = WebSocketNotifier()

def notify_message_saved(conversation_id, message_id, message_text, sender, message_type="text", tokens=0):
    """
    Função para ser chamada quando uma mensagem é salva
    Pode ser chamada de qualquer lugar do código
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
        
        message_data = db_manager._execute_with_fresh_connection(_get_message_data_operation)
        
        if message_data:
            websocket_notifier._notify_message(message_data)
        else:
            logger.warning(f"⚠️ Mensagem {message_id} não encontrada para notificação WebSocket")
            
    except Exception as e:
        logger.error(f"❌ Erro ao notificar mensagem salva {message_id}: {e}")

def start_notifier():
    """Inicia o notificador"""
    websocket_notifier.start_monitoring()

def stop_notifier():
    """Para o notificador"""
    websocket_notifier.stop_monitoring()

if __name__ == "__main__":
    # Teste standalone
    start_notifier()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_notifier()