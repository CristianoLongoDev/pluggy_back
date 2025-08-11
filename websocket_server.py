#!/usr/bin/env python3
"""
WebSocket Server para comunicação em tempo real
Permite ao frontend receber atualizações de mensagens instantaneamente
"""

import asyncio
import websockets
import json
import logging
import jwt
from jwt import PyJWKClient
from datetime import datetime
import threading
import time
import requests
from config import JWT_SECRET_KEY, SUPABASE_JWKS_URL

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

# Cliente JWKS global (cache)
jwks_client = None

def get_jwks_client():
    """
    Obtém cliente JWKS do Supabase (com cache)
    """
    global jwks_client
    
    if jwks_client is None:
        if not SUPABASE_JWKS_URL:
            logger.error("❌ SUPABASE_JWKS_URL não configurado")
            return None
        
        try:
            logger.info(f"🔑 Criando cliente JWKS para: {SUPABASE_JWKS_URL}")
            
            # Criar cliente JWKS com configuração básica compatível
            jwks_client = PyJWKClient(
                SUPABASE_JWKS_URL,
                cache_keys=True,
                max_cached_keys=10
            )
            
            logger.info(f"✅ Cliente JWKS criado com sucesso")
            
            # Testar o cliente imediatamente
            test_response = requests.get(SUPABASE_JWKS_URL, timeout=5)
            if test_response.status_code == 200:
                jwks_data = test_response.json()
                logger.info(f"✅ JWKS endpoint funcionando: {len(jwks_data.get('keys', []))} chaves encontradas")
            else:
                logger.warning(f"⚠️ JWKS endpoint retornou: {test_response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao criar cliente JWKS: {e}")
            return None
    
    return jwks_client

def validate_jwt_token(token):
    """
    Valida token JWT do Supabase usando JWT Signing Keys (nova API)
    """
    try:
        logger.info(f"🔐 Iniciando validação JWT para token: {token[:30]}...")
        
        if not token:
            logger.error("❌ Token JWT está vazio ou None")
            return None
            
        if not isinstance(token, str):
            logger.error(f"❌ Token JWT não é string: {type(token)}")
            return None
        
        if not SUPABASE_JWKS_URL:
            logger.error("❌ SUPABASE_JWKS_URL não configurado")
            return None
        
        logger.info(f"🔗 SUPABASE_JWKS_URL configurado: {SUPABASE_JWKS_URL}")
        
        # Obter cliente JWKS
        client = get_jwks_client()
        if not client:
            logger.error("❌ Falha ao obter cliente JWKS")
            return None
        
        # Obter cabeçalho do token para extrair kid (key ID)
        try:
            unverified_header = jwt.get_unverified_header(token)
            algorithm = unverified_header.get('alg')
            kid = unverified_header.get('kid')
            typ = unverified_header.get('typ')
            logger.info(f"🔍 Token header: alg={algorithm}, kid={kid}, typ={typ}")
            logger.info(f"🔍 Header completo: {unverified_header}")
            
            if not kid:
                logger.warning("⚠️ Token JWT sem 'kid' no header")
                return None
        except Exception as e:
            logger.error(f"❌ Erro ao extrair header do token: {e}")
            logger.error(f"❌ Token problematico: {token[:100]}...")
            return None
        
        # Buscar chave pública correspondente
        try:
            logger.info(f"🔍 Buscando chave pública para kid: {kid}")
            signing_key = client.get_signing_key(kid)
            public_key = signing_key.key
            logger.info(f"✅ Chave pública obtida com sucesso")
        except Exception as e:
            logger.error(f"❌ Erro ao obter chave pública para kid '{kid}': {e}")
            return None
        
        # Validar token com chave pública - TENTATIVA SEM VALIDAÇÃO DE AUDIENCE/ISSUER PRIMEIRO
        try:
            logger.info(f"🔐 Tentando validação simples primeiro...")
            
            # Primeira tentativa: sem audience/issuer para debug
            payload_simple = jwt.decode(
                token,
                public_key,
                algorithms=['RS256', 'ES256', 'HS256'],  # Incluir HS256 também
                options={"verify_aud": False, "verify_iss": False}
            )
            
            logger.info(f"✅ Token decodificado com sucesso (validação simples)")
            logger.info(f"🔍 Claims encontrados: {list(payload_simple.keys())}")
            logger.info(f"🔍 Audience (aud): {payload_simple.get('aud')}")
            logger.info(f"🔍 Issuer (iss): {payload_simple.get('iss')}")
            logger.info(f"🔍 Algorithm usado: {algorithm}")
            
            # Agora tentar com validação completa usando os valores reais
            actual_issuer = payload_simple.get('iss')
            actual_audience = payload_simple.get('aud')
            
            if actual_issuer and actual_audience:
                logger.info(f"🔐 Tentando validação completa com aud={actual_audience}, iss={actual_issuer}")
                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=[algorithm],
                    audience=actual_audience,
                    issuer=actual_issuer
                )
                logger.info(f"✅ Token JWT totalmente válido para usuário: {payload.get('sub', 'unknown')}")
                return payload
            else:
                logger.warning("⚠️ Token sem audience/issuer, usando validação simples")
                return payload_simple
                
        except jwt.ExpiredSignatureError:
            logger.warning("⚠️ Token JWT expirado")
            return None
        except jwt.InvalidAudienceError as e:
            logger.warning(f"⚠️ Token JWT com audience inválida: {e}")
            return None
        except jwt.InvalidIssuerError as e:
            logger.warning(f"⚠️ Token JWT com issuer inválido: {e}")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"⚠️ Token JWT inválido: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro na validação da assinatura: {e}")
            return None
        
    except jwt.ExpiredSignatureError:
        logger.warning("⚠️ Token JWT expirado")
        return None
    except jwt.InvalidAudienceError as e:
        logger.warning(f"⚠️ Token JWT com audience inválida: {e}")
        return None
    except jwt.InvalidIssuerError as e:
        logger.warning(f"⚠️ Token JWT com issuer inválido: {e}")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"⚠️ Token JWT inválido: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Erro ao validar token JWT: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return None

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
        """Autentica cliente via JWT usando validação do Supabase"""
        try:
            if not token:
                logger.error("❌ Token não fornecido (None ou vazio)")
                return {"valid": False, "error": "Token não fornecido"}
                
            logger.info(f"🔐 Iniciando autenticação WebSocket com token: {token[:50]}...")
            
            payload = validate_jwt_token(token)
            if payload:
                # Extrair informações do payload do Supabase
                user_id = payload.get("sub")  # Supabase usa 'sub' para user ID
                email = payload.get("email")
                account_id = payload.get("account_id")  # Usar account_id diretamente do Supabase
                
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
                conversation_id_raw = data.get("data", {}).get("conversation_id")
                
                logger.info(f"🔍 DEBUG - conversation_id recebido: {conversation_id_raw} (tipo: {type(conversation_id_raw)})")
                
                if not conversation_id_raw:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": "conversation_id é obrigatório para get_messages"
                    }))
                    return
                
                # Converter para integer se necessário
                try:
                    conversation_id = int(conversation_id_raw)
                    logger.info(f"✅ conversation_id convertido para int: {conversation_id}")
                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Erro ao converter conversation_id para int: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": f"conversation_id deve ser um número válido, recebido: {conversation_id_raw}"
                    }))
                    return
                
                if client_id in self.clients:
                    client_info = self.clients[client_id]
                    account_id = client_info.get("account_id")
                    
                    # Buscar mensagens da conversa
                    logger.info(f"📨 Cliente {client_id} solicitou mensagens da conversa {conversation_id}")
                    messages = await self.get_conversation_messages(conversation_id, account_id)
                    
                    # Enviar mensagens para o cliente
                    response_data = {
                        "type": "messages_response",
                        "conversation_id": conversation_id,
                        "data": {
                            "messages": messages
                        },
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    logger.info(f"🔍 DEBUG - Enviando resposta: type={response_data['type']}, conversation_id={response_data['conversation_id']}, total_messages={len(messages)}")
                    if messages:
                        logger.info(f"🔍 DEBUG - Primeira mensagem: {messages[0]}")
                        logger.info(f"🔍 DEBUG - Última mensagem: {messages[-1]}")
                    
                    await websocket.send(json.dumps(response_data))
                    logger.info(f"📤 Enviadas {len(messages)} mensagens da conversa {conversation_id} para cliente {client_id}")
            
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
        if not self.clients:
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
            if (not client_info["conversations"] or  # Se não especificou conversas, recebe todas
                conversation_id in client_info["conversations"]):
                interested_clients.append(client_id)
        
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
    
    async def _send_to_client(self, websocket, message_payload, client_id):
        """Envia mensagem para um cliente específico"""
        try:
            await websocket.send(json.dumps(message_payload))
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"⚠️ Cliente {client_id} desconectado durante envio")
            await self.unregister_client(client_id)
        except Exception as e:
            logger.error(f"❌ Erro ao enviar para cliente {client_id}: {e}")
    
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
                    ORDER BY c.started_at DESC
                    LIMIT 100
                """
                cursor.execute(query, (account_id,))
                conversations = cursor.fetchall()
                cursor.close()
                
                # Converter datetime para string para JSON
                for conv in conversations:
                    if conv.get('started_at'):
                        conv['started_at'] = conv['started_at'].isoformat()
                    if conv.get('ended_at'):
                        conv['ended_at'] = conv['ended_at'].isoformat()
                    if conv.get('last_message_time'):
                        conv['last_message_time'] = conv['last_message_time'].isoformat()
                
                return conversations
            
            conversations = db_manager._execute_with_fresh_connection(_get_conversations_operation)
            logger.info(f"✅ Encontradas {len(conversations)} conversas para account {account_id}")
            return conversations or []
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar conversas do account {account_id}: {e}")
            return []
    
    async def get_conversation_messages(self, conversation_id, account_id):
        """Busca todas as mensagens de uma conversa específica"""
        if not DB_AVAILABLE or not db_manager:
            logger.warning("⚠️ Database não disponível para buscar mensagens")
            return []
        
        # Verificar se a conexão do banco está funcionando
        if not db_manager.enabled:
            logger.info("🔄 Tentando reconectar ao banco de dados...")
            if not db_manager.connect():
                logger.warning("⚠️ Não foi possível conectar ao banco de dados")
                return []
        
        try:
            def _get_messages_operation(connection):
                cursor = connection.cursor(dictionary=True)
                
                # Primeiro verificar se a conversa pertence ao account (segurança)
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
                    return []
                
                # Buscar mensagens da conversa com informações do bot
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
                        b.name as bot_name,
                        b.agent_name as bot_agent_name
                    FROM conversation_message cm
                    LEFT JOIN conversation c ON cm.conversation_id = c.id
                    LEFT JOIN channels ch ON c.channel_id = ch.id
                    LEFT JOIN bots b ON ch.bot_id = b.id
                    WHERE cm.conversation_id = %s
                    ORDER BY cm.timestamp ASC
                    LIMIT 1000
                """
                cursor.execute(query, (conversation_id,))
                messages = cursor.fetchall()
                cursor.close()
                
                # Converter datetime para string para JSON
                for msg in messages:
                    if msg.get('timestamp'):
                        msg['timestamp'] = msg['timestamp'].isoformat()
                    
                    # Parsear metadata JSON se existir
                    if msg.get('metadata'):
                        try:
                            if isinstance(msg['metadata'], str):
                                msg['metadata'] = json.loads(msg['metadata'])
                        except (json.JSONDecodeError, TypeError):
                            msg['metadata'] = {}
                    else:
                        msg['metadata'] = {}
                
                return messages
            
            messages = db_manager._execute_with_fresh_connection(_get_messages_operation)
            logger.info(f"✅ Encontradas {len(messages)} mensagens para conversa {conversation_id}")
            return messages or []
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar mensagens da conversa {conversation_id}: {e}")
            return []
    
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

if __name__ == "__main__":
    asyncio.run(websocket_server.start_server())