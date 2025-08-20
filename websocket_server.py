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
                sender = message_data.get("sender", "agent")
                user_id = message_data.get("user_id")  # NOVO: Campo user_id
                
                logger.info(f"📤 Cliente {client_id} quer enviar mensagem: conversation_id={conversation_id_raw}, content='{content[:50]}...', sender={sender}, user_id={user_id}")
                
                if not conversation_id_raw or not content:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": "conversation_id e content são obrigatórios para send_message"
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
                        "sender": self._normalize_sender_value(msg["sender"]),  # Padronizar valores
                        "timestamp": msg["timestamp"].isoformat() if msg.get("timestamp") else None,
                        "channel": "whatsapp",
                        "message_type": msg["message_type"],
                        "tokens": msg.get("tokens", 0),
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

if __name__ == "__main__":
    asyncio.run(websocket_server.start_server())