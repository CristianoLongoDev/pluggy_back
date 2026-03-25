#!/usr/bin/env python3
"""
WebSocket Server para comunicação em tempo real
Permite ao frontend receber atualizações de mensagens instantaneamente
"""

import asyncio
import websockets
import json
import logging
from datetime import datetime
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
from auth_utils import validate_jwt_token

# Importar database de forma opcional (não crítica para WebSocket)
try:
    from database import db_manager
    DB_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("📊 Database manager carregado com sucesso")
except Exception as e:
    DB_AVAILABLE = False
    db_manager = None
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ Database manager não disponível: {e}")

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_ws_token(token):
    payload = validate_jwt_token(token, required_type="access")
    return payload

class NotificationHandler(BaseHTTPRequestHandler):
    """Handler HTTP para receber notificações de mensagens"""
    
    def do_POST(self):
        try:
            if self.path == '/api/notify':
                # Ler dados da requisição
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                conversation_id = data.get('conversation_id')
                message_data = data.get('message_data')
                
                if not conversation_id or not message_data:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Missing conversation_id or message_data"}).encode())
                    return
                
                # Chamar o WebSocket server de forma async
                def notify_async():
                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # Chamar a função do WebSocket server
                        success = loop.run_until_complete(
                            websocket_server.handle_http_notification(conversation_id, message_data)
                        )
                        
                        loop.close()
                        
                        if success:
                            logger.info(f"✅ HTTP-NOTIFY: Notificação processada para conversa {conversation_id}")
                        else:
                            logger.error(f"❌ HTTP-NOTIFY: Falha ao processar notificação para conversa {conversation_id}")
                            
                    except Exception as notify_error:
                        logger.error(f"❌ HTTP-NOTIFY: Erro na notificação: {notify_error}")
                
                # Executar em thread separada
                thread = threading.Thread(target=notify_async, daemon=True)
                thread.start()
                
                # Responder sucesso imediatamente
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode())
                
            else:
                self.send_response(404)
                self.end_headers()
                
        except Exception as e:
            logger.error(f"❌ HTTP-NOTIFY: Erro no handler: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
    
    def log_message(self, format, *args):
        # Suprimir logs do HTTPServer
        pass

class WebSocketServer:
    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.clients = {}  # {client_id: {"websocket": ws, "account_id": "", "conversations": []}}
        self.running = False
        
    async def register_client(self, websocket, client_data):
        """Registra um cliente WebSocket"""
        try:
            client_id = f"{client_data['account_id']}_{int(time.time())}"
            self.clients[client_id] = {
                "websocket": websocket,
                "account_id": client_data["account_id"],
                "conversations": client_data.get("conversations", []),
                "connected_at": datetime.now()
            }
            
            logger.info(f"✅ Cliente registrado: {client_id} (Account: {client_data['account_id']})")
            
            # Enviar confirmação
            await websocket.send(json.dumps({
                "type": "connection_confirmed",
                "client_id": client_id,
                "timestamp": datetime.now().isoformat()
            }))
            
            return client_id
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar cliente: {e}")
            return None
    
    async def unregister_client(self, client_id):
        """Remove cliente da lista"""
        if client_id in self.clients:
            del self.clients[client_id]
            logger.info(f"🚪 Cliente desconectado: {client_id}")
    

    async def authenticate_client(self, token):
        """Autentica cliente via JWT local (HS256)"""
        try:
            if not token:
                logger.error("❌ Token não fornecido (None ou vazio)")
                return {"valid": False, "error": "Token não fornecido"}
                
            logger.info(f"🔐 Iniciando autenticação WebSocket com token: {token[:50]}...")
            
            payload = validate_jwt_token(token)
            if payload:
                user_id = payload.get("sub")
                email = payload.get("email")
                account_id = payload.get("account_id")
                
                if not account_id:
                    logger.warning(f"❌ Account_id não encontrado no JWT para user {user_id}")
                    return {"valid": False, "error": "Account_id não encontrado no token"}
                
                logger.info(f"✅ Autenticação WebSocket OK - User: {user_id}, Email: {email}, Account: {account_id}")
                logger.info(f"🔍 Claims completos do token: {list(payload.keys())}")
                
                return {
                    "account_id": account_id,
                    "user_id": user_id,
                    "email": email,
                    "valid": True
                }
            else:
                logger.warning("❌ Token JWT inválido no WebSocket - validate_jwt_token retornou None")
                return {"valid": False, "error": "Token inválido"}
                
        except Exception as e:
            logger.error(f"❌ Erro na autenticação WebSocket: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return {"valid": False, "error": "Erro interno na autenticação"}
    
    async def handle_http_notification(self, conversation_id, message_data):
        """Processa notificações HTTP de mensagens dos workers"""
        try:
            logger.info(f"🌐 HTTP-NOTIFY: Recebida notificação para conversa {conversation_id}")
            
            # Chamar broadcast_message diretamente
            await self.broadcast_message(conversation_id, message_data)
            
            logger.info(f"✅ HTTP-NOTIFY: Notificação processada para conversa {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ HTTP-NOTIFY: Erro ao processar notificação: {e}")
            return False

    async def handle_client_message(self, websocket, message, client_id):
        """Processa mensagens do cliente"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "subscribe_conversations":
                # Cliente quer monitorar conversas específicas ou todas do account
                conversation_ids = data.get("data", {}).get("conversation_ids", []) or data.get("conversation_ids", [])
                
                if client_id in self.clients:
                    client_info = self.clients[client_id]
                    account_id = client_info.get("account_id")
                    
                    # Se não foram fornecidos conversation_ids específicos, buscar todas do account
                    if not conversation_ids and account_id and DB_AVAILABLE:
                        logger.info(f"🔍 Buscando todas as conversas para account {account_id}")
                        conversations = await self.get_account_conversations(account_id)
                        conversation_ids = [conv["id"] for conv in conversations]
                        
                        # Atualizar as conversas do cliente
                        self.clients[client_id]["conversations"] = conversation_ids
                        
                        # Enviar resposta com as conversas completas
                        await websocket.send(json.dumps({
                            "type": "subscription_updated",
                            "conversation_ids": conversation_ids,
                            "data": {
                                "conversations": conversations
                            },
                            "timestamp": datetime.now().isoformat()
                        }))
                        logger.info(f"📺 Cliente {client_id} inscrito em {len(conversation_ids)} conversas do account {account_id}")
                    else:
                        # Comportamento original para conversation_ids específicos
                        self.clients[client_id]["conversations"] = conversation_ids
                        await websocket.send(json.dumps({
                            "type": "subscription_updated",
                            "conversation_ids": conversation_ids,
                            "timestamp": datetime.now().isoformat()
                        }))
                        logger.info(f"📺 Cliente {client_id} inscrito em {len(conversation_ids)} conversas específicas")
            
            elif message_type == "get_messages":
                # Cliente quer buscar mensagens de uma conversa específica
                message_data = data.get("data", {})
                conversation_id_raw = message_data.get("conversation_id")
                limit = message_data.get("limit", 50)  # Padrão: 50 mensagens
                offset = message_data.get("offset", 0)  # Padrão: sem offset
                
                logger.info(f"🔍 DEBUG - Parâmetros recebidos: conversation_id={conversation_id_raw}, limit={limit}, offset={offset}")
                
                if not conversation_id_raw:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": "conversation_id é obrigatório para get_messages"
                    }))
                    return
                
                # Validar parâmetros
                try:
                    conversation_id = int(conversation_id_raw)
                    limit = min(int(limit), 1000)  # Máximo de 1000 mensagens por requisição
                    offset = max(int(offset), 0)   # Offset não pode ser negativo
                    logger.info(f"✅ Parâmetros validados: conversation_id={conversation_id}, limit={limit}, offset={offset}")
                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Erro ao validar parâmetros: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": f"Parâmetros inválidos: conversation_id deve ser um número, limit e offset devem ser inteiros"
                    }))
                    return
                
                if client_id in self.clients:
                    client_info = self.clients[client_id]
                    account_id = client_info.get("account_id")
                    
                    # Buscar mensagens da conversa com paginação
                    logger.info(f"📨 Cliente {client_id} solicitou mensagens da conversa {conversation_id} (limit={limit}, offset={offset})")
                    result = await self.get_conversation_messages(conversation_id, account_id, limit, offset)
                    
                    # Extrair mensagens e status da conversa
                    if isinstance(result, dict):
                        messages = result.get("messages", [])
                        conversation_status = result.get("conversation_status")
                    else:
                        # Fallback para compatibilidade (se retornar formato antigo)
                        messages = result if isinstance(result, list) else []
                        conversation_status = None
                    
                    # Enviar mensagens para o cliente
                    response_data = {
                        "type": "messages_response",
                        "conversation_id": conversation_id,
                        "data": {
                            "messages": messages,
                            "conversation_status": conversation_status,  # NOVO CAMPO
                            "pagination": {
                                "limit": limit,
                                "offset": offset,
                                "total": len(messages),
                                "has_more": len(messages) == limit  # Se retornou exatamente o limit, pode haver mais
                            }
                        },
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    logger.info(f"🔍 DEBUG - Enviando resposta: type={response_data['type']}, conversation_id={response_data['conversation_id']}, total_messages={len(messages)}, status={conversation_status}")
                    if messages:
                        logger.info(f"🔍 DEBUG - Primeira mensagem: {messages[0]}")
                        logger.info(f"🔍 DEBUG - Última mensagem: {messages[-1]}")
                    
                    await websocket.send(json.dumps(response_data))
                    logger.info(f"📤 Enviadas {len(messages)} mensagens da conversa {conversation_id} para cliente {client_id} (limit={limit}, offset={offset}, status={conversation_status})")
            
            elif message_type == "send_message":
                # Cliente quer enviar uma mensagem
                message_data = data.get("data", {})
                conversation_id_raw = message_data.get("conversation_id")
                content = message_data.get("content", "").strip()
                sender = message_data.get("sender")  # Usar exatamente o que o frontend envia
                user_id = message_data.get("user_id")  # NOVO: Campo user_id
                
                logger.info(f"📤 Cliente {client_id} quer enviar mensagem: conversation_id={conversation_id_raw}, content='{content[:50]}...', sender={sender}, user_id={user_id}")
                
                if not conversation_id_raw or not content:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": "conversation_id e content são obrigatórios para send_message"
                    }))
                    return
                
                if not sender:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": "sender é obrigatório para send_message"
                    }))
                    return
                
                try:
                    conversation_id = int(conversation_id_raw)
                    
                    if client_id in self.clients:
                        client_info = self.clients[client_id]
                        account_id = client_info.get("account_id")
                        
                        # Salvar mensagem no banco (agora com user_id)
                        success = await self.save_outgoing_message(conversation_id, account_id, content, sender, user_id)
                        
                        if success:
                            await websocket.send(json.dumps({
                                "type": "message_sent",
                                "conversation_id": conversation_id,
                                "timestamp": datetime.now().isoformat()
                            }))
                            logger.info(f"✅ Mensagem enviada com sucesso pelo cliente {client_id} na conversa {conversation_id}")
                        else:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "error": "Falha ao salvar mensagem"
                            }))
                            
                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Erro ao processar send_message: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": "Parâmetros inválidos para send_message"
                    }))
            
            elif message_type == "ping":
                # Manter conexão viva
                await websocket.send(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }))
                
        except json.JSONDecodeError:
            logger.error(f"❌ Mensagem JSON inválida de {client_id}: {message}")
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem de {client_id}: {e}")
    
    async def handle_client(self, websocket, path):
        """Gerencia conexão de um cliente"""
        client_id = None
        try:
            client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
            logger.info(f"🔗 Nova conexão WebSocket recebida de {client_ip} no path: {path}")
            logger.info(f"🔍 Headers da conexão: {dict(websocket.request_headers) if hasattr(websocket, 'request_headers') else 'N/A'}")
            logger.info(f"🔍 Protocolo WebSocket: {websocket.protocol if hasattr(websocket, 'protocol') else 'N/A'}")
            logger.info(f"🔍 Estado da conexão: {websocket.state if hasattr(websocket, 'state') else 'N/A'}")
            
            # Aguardar autenticação
            logger.info(f"⏳ Aguardando mensagem de autenticação de {client_ip}...")
            try:
                auth_message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                logger.info(f"📨 Mensagem de autenticação recebida ({len(auth_message)} chars): {auth_message[:200]}...")
            except asyncio.TimeoutError:
                logger.error(f"❌ Timeout aguardando autenticação de {client_ip}")
                await websocket.close(code=4000, reason="Timeout de autenticação")
                return
            except Exception as e:
                logger.error(f"❌ Erro ao receber mensagem de autenticação de {client_ip}: {e}")
                return
            
            try:
                auth_data = json.loads(auth_message)
                token_in_root = bool(auth_data.get('token'))
                token_in_data = bool(auth_data.get('data', {}).get('token')) if isinstance(auth_data.get('data'), dict) else False
                logger.info(f"🔍 Dados de autenticação parseados: type={auth_data.get('type')}, token_in_root={token_in_root}, token_in_data={token_in_data}")
                logger.info(f"🔍 Estrutura completa: {json.dumps(auth_data, indent=2)[:500]}...")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Erro ao parsear JSON da autenticação de {client_ip}: {e}")
                logger.error(f"❌ Raw message: {auth_message}")
                await websocket.send(json.dumps({"error": "JSON inválido"}))
                await websocket.close(code=4002, reason="JSON inválido")
                return
            
            if auth_data.get("type") != "authenticate":
                logger.warning(f"❌ Tipo de mensagem incorreto de {client_ip}: {auth_data.get('type')}")
                await websocket.send(json.dumps({"error": "Autenticação requerida"}))
                await websocket.close(code=4001, reason="Autenticação requerida")
                return
            
            # Validar token (buscar em data.token)
            token_data = auth_data.get("data", {})
            token = token_data.get("token") if isinstance(token_data, dict) else auth_data.get("token")
            logger.info(f"🔐 Extraindo token para autenticação de {client_ip}: {token[:50] if token else 'None'}...")
            
            if not token:
                logger.error(f"❌ Token não encontrado na mensagem de {client_ip}")
                await websocket.send(json.dumps({"error": "Token não fornecido"}))
                await websocket.close(code=4003, reason="Token não fornecido")
                return
            
            auth_result = await self.authenticate_client(token)
            logger.info(f"🔐 Resultado da autenticação para {client_ip}: {auth_result}")
            
            if not auth_result["valid"]:
                logger.error(f"❌ Autenticação falhou para {client_ip}: {auth_result.get('error')}")
                await websocket.send(json.dumps({"error": auth_result["error"]}))
                await websocket.close(code=4004, reason=auth_result["error"])
                return
            
            logger.info(f"✅ Autenticação bem-sucedida para {client_ip}")
            
            # Registrar cliente
            client_id = await self.register_client(websocket, auth_result)
            if not client_id:
                logger.error(f"❌ Falha ao registrar cliente {client_ip}")
                await websocket.close(code=4005, reason="Falha no registro")
                return
            
            logger.info(f"✅ Cliente {client_id} registrado com sucesso para {client_ip}")
            
            # Loop principal - escutar mensagens
            async for message in websocket:
                await self.handle_client_message(websocket, message, client_id)
                
        except asyncio.TimeoutError:
            logger.warning("⏰ Timeout na autenticação")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 Conexão fechada: {client_id or 'não autenticado'}")
        except Exception as e:
            logger.error(f"❌ Erro na conexão: {e}")
        finally:
            if client_id:
                await self.unregister_client(client_id)
    
    async def broadcast_message(self, conversation_id, message_data):
        """Envia mensagem para clientes interessados"""
        logger.info(f"🔍 BROADCAST-DEBUG: Iniciando broadcast para conversa {conversation_id}")
        logger.info(f"🔍 BROADCAST-DEBUG: Total de clientes conectados: {len(self.clients)}")
        
        if not self.clients:
            logger.warning(f"⚠️ BROADCAST-DEBUG: Nenhum cliente conectado")
            return
        
        message_payload = {
            "type": "new_message",
            "conversation_id": conversation_id,
            "data": message_data,
            "timestamp": datetime.now().isoformat()
        }
        
        # Encontrar clientes interessados nesta conversa
        interested_clients = []
        for client_id, client_info in self.clients.items():
            logger.info(f"🔍 BROADCAST-DEBUG: Cliente {client_id} - conversations: {client_info['conversations']}")
            
            if (not client_info["conversations"] or  # Se não especificou conversas, recebe todas
                conversation_id in client_info["conversations"]):
                interested_clients.append(client_id)
                logger.info(f"✅ BROADCAST-DEBUG: Cliente {client_id} interessado na conversa {conversation_id}")
            else:
                logger.info(f"❌ BROADCAST-DEBUG: Cliente {client_id} NÃO interessado na conversa {conversation_id}")
        
        logger.info(f"🔍 BROADCAST-DEBUG: Total de clientes interessados: {len(interested_clients)}")
        
        # Verificar se é uma nova conversa (primeira mensagem) para fazer refresh
        should_refresh_new_conversation = await self._is_new_conversation(conversation_id)
        
        # Enviar para clientes interessados
        if interested_clients:
            logger.info(f"📤 Enviando mensagem da conversa {conversation_id} para {len(interested_clients)} clientes")
            
            # Enviar assincronamente para todos
            tasks = []
            for client_id in interested_clients:
                client_info = self.clients.get(client_id)
                if client_info:
                    task = self._send_to_client(client_info["websocket"], message_payload, client_id)
                    tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        else:
            logger.warning(f"⚠️ BROADCAST-DEBUG: Nenhum cliente interessado na conversa {conversation_id}")
        
        # Se é uma nova conversa, sempre fazer refresh para clientes com conversas específicas
        if should_refresh_new_conversation:
            logger.info(f"🔄 BROADCAST-DEBUG: Nova conversa {conversation_id} detectada - fazendo refresh para todos os clientes")
            await self.refresh_conversations_for_new_conversation(conversation_id)
    
    async def _send_to_client(self, websocket, message_payload, client_id):
        """Envia mensagem para um cliente específico"""
        try:
            await websocket.send(json.dumps(message_payload))
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"⚠️ Cliente {client_id} desconectado durante envio")
            await self.unregister_client(client_id)
        except Exception as e:
            logger.error(f"❌ Erro ao enviar para cliente {client_id}: {e}")
    
    async def _is_new_conversation(self, conversation_id):
        """Verifica se é uma nova conversa (poucas mensagens)"""
        try:
            if not DB_AVAILABLE or not db_manager:
                return False
                
            def _count_messages_operation(connection):
                cursor = connection.cursor()
                query = "SELECT COUNT(*) FROM conversation_message WHERE conversation_id = %s"
                cursor.execute(query, (conversation_id,))
                count = cursor.fetchone()[0]
                cursor.close()
                return count
            
            message_count = db_manager._execute_with_fresh_connection(_count_messages_operation)
            
            # Consideramos nova conversa se tem 2 mensagens ou menos (user + primeira resposta bot)
            is_new = message_count <= 2
            logger.info(f"🔍 NEW-CONV-DEBUG: Conversa {conversation_id} tem {message_count} mensagens - é nova: {is_new}")
            return is_new
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar se conversa {conversation_id} é nova: {e}")
            return False
    
    async def refresh_conversations_for_new_conversation(self, conversation_id):
        """Atualiza lista de conversas para clientes que usam [] (todas as conversas)"""
        try:
            # Buscar informações da conversa nova
            if not DB_AVAILABLE or not db_manager:
                return
                
            def _get_conversation_account_operation(connection):
                cursor = connection.cursor(dictionary=True)
                query = """
                    SELECT c.id, ct.account_id 
                    FROM conversation c
                    LEFT JOIN contacts ct ON c.contact_id = ct.id
                    WHERE c.id = %s AND c.status = 'active'
                """
                cursor.execute(query, (conversation_id,))
                result = cursor.fetchone()
                cursor.close()
                return result
            
            conversation_info = db_manager._execute_with_fresh_connection(_get_conversation_account_operation)
            
            if not conversation_info:
                logger.debug(f"🔍 Conversa {conversation_id} não encontrada ou não é ativa")
                return
                
            account_id = conversation_info['account_id']
            logger.info(f"🔄 REFRESH-DEBUG: Nova conversa {conversation_id} para account {account_id}")
            
            # Atualizar clientes que monitoram todas as conversas (lista vazia)
            clients_to_update = []
            for client_id, client_info in self.clients.items():
                if (client_info.get("account_id") == account_id and 
                    not client_info.get("conversations")):  # Lista vazia = todas as conversas
                    clients_to_update.append(client_id)
            
            if clients_to_update:
                logger.info(f"🔄 REFRESH-DEBUG: Atualizando {len(clients_to_update)} clientes")
                
                # Buscar conversas atualizadas
                conversations = await self.get_account_conversations(account_id)
                conversation_ids = [conv["id"] for conv in conversations]
                
                # Notificar cada cliente
                for client_id in clients_to_update:
                    client_info = self.clients.get(client_id)
                    if client_info:
                        # Atualizar lista no cliente
                        self.clients[client_id]["conversations"] = conversation_ids
                        
                        # Enviar notificação
                        update_payload = {
                            "type": "subscription_updated",
                            "conversation_ids": conversation_ids,
                            "data": {
                                "conversations": conversations,
                                "new_conversation_id": conversation_id
                            },
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        await self._send_to_client(client_info["websocket"], update_payload, client_id)
                        logger.info(f"✅ REFRESH-DEBUG: Cliente {client_id} atualizado com nova conversa {conversation_id}")
            else:
                logger.debug(f"🔍 REFRESH-DEBUG: Nenhum cliente para atualizar")
                
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar conversas para nova conversa {conversation_id}: {e}")
    
    async def get_account_conversations(self, account_id):
        """Busca todas as conversas de um account"""
        if not DB_AVAILABLE or not db_manager:
            logger.warning("⚠️ Database não disponível para buscar conversas")
            return []
        
        # Verificar se a conexão do banco está funcionando
        if not db_manager.enabled:
            logger.info("🔄 Tentando reconectar ao banco de dados...")
            if not db_manager.connect():
                logger.warning("⚠️ Não foi possível conectar ao banco de dados")
                return []
        
        try:
            def _get_conversations_operation(connection):
                cursor = connection.cursor(dictionary=True)
                query = """
                    SELECT 
                        c.id,
                        c.contact_id,
                        c.channel_id,
                        c.status,
                        c.status_attendance,
                        c.started_at,
                        c.ended_at,
                        ct.name as contact_name,
                        ct.whatsapp_phone_number as contact_phone,
                        ct.email as contact_email,
                        ch.name as channel_name,
                        ch.type as channel_type,
                        b.name as bot_name,
                        b.agent_name as bot_agent_name,
                        (SELECT COUNT(*) FROM conversation_message cm WHERE cm.conversation_id = c.id) as message_count,
                        (SELECT cm.message_text FROM conversation_message cm WHERE cm.conversation_id = c.id ORDER BY cm.timestamp DESC LIMIT 1) as last_message,
                        (SELECT cm.timestamp FROM conversation_message cm WHERE cm.conversation_id = c.id ORDER BY cm.timestamp DESC LIMIT 1) as last_message_time
                    FROM conversation c
                    LEFT JOIN contacts ct ON c.contact_id = ct.id
                    LEFT JOIN channels ch ON c.channel_id = ch.id
                    LEFT JOIN bots b ON ch.bot_id = b.id
                    WHERE ct.account_id = %s 
                      AND c.status = 'active'
                    ORDER BY c.started_at DESC
                    LIMIT 100
                """
                cursor.execute(query, (account_id,))
                conversations = cursor.fetchall()
                cursor.close()
                
                # Converter para formato padronizado
                standardized_conversations = []
                for conv in conversations:
                    # Calcular unread_count (simplificado: assumir que mensagens não lidas são as do cliente)
                    unread_count = 0  # Implementar lógica real depois se necessário
                    
                    # Determinar status padronizado
                    status = self._normalize_conversation_status(conv.get('status'), conv.get('status_attendance'))
                    
                    standardized_conv = {
                        "id": conv["id"],
                        "customer_name": conv.get("contact_name", "Cliente"),
                        "channel": "whatsapp",
                        "status": status,
                        "conversation_status": conv.get("status", "active"),  # NOVO: status original do banco
                        "created_at": conv["started_at"].isoformat() if conv.get("started_at") else None,
                        "updated_at": conv["last_message_time"].isoformat() if conv.get("last_message_time") else None,
                        "last_message": conv.get("last_message", ""),
                        "unread_count": unread_count,
                        "metadata": {
                            "contact": {
                                "id": conv.get("contact_id"),
                                "phone": conv.get("contact_phone"),
                                "email": conv.get("contact_email")
                            },
                            "channel": {
                                "id": conv.get("channel_id"),
                                "name": conv.get("channel_name"),
                                "type": conv.get("channel_type")
                            },
                            "bot": {
                                "name": conv.get("bot_name"),
                                "agent_name": conv.get("bot_agent_name")
                            },
                            "stats": {
                                "message_count": conv.get("message_count", 0),
                                "ended_at": conv["ended_at"].isoformat() if conv.get("ended_at") else None
                            }
                        }
                    }
                    standardized_conversations.append(standardized_conv)
                
                return standardized_conversations
            
            conversations = db_manager._execute_with_fresh_connection(_get_conversations_operation)
            logger.info(f"✅ Encontradas {len(conversations)} conversas para account {account_id}")
            return conversations or []
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar conversas do account {account_id}: {e}")
            return []
    
    async def get_conversation_messages(self, conversation_id, account_id, limit=50, offset=0):
        """Busca todas as mensagens de uma conversa específica"""
        if not DB_AVAILABLE or not db_manager:
            logger.warning("⚠️ Database não disponível para buscar mensagens")
            return {"messages": [], "conversation_status": None}
        
        # Verificar se a conexão do banco está funcionando
        if not db_manager.enabled:
            logger.info("🔄 Tentando reconectar ao banco de dados...")
            if not db_manager.connect():
                logger.warning("⚠️ Não foi possível conectar ao banco de dados")
                return {"messages": [], "conversation_status": None}
        
        try:
            def _get_messages_operation(connection):
                cursor = connection.cursor(dictionary=True)
                
                # Primeiro verificar se a conversa pertence ao account e buscar status (segurança)
                security_query = """
                    SELECT c.id, c.status 
                    FROM conversation c
                    LEFT JOIN contacts ct ON c.contact_id = ct.id
                    WHERE c.id = %s AND ct.account_id = %s
                """
                cursor.execute(security_query, (conversation_id, account_id))
                conversation_info = cursor.fetchone()
                if not conversation_info:
                    cursor.close()
                    logger.warning(f"⚠️ Conversa {conversation_id} não pertence ao account {account_id}")
                    return {"messages": [], "conversation_status": None}
                
                # Buscar mensagens da conversa com informações do bot (com paginação)
                query = """
                    SELECT 
                        cm.id,
                        cm.conversation_id,
                        cm.message_text,
                        cm.sender,
                        cm.message_type,
                        cm.timestamp,
                        cm.prompt,
                        cm.tokens,
                        cm.user_id,
                        b.name as bot_name,
                        b.agent_name as bot_agent_name
                    FROM conversation_message cm
                    LEFT JOIN conversation c ON cm.conversation_id = c.id
                    LEFT JOIN channels ch ON c.channel_id = ch.id
                    LEFT JOIN bots b ON ch.bot_id = b.id
                    WHERE cm.conversation_id = %s
                    ORDER BY cm.timestamp ASC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(query, (conversation_id, limit, offset))
                messages = cursor.fetchall()
                cursor.close()
                
                # Converter para formato padronizado
                standardized_messages = []
                for msg in messages:
                    standardized_msg = {
                        "id": msg["id"],
                        "conversation_id": msg["conversation_id"],
                        "content": msg["message_text"],  # Padronizar para 'content'
                        "sender": msg["sender"],  # Usar valor original da tabela (user/agent/human)
                        "timestamp": msg["timestamp"].isoformat() if msg.get("timestamp") else None,
                        "channel": "whatsapp",
                        "message_type": msg["message_type"],
                        "tokens": msg.get("tokens", 0),
                        "user_id": msg.get("user_id"),  # Incluir user_id (null se não existir)
                        "metadata": {
                            "bot": {
                                "name": msg.get("bot_name"),
                                "agent_name": msg.get("bot_agent_name")
                            },
                            "prompt": msg.get("prompt")
                        }
                    }
                    standardized_messages.append(standardized_msg)
                
                return {
                    "messages": standardized_messages,
                    "conversation_status": conversation_info["status"]
                }
            
            result = db_manager._execute_with_fresh_connection(_get_messages_operation)
            if result and isinstance(result, dict):
                messages = result.get("messages", [])
                conversation_status = result.get("conversation_status")
                logger.info(f"✅ Encontradas {len(messages)} mensagens para conversa {conversation_id} (status: {conversation_status})")
                return {
                    "messages": messages,
                    "conversation_status": conversation_status
                }
            else:
                logger.warning(f"⚠️ Formato inesperado de retorno para conversa {conversation_id}")
                return {"messages": [], "conversation_status": None}
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar mensagens da conversa {conversation_id}: {e}")
            return {"messages": [], "conversation_status": None}
    
    def _normalize_sender_value(self, sender):
        """Normaliza valores do campo sender"""
        sender_mapping = {
            "user": "customer",  # Usuário do WhatsApp = customer
            "bot": "ai",         # Bot/IA = ai
            "agent": "agent",    # Agente humano = agent
            "system": "ai"       # Sistema = ai
        }
        return sender_mapping.get(sender, sender)
    
    def _normalize_conversation_status(self, status, status_attendance):
        """Normaliza status da conversa para ai|human|waiting"""
        # Priorizar status_attendance se disponível
        if status_attendance:
            if status_attendance in ['human', 'agent']:
                return "human"
            elif status_attendance in ['ai', 'bot']:
                return "ai"
            elif status_attendance in ['waiting', 'pending']:
                return "waiting"
        
        # Fallback para status principal
        if status:
            if status in ['closed', 'resolved']:
                return "ai"  # Conversa encerrada pelo AI
            elif status in ['active', 'open']:
                return "ai"  # Assumir AI por padrão se ativo
            elif status in ['waiting', 'pending']:
                return "waiting"
        
        return "ai"  # Padrão
    
    async def save_outgoing_message(self, conversation_id, account_id, content, sender, user_id=None):
        """Salva mensagem enviada pelo agente no banco de dados"""
        try:
            if not DB_AVAILABLE or not db_manager:
                logger.warning("⚠️ Database não disponível para salvar mensagem")
                return False
            
            # Verificar se a conversa pertence ao account (segurança)
            def _verify_and_save_operation(connection):
                cursor = connection.cursor(dictionary=True)
                
                # Verificar se a conversa pertence ao account
                security_query = """
                    SELECT c.id 
                    FROM conversation c
                    LEFT JOIN contacts ct ON c.contact_id = ct.id
                    WHERE c.id = %s AND ct.account_id = %s
                """
                cursor.execute(security_query, (conversation_id, account_id))
                if not cursor.fetchone():
                    cursor.close()
                    logger.warning(f"⚠️ Conversa {conversation_id} não pertence ao account {account_id}")
                    return False
                
                # Salvar mensagem (agora com user_id)
                from datetime import datetime
                message_query = """
                    INSERT INTO conversation_message 
                    (conversation_id, message_text, sender, message_type, timestamp, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(message_query, (
                    conversation_id, 
                    content, 
                    sender, 
                    'text', 
                    datetime.now(),
                    user_id
                ))
                
                message_id = cursor.lastrowid
                connection.commit()
                cursor.close()
                
                return message_id
            
            message_id = db_manager._execute_with_fresh_connection(_verify_and_save_operation)
            
            if message_id:
                logger.info(f"✅ Mensagem salva com ID {message_id} na conversa {conversation_id}")
                
                # Notificar via WebSocket para outros clientes
                try:
                    from websocket_notifier import notify_message_saved
                    notify_message_saved(conversation_id, message_id, content, sender)
                except Exception as notify_error:
                    logger.warning(f"⚠️ Falha ao notificar WebSocket: {notify_error}")
                
                return True
            else:
                return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar mensagem: {e}")
            return False
    
    async def start_server(self):
        """Inicia o servidor WebSocket"""
        self.running = True
        logger.info(f"🚀 Iniciando WebSocket Server em {self.host}:{self.port}")
        
        server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            ping_interval=30,
            ping_timeout=10
        )
        
        logger.info(f"✅ WebSocket Server rodando em ws://{self.host}:{self.port}")
        
        # Manter servidor rodando
        await server.wait_closed()
    
    def get_stats(self):
        """Retorna estatísticas do servidor"""
        return {
            "connected_clients": len(self.clients),
            "clients": [
                {
                    "client_id": client_id,
                    "account_id": info["account_id"],
                    "conversations_count": len(info["conversations"]),
                    "connected_at": info["connected_at"].isoformat()
                }
                for client_id, info in self.clients.items()
            ]
        }

# Instância global do servidor
websocket_server = WebSocketServer()

# Função para ser chamada pelos workers
async def notify_new_message(conversation_id, message_data):
    """Função para notificar nova mensagem via WebSocket"""
    await websocket_server.broadcast_message(conversation_id, message_data)

def notify_new_message_sync(conversation_id, message_data):
    """Versão síncrona para chamar de código não-async"""
    try:
        import threading
        
        logger.info(f"🔔 Tentando notificar mensagem via WebSocket: conversa {conversation_id}")
        
        # Tentar diferentes abordagens para executar a função async
        try:
            # Abordagem 1: Tentar obter loop existente
            loop = asyncio.get_running_loop()
            # Se conseguiu, usar create_task
            future = asyncio.run_coroutine_threadsafe(
                notify_new_message(conversation_id, message_data), 
                loop
            )
            logger.info(f"✅ Notificação agendada via loop existente")
        except RuntimeError:
            # Abordagem 2: Executar em thread separada com novo loop
            def run_in_thread():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.run_until_complete(notify_new_message(conversation_id, message_data))
                    new_loop.close()
                    logger.info(f"✅ Notificação executada via thread separada")
                except Exception as thread_e:
                    logger.error(f"❌ Erro na thread de notificação: {thread_e}")
            
            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()
            
    except Exception as e:
        logger.error(f"❌ Erro ao notificar mensagem via WebSocket: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")

def start_http_server():
    """Inicia servidor HTTP para receber notificações em thread separada"""
    try:
        server = HTTPServer(('0.0.0.0', 8765), NotificationHandler)
        logger.info(f"✅ Servidor HTTP iniciado na porta 8765 para notificações")
        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Erro no servidor HTTP: {e}")
        import traceback
        logger.error(f"❌ Traceback HTTP: {traceback.format_exc()}")

async def start_websocket_and_http():
    """Inicia WebSocket server e HTTP server em paralelo"""
    global websocket_server
    
    try:
        logger.info("🚀 Iniciando servidores HTTP (8765) e WebSocket (8766)")
        
        # Iniciar servidor HTTP em thread separada
        http_thread = threading.Thread(target=start_http_server, daemon=True)
        http_thread.start()
        logger.info("🌐 Servidor HTTP iniciado em thread separada")
        
        # Aguardar um pouco para o HTTP server iniciar
        await asyncio.sleep(2)
        
        # Recriar instância do WebSocket server com porta 8766
        websocket_server = WebSocketServer(host="0.0.0.0", port=8766)
        logger.info(f"🔌 Iniciando WebSocket server na porta {websocket_server.port}...")
        await websocket_server.start_server()
        
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar servidores: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    asyncio.run(start_websocket_and_http())