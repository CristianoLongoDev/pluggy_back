from flask import Flask, jsonify, request, redirect, render_template_string
from flask_cors import CORS
import json
import logging
import os
from config import (
    WEBHOOK_VERIFY_TOKEN, DEBUG, HOST, PORT, LOG_LEVEL,
    SSL_CERT_PATH, SSL_KEY_PATH, USE_SSL,
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_ENABLED,
    RABBITMQ_ENABLED, RABBITMQ_HOST, RABBITMQ_PORT,
    SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_JWKS_URL,
    AUTH_BOOTSTRAP_SECRET, AUTH_REFRESH_TTL_SECONDS,
    AUTH_JWT_ACCESS_TTL_SECONDS, AUTH_JWT_ISSUER, AUTH_JWT_AUDIENCE,
    AUTH_ACCEPT_SUPABASE_TOKENS, PASSWORD_RESET_TTL_SECONDS,
    FRONTEND_URL
)
from database import db_manager
from rabbitmq_manager import rabbitmq_manager
from datetime import datetime
import hashlib
import secrets
import traceback
import time
import uuid
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import asyncio
import threading
from functools import wraps
import requests
from auth_utils import (
    create_refresh_token,
    hash_refresh_token,
    issue_access_token,
    validate_jwt_token,
)
from email_service import send_password_reset_email

# Configurar logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Permite acesso de outros domínios

def _extract_bearer_token():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    try:
        return auth_header.split(" ")[1]
    except IndexError:
        return None

def jwt_required(f):
    """
    Decorador para proteger endpoints com autenticação JWT
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return jsonify({
                "error": "Token de autorização é obrigatório",
                "status": "error"
            }), 401

        payload = validate_jwt_token(token, required_type="access")
        if not payload:
            return jsonify({
                "error": "Token inválido ou expirado",
                "status": "error"
            }), 401
        
        # Adicionar payload do usuário ao request para uso posterior
        request.current_user = payload
        
        return f(*args, **kwargs)
    
    return decorated_function

@app.teardown_appcontext
def close_database_connection(exception=None):
    """Fecha a conexão com o banco ao finalizar a aplicação"""
    try:
        if db_manager and hasattr(db_manager, 'disconnect'):
            db_manager.disconnect()
    except Exception as e:
        logger.error(f"Erro ao fechar conexão no teardown: {e}")

@app.route('/')
def home():
    """
    Rota principal da API - informações básicas
    """
    return jsonify({
        "message": "WhatsApp Webhook API",
        "status": "active",
        "version": "1.0.0",
        "endpoints": {
            "/api": "API principal",
            "/health": "Health check",
            "/webhook": "Webhook do WhatsApp",
            "/logs": "Consultar logs",
            "/rabbitmq/status": "Status do RabbitMQ",
            "/accounts": "Criar nova conta (POST)",
            "/accounts/<id>": "Buscar conta por ID (GET - JWT obrigatório)",
            "/channels": "Listar/Criar canais (GET/POST - JWT obrigatório)",
            "/channels/<id>": "Buscar/Atualizar/Deletar canal permanentemente (GET/PUT/DELETE - JWT obrigatório)",
            "/channels/security/audit": "Auditoria de segurança da filtragem (GET - JWT obrigatório)",
            "/bots": "Listar/Criar bots (GET/POST - JWT obrigatório)",
            "/bots/<id>": "Buscar/Atualizar/Deletar bot permanentemente (GET/PUT/DELETE - JWT obrigatório)",
            "/bots/security/audit": "Auditoria de segurança da filtragem de bots (GET - JWT obrigatório)",
            "/bots/<bot_id>/prompts": "Listar/Criar prompts de bot (GET/POST - JWT obrigatório)",
            "/bots/<bot_id>/prompts/<id>": "Atualizar/Deletar prompt (PUT/DELETE - JWT obrigatório)",
            "/bots/<bot_id>/functions": "Listar/Criar funções de bot (GET/POST - JWT obrigatório)",
            "/bots/<bot_id>/functions/<id>": "Atualizar/Deletar função (PUT/DELETE - JWT obrigatório)",
            "/bots/<bot_id>/functions/<function_id>/parameters": "Listar/Criar/Atualizar/Deletar parâmetros - suporta operações batch (GET/POST/PUT/DELETE - JWT obrigatório)",
            "/bots/<bot_id>/functions/<function_id>/parameters/<id>": "Atualizar/Deletar parâmetro (PUT/DELETE - JWT obrigatório)",
            "/whatsapp/token/optimize": "Otimizar token WhatsApp (POST - JWT obrigatório)",
            "/whatsapp/phone/config": "Config telefone WhatsApp (GET - JWT obrigatório)",
            "/whatsapp/token/status": "Status token WhatsApp (GET - JWT obrigatório)",
            "/auth/jwt/test": "Testar validação JWT (POST - JWT obrigatório)",
            "/auth/jwt/status": "Status da configuração JWT (GET - público)",
            "/auth/jwt/decode": "Debug: decodificar token JWT (POST - não valida)"
        }
    })

@app.route('/api')
def api():
    """
    Endpoint da API - retorna dados JSON
    """
    return jsonify({
        "message": "HELLO WORLD",
        "status": "success",
        "endpoint": "/api",
        "database_status": db_manager.get_connection_status(),
        "rabbitmq_status": rabbitmq_manager.get_status()
    })

@app.route('/accounts', methods=['POST'])
def create_account():
    """
    Endpoint para criar uma nova conta
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter dados do JSON
        data = request.get_json()
        
        # Validação dos dados obrigatórios
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        if 'id' not in data or not data['id']:
            return jsonify({
                "error": "Campo 'id' é obrigatório",
                "status": "error"
            }), 400
        
        if 'name' not in data or not data['name']:
            return jsonify({
                "error": "Campo 'name' é obrigatório",
                "status": "error"
            }), 400
        
        # Validar formato do UUID (opcional, mas recomendado)
        try:
            uuid.UUID(data['id'])
        except ValueError:
            return jsonify({
                "error": "Campo 'id' deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se a conta já existe
        existing_account = db_manager.get_account(data['id'])
        if existing_account:
            return jsonify({
                "error": "Conta com este ID já existe",
                "status": "error",
                "existing_account": existing_account
            }), 409
        
        # Inserir nova conta
        success = db_manager.insert_account(data['id'], data['name'])
        
        if success:
            # Buscar a conta criada para retornar
            new_account = db_manager.get_account(data['id'])
            
            logger.info(f"✅ Nova conta criada: ID={data['id']}, Nome={data['name']}")
            
            return jsonify({
                "message": "Conta criada com sucesso",
                "status": "success",
                "account": new_account
            }), 201
        else:
            logger.error(f"❌ Falha ao criar conta: ID={data['id']}, Nome={data['name']}")
            return jsonify({
                "error": "Falha ao criar conta no banco de dados",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint create_account: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/accounts/<account_id>', methods=['GET'])
@jwt_required
def get_account_by_id(account_id):
    """
    Endpoint para buscar uma conta pelo ID
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Validar formato do UUID
        try:
            uuid.UUID(account_id)
        except ValueError:
            return jsonify({
                "error": "ID deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Garantir isolamento por tenant: conta do token deve bater com a rota
        token_account_id = get_account_id_from_token()
        if token_account_id and token_account_id != account_id:
            return jsonify({
                "error": "Acesso negado para esta conta",
                "status": "error"
            }), 403

        # Buscar conta
        account = db_manager.get_account(account_id)
        
        if account:
            # Obter informações do usuário autenticado
            user_info = {
                "user_id": request.current_user.get('sub'),
                "email": request.current_user.get('email'),
                "role": request.current_user.get('role', 'user')
            }
            
            logger.info(f"✅ Usuário {user_info['user_id']} acessou conta {account_id}")
            
            return jsonify({
                "status": "success",
                "account": account,
                "authenticated_user": user_info
            }), 200
        else:
            return jsonify({
                "error": "Conta não encontrada",
                "status": "error"
            }), 404
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_account: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500


@app.route('/users', methods=['GET'])
@jwt_required
def list_users():
    """
    Lista usuários da conta autenticada
    """
    try:
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503

        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400

        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        if limit > 100:
            limit = 100

        users, total = db_manager.list_users_by_account(account_id, limit, offset)

        for user in users:
            for field in ('last_login_at', 'created_at', 'updated_at'):
                if user.get(field):
                    user[field] = user[field].isoformat()

        logger.info(f"✅ Listados {len(users)} usuários para account {account_id}")

        return jsonify({
            "status": "success",
            "data": {
                "users": users,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_next": offset + limit < total
                }
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ Erro no endpoint list_users: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500


@app.route('/users', methods=['POST'])
@jwt_required
def create_user():
    """Cria um novo usuário na conta autenticada."""
    try:
        if not db_manager.enabled:
            return jsonify({"error": "Banco de dados não está habilitado", "status": "error"}), 503

        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({"error": "Token JWT não contém account_id válido", "status": "error"}), 400

        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        full_name = data.get("full_name")
        role = data.get("role") or "user"
        department = data.get("department")

        if not email or not password:
            return jsonify({"error": "email e password são obrigatórios", "status": "error"}), 400

        existing = db_manager.get_user_by_email(email)
        if existing:
            return jsonify({"error": "Usuário já existe com este e-mail", "status": "error"}), 409

        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)
        ok = db_manager.insert_user(
            user_id=user_id,
            email=email,
            password_hash=password_hash,
            account_id=account_id,
            full_name=full_name,
            role=role,
            department=department,
            is_active=True,
        )
        if not ok:
            return jsonify({"error": "Falha ao criar usuário", "status": "error"}), 500

        logger.info(f"✅ Usuário {user_id} criado na account {account_id}")
        return jsonify({"status": "success", "user_id": user_id}), 201

    except Exception as e:
        logger.error(f"❌ Erro no endpoint create_user: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Erro interno do servidor: {str(e)}", "status": "error"}), 500


@app.route('/users/<user_id>', methods=['PUT'])
@jwt_required
def update_user(user_id):
    """Atualiza dados de um usuário da conta autenticada."""
    try:
        if not db_manager.enabled:
            return jsonify({"error": "Banco de dados não está habilitado", "status": "error"}), 503

        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({"error": "Token JWT não contém account_id válido", "status": "error"}), 400

        data = request.get_json() or {}

        ok = db_manager.update_user(
            user_id=user_id,
            account_id=account_id,
            full_name=data.get("full_name"),
            role=data.get("role"),
            department=data.get("department"),
            is_active=data.get("is_active"),
        )
        if not ok:
            return jsonify({"error": "Usuário não encontrado ou nenhum campo alterado", "status": "error"}), 404

        logger.info(f"✅ Usuário {user_id} atualizado na account {account_id}")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"❌ Erro no endpoint update_user: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Erro interno do servidor: {str(e)}", "status": "error"}), 500


@app.route('/users/<user_id>', methods=['DELETE'])
@jwt_required
def delete_user(user_id):
    """Remove um usuário da conta autenticada."""
    try:
        if not db_manager.enabled:
            return jsonify({"error": "Banco de dados não está habilitado", "status": "error"}), 503

        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({"error": "Token JWT não contém account_id válido", "status": "error"}), 400

        current_user_id = request.current_user.get("user_id")
        if current_user_id == user_id:
            return jsonify({"error": "Não é possível excluir a si mesmo", "status": "error"}), 400

        ok = db_manager.delete_user(user_id=user_id, account_id=account_id)
        if not ok:
            return jsonify({"error": "Usuário não encontrado", "status": "error"}), 404

        logger.info(f"✅ Usuário {user_id} removido da account {account_id}")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"❌ Erro no endpoint delete_user: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Erro interno do servidor: {str(e)}", "status": "error"}), 500


@app.route('/conversations', methods=['GET'])
@jwt_required
def list_conversations():
    """
    Lista conversas da conta autenticada
    """
    try:
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503

        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400

        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        status = request.args.get('status', None)
        if limit > 100:
            limit = 100

        conversations, total = db_manager.list_conversations_by_account(
            account_id, limit, offset, status
        )

        formatted = []
        for conv in conversations:
            started_at = conv['started_at'].isoformat() if conv.get('started_at') else None
            ended_at = conv['ended_at'].isoformat() if conv.get('ended_at') else None
            last_msg_time = conv['last_message_time'].isoformat() if conv.get('last_message_time') else None

            formatted.append({
                "conversation_id": conv['conversation_id'],
                "status": conv['status'],
                "status_attendance": conv.get('status_attendance'),
                "started_at": started_at,
                "ended_at": ended_at,
                "message_count": conv.get('message_count', 0),
                "last_message": {
                    "text": conv.get('last_message'),
                    "timestamp": last_msg_time
                } if conv.get('last_message') else None,
                "contact": {
                    "id": conv['contact_id'],
                    "name": conv.get('contact_name'),
                    "phone": conv.get('contact_phone'),
                    "email": conv.get('contact_email')
                },
                "channel": {
                    "id": conv.get('channel_id'),
                    "name": conv.get('channel_name'),
                    "type": conv.get('channel_type')
                }
            })

        logger.info(f"✅ Listadas {len(formatted)} conversas para account {account_id}")

        return jsonify({
            "status": "success",
            "data": {
                "conversations": formatted,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_next": offset + limit < total
                }
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ Erro no endpoint list_conversations: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500


# ==================== HELPER FUNCTIONS ====================

def get_account_id_from_token():
    """
    Extrai o account_id do token JWT do usuário autenticado
    Agora está direto no root do JWT, não mais no user_metadata
    """
    try:
        # Buscar account_id direto no root do JWT (novo formato)
        account_id = request.current_user.get('account_id')
        
        if not account_id:
            logger.warning(f"⚠️ Token JWT não contém account_id")
            return None
        
        # Validar se é um UUID válido
        try:
            uuid.UUID(account_id)
        except ValueError:
            logger.warning(f"⚠️ account_id inválido no token: {account_id}")
            return None
        
        return account_id
        
    except Exception as e:
        logger.error(f"❌ Erro ao extrair account_id do token: {e}")
        return None

def get_user_name_by_id(user_id):
    """
    Busca o nome do usuário pelo user_id no MySQL (auth local)
    """
    try:
        if not user_id:
            return None
        user = db_manager.get_user_by_id(user_id)
        if not user:
            return None
        return user.get("full_name") or user.get("email")
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar nome do usuário {user_id}: {e}")
        return None


# ==================== AUTH ENDPOINTS (LOCAL) ====================

@app.route("/auth/login", methods=["POST"])
def auth_login():
    try:
        if not db_manager.enabled:
            return jsonify({"error": "Banco de dados não está habilitado", "status": "error"}), 503

        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        if not email or not password:
            return jsonify({"error": "email e password são obrigatórios", "status": "error"}), 400

        user = db_manager.get_user_by_email(email)
        # Mensagem genérica para não vazar existência de usuário
        if not user or not user.get("is_active"):
            return jsonify({"error": "Credenciais inválidas", "status": "error"}), 401

        if not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Credenciais inválidas", "status": "error"}), 401

        access_token = issue_access_token(
            user_id=user["id"],
            email=user["email"],
            account_id=user.get("account_id"),
            role=user.get("role") or "user",
        )

        refresh_token = create_refresh_token()
        refresh_hash = hash_refresh_token(refresh_token)
        expires_at = datetime.utcnow() + timedelta(seconds=AUTH_REFRESH_TTL_SECONDS)
        db_manager.store_refresh_token(user["id"], refresh_hash, expires_at)
        db_manager.update_user_last_login(user["id"])

        return jsonify(
            {
                "status": "success",
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": AUTH_JWT_ACCESS_TTL_SECONDS,
                "refresh_token": refresh_token,
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "account_id": user.get("account_id"),
                    "full_name": user.get("full_name"),
                    "role": user.get("role") or "user",
                },
            }
        ), 200
    except Exception as e:
        logger.error(f"❌ Erro no login: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Erro interno do servidor", "status": "error"}), 500


@app.route("/auth/refresh", methods=["POST"])
def auth_refresh():
    try:
        if not db_manager.enabled:
            return jsonify({"error": "Banco de dados não está habilitado", "status": "error"}), 503

        data = request.get_json() or {}
        refresh_token = data.get("refresh_token") or ""
        if not refresh_token:
            return jsonify({"error": "refresh_token é obrigatório", "status": "error"}), 400

        token_hash = hash_refresh_token(refresh_token)
        stored = db_manager.get_refresh_token_by_hash(token_hash)
        if not stored or stored.get("revoked_at"):
            return jsonify({"error": "Refresh token inválido", "status": "error"}), 401

        # Expiração
        expires_at = stored.get("expires_at")
        if not expires_at or expires_at <= datetime.utcnow():
            db_manager.revoke_refresh_token_by_hash(token_hash)
            return jsonify({"error": "Refresh token expirado", "status": "error"}), 401

        user = db_manager.get_user_by_id(stored["user_id"])
        if not user or not user.get("is_active"):
            return jsonify({"error": "Usuário inválido", "status": "error"}), 401

        # Rotação: revogar o antigo e emitir um novo
        db_manager.revoke_refresh_token_by_hash(token_hash)

        new_refresh = create_refresh_token()
        new_hash = hash_refresh_token(new_refresh)
        new_expires = datetime.utcnow() + timedelta(seconds=AUTH_REFRESH_TTL_SECONDS)
        db_manager.store_refresh_token(user["id"], new_hash, new_expires)

        access_token = issue_access_token(
            user_id=user["id"],
            email=user["email"],
            account_id=user.get("account_id"),
            role=user.get("role") or "user",
        )

        return jsonify(
            {
                "status": "success",
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": AUTH_JWT_ACCESS_TTL_SECONDS,
                "refresh_token": new_refresh,
            }
        ), 200

    except Exception as e:
        logger.error(f"❌ Erro no refresh: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Erro interno do servidor", "status": "error"}), 500


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    try:
        if not db_manager.enabled:
            return jsonify({"error": "Banco de dados não está habilitado", "status": "error"}), 503

        data = request.get_json() or {}
        refresh_token = data.get("refresh_token") or ""
        if not refresh_token:
            return jsonify({"error": "refresh_token é obrigatório", "status": "error"}), 400

        token_hash = hash_refresh_token(refresh_token)
        db_manager.revoke_refresh_token_by_hash(token_hash)
        return jsonify({"status": "success", "message": "Logout realizado"}), 200
    except Exception as e:
        logger.error(f"❌ Erro no logout: {e}")
        return jsonify({"error": "Erro interno do servidor", "status": "error"}), 500


@app.route("/auth/me", methods=["GET"])
@jwt_required
def auth_me():
    user_id = request.current_user.get("sub")
    if not user_id:
        return jsonify({"error": "Token inválido", "status": "error"}), 401
    user = db_manager.get_user_by_id(user_id) if db_manager.enabled else None
    return jsonify(
        {
            "status": "success",
            "user": user
            or {
                "id": request.current_user.get("sub"),
                "email": request.current_user.get("email"),
                "account_id": request.current_user.get("account_id"),
                "role": request.current_user.get("role", "user"),
            },
        }
    ), 200


@app.route("/auth/bootstrap/create-user", methods=["POST"])
def auth_bootstrap_create_user():
    """
    Endpoint seguro para criar o primeiro(s) usuário(s).
    Habilita somente se AUTH_BOOTSTRAP_SECRET estiver definido.
    """
    try:
        if not AUTH_BOOTSTRAP_SECRET:
            return jsonify({"error": "Endpoint desabilitado", "status": "error"}), 404

        provided = request.headers.get("X-Bootstrap-Secret", "")
        if not provided or provided != AUTH_BOOTSTRAP_SECRET:
            return jsonify({"error": "Não autorizado", "status": "error"}), 403

        if not db_manager.enabled:
            return jsonify({"error": "Banco de dados não está habilitado", "status": "error"}), 503

        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        account_id = data.get("account_id")
        full_name = data.get("full_name")
        role = data.get("role") or "admin"

        if not email or not password:
            return jsonify({"error": "email e password são obrigatórios", "status": "error"}), 400

        existing = db_manager.get_user_by_email(email)
        if existing:
            return jsonify({"error": "Usuário já existe", "status": "error"}), 409

        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)
        ok = db_manager.insert_user(
            user_id=user_id,
            email=email,
            password_hash=password_hash,
            account_id=account_id,
            full_name=full_name,
            role=role,
            is_active=True,
        )
        if not ok:
            return jsonify({"error": "Falha ao criar usuário", "status": "error"}), 500

        return jsonify({"status": "success", "user_id": user_id}), 201
    except Exception as e:
        logger.error(f"❌ Erro no bootstrap create-user: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Erro interno do servidor", "status": "error"}), 500


@app.route("/auth/reset-password/request", methods=["POST"])
def auth_reset_password_request():
    """
    Endpoint público — o usuário informa o e-mail e recebe um link de reset por e-mail.
    Resposta genérica para não vazar existência de contas.
    """
    try:
        if not db_manager.enabled:
            return jsonify({"error": "Banco de dados não está habilitado", "status": "error"}), 503

        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        if not email:
            return jsonify({"error": "email é obrigatório", "status": "error"}), 400

        generic_msg = "Se o e-mail estiver cadastrado, você receberá as instruções para redefinir sua senha."

        user = db_manager.get_user_by_email(email)
        if not user or not user.get("is_active"):
            return jsonify({"status": "success", "message": generic_msg}), 200

        db_manager.invalidate_reset_tokens_for_user(user["id"])

        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.utcnow() + timedelta(seconds=PASSWORD_RESET_TTL_SECONDS)

        ok = db_manager.store_password_reset_token(user["id"], token_hash, expires_at)
        if not ok:
            logger.error(f"Falha ao salvar token de reset para {email}")
            return jsonify({"status": "success", "message": generic_msg}), 200

        ttl_minutes = PASSWORD_RESET_TTL_SECONDS // 60
        email_sent = send_password_reset_email(
            to_email=user["email"],
            user_name=user.get("full_name") or "",
            reset_token=raw_token,
            frontend_url=FRONTEND_URL,
            ttl_minutes=ttl_minutes,
        )

        if not email_sent:
            logger.error(f"Falha ao enviar e-mail de reset para {email}")

        return jsonify({"status": "success", "message": generic_msg}), 200
    except Exception as e:
        logger.error(f"❌ Erro no reset-password request: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Erro interno do servidor", "status": "error"}), 500


@app.route("/auth/reset-password/confirm", methods=["POST"])
def auth_reset_password_confirm():
    """
    Redefine a senha usando um token de reset válido.
    Público — não exige autenticação.
    """
    try:
        if not db_manager.enabled:
            return jsonify({"error": "Banco de dados não está habilitado", "status": "error"}), 503

        data = request.get_json() or {}
        token = data.get("token") or ""
        new_password = data.get("new_password") or ""

        if not token or not new_password:
            return jsonify({"error": "token e new_password são obrigatórios", "status": "error"}), 400

        if len(new_password) < 8:
            return jsonify({"error": "A senha deve ter pelo menos 8 caracteres", "status": "error"}), 400

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        stored = db_manager.get_valid_reset_token(token_hash)
        if not stored:
            return jsonify({"error": "Token inválido ou expirado", "status": "error"}), 401

        user = db_manager.get_user_by_id(stored["user_id"])
        if not user or not user.get("is_active"):
            return jsonify({"error": "Usuário inválido", "status": "error"}), 401

        new_hash = generate_password_hash(new_password)
        ok = db_manager.update_user_password(user["id"], new_hash)
        if not ok:
            return jsonify({"error": "Falha ao atualizar a senha", "status": "error"}), 500

        db_manager.mark_reset_token_used(token_hash)
        db_manager.invalidate_reset_tokens_for_user(user["id"])

        return jsonify({"status": "success", "message": "Senha redefinida com sucesso"}), 200
    except Exception as e:
        logger.error(f"❌ Erro no reset-password confirm: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Erro interno do servidor", "status": "error"}), 500


@app.route("/auth/change-password", methods=["POST"])
@jwt_required
def auth_change_password():
    """
    Permite ao usuário autenticado trocar a própria senha.
    Requer a senha atual para confirmação.
    """
    try:
        if not db_manager.enabled:
            return jsonify({"error": "Banco de dados não está habilitado", "status": "error"}), 503

        user_id = request.current_user.get("sub")
        if not user_id:
            return jsonify({"error": "Token inválido", "status": "error"}), 401

        data = request.get_json() or {}
        current_password = data.get("current_password") or ""
        new_password = data.get("new_password") or ""

        if not current_password or not new_password:
            return jsonify({"error": "current_password e new_password são obrigatórios", "status": "error"}), 400

        if len(new_password) < 8:
            return jsonify({"error": "A nova senha deve ter pelo menos 8 caracteres", "status": "error"}), 400

        user = db_manager.get_user_by_id(user_id)
        if not user or not user.get("is_active"):
            return jsonify({"error": "Usuário inválido", "status": "error"}), 401

        full_user = db_manager.get_user_by_email(user["email"])
        if not full_user or not check_password_hash(full_user["password_hash"], current_password):
            return jsonify({"error": "Senha atual incorreta", "status": "error"}), 401

        new_hash = generate_password_hash(new_password)
        ok = db_manager.update_user_password(user_id, new_hash)
        if not ok:
            return jsonify({"error": "Falha ao atualizar a senha", "status": "error"}), 500

        return jsonify({"status": "success", "message": "Senha alterada com sucesso"}), 200
    except Exception as e:
        logger.error(f"❌ Erro no change-password: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Erro interno do servidor", "status": "error"}), 500


# ==================== CONVERSATIONS ENDPOINTS ====================

@app.route('/conversations/<conversation_id>/messages', methods=['GET'])
@jwt_required
def get_conversation_messages(conversation_id):
    """
    Lista mensagens de uma conversa específica
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar que conversation_id é um número inteiro válido
        try:
            int(conversation_id)
        except (ValueError, TypeError):
            return jsonify({
                "error": "conversation_id deve ser um número inteiro válido",
                "status": "error"
            }), 400
        
        # Parâmetros da query
        limit = request.args.get('limit', 50, type=int)
        if limit > 100:
            limit = 100  # Máximo de 100 mensagens por vez
        
        # Verificar se a conversa pertence à conta do usuário
        def _check_conversation_ownership(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT c.id, c.contact_id, ct.account_id
                FROM conversation c
                LEFT JOIN contacts ct ON c.contact_id = ct.id
                WHERE c.id = %s
            """
            cursor.execute(query, (conversation_id,))
            result = cursor.fetchone()
            cursor.close()
            return result
        
        conversation = db_manager._execute_with_fresh_connection(_check_conversation_ownership)
        
        if not conversation:
            return jsonify({
                "error": "Conversa não encontrada",
                "status": "error"
            }), 404
        
        # Verificar se a conversa pertence à conta do usuário
        if conversation['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - conversa não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Buscar mensagens da conversa com campos completos
        def _get_full_messages(connection):
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
                    cm.user_id,
                    b.name as bot_name,
                    b.agent_name as bot_agent_name
                FROM conversation_message cm
                LEFT JOIN conversation c ON cm.conversation_id = c.id
                LEFT JOIN channels ch ON c.channel_id = ch.id
                LEFT JOIN bots b ON ch.bot_id = b.id
                WHERE cm.conversation_id = %s
                ORDER BY cm.timestamp ASC
                LIMIT %s
            """
            cursor.execute(query, (conversation_id, limit))
            rows = cursor.fetchall()
            cursor.close()
            return rows

        raw_messages = db_manager._execute_with_fresh_connection(_get_full_messages) or []

        formatted_messages = []
        for msg in raw_messages:
            formatted_msg = {
                "id": str(msg.get("id")),
                "conversation_id": str(msg.get("conversation_id")),
                "content": msg.get("message_text", ""),
                "sender": msg.get("sender", ""),
                "message_type": msg.get("message_type", "text"),
                "timestamp": msg["timestamp"].isoformat() if msg.get("timestamp") else None,
                "tokens": msg.get("tokens"),
                "user_id": str(msg.get("user_id")) if msg.get("user_id") else None,
            }
            if msg.get("bot_name"):
                formatted_msg["metadata"] = {
                    "bot": {
                        "name": msg.get("bot_name"),
                        "agent_name": msg.get("bot_agent_name")
                    }
                }
            formatted_messages.append(formatted_msg)

        logger.info(f"✅ Usuário {request.current_user.get('sub')} acessou {len(formatted_messages)} mensagens da conversa {conversation_id}")
        
        return jsonify({
            "status": "success",
            "conversation_id": conversation_id,
            "messages": formatted_messages,
            "total": len(formatted_messages),
            "limit": limit
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_conversation_messages: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/conversations/<conversation_id>/status', methods=['PUT'])
@jwt_required
def update_conversation_status(conversation_id):
    """
    Atualiza o status_attendance de uma conversa (bot/human)
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar formato do ID da conversa (deve ser um número inteiro)
        try:
            conversation_id = int(conversation_id)
        except ValueError:
            return jsonify({
                "error": "conversation_id deve ser um número inteiro válido",
                "status": "error"
            }), 400
        
        # Obter dados do request
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Validar status_attendance
        status_attendance = data.get('status_attendance')
        if not status_attendance:
            return jsonify({
                "error": "Campo 'status_attendance' é obrigatório",
                "status": "error"
            }), 400
        
        if status_attendance not in ['bot', 'human']:
            return jsonify({
                "error": "status_attendance deve ser 'bot' ou 'human'",
                "status": "error"
            }), 400
        
        # Verificar se a conversa existe e pertence à conta
        conversation = db_manager.get_conversation_by_id(conversation_id)
        if not conversation:
            return jsonify({
                "error": "Conversa não encontrada",
                "status": "error"
            }), 404
        
        # Verificar se a conversa pertence à conta do usuário
        contact = db_manager.get_contact_by_id(conversation['contact_id'])
        if not contact or contact['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - conversa não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Atualizar status_attendance
        success = db_manager.update_conversation_status_attendance(conversation_id, status_attendance)
        if not success:
            return jsonify({
                "error": "Falha ao atualizar status da conversa",
                "status": "error"
            }), 500
        
        # Buscar conversa atualizada
        updated_conversation = db_manager.get_conversation_by_id(conversation_id)
        
        return jsonify({
            "conversation": {
                "id": updated_conversation['id'],
                "status": updated_conversation['status'],
                "status_attendance": updated_conversation['status_attendance'],
                "started_at": updated_conversation['started_at'].isoformat() if updated_conversation['started_at'] else None,
                "ended_at": updated_conversation['ended_at'].isoformat() if updated_conversation['ended_at'] else None
            },
            "message": f"Status alterado para {status_attendance} com sucesso",
            "status": "success"
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint update_conversation_status: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/conversations/<conversation_id>/send-message', methods=['POST'])
@jwt_required
def send_message_to_conversation(conversation_id):
    """Envia mensagem de agente humano para uma conversa e para o canal (WhatsApp)"""
    try:
        # Validar conversation_id como int
        try:
            conversation_id = int(conversation_id)
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "conversation_id deve ser um número inteiro"
            }), 400
        
        # Extrair payload
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "Body JSON é obrigatório"
            }), 400
        
        message_content = data.get('content', '').strip()
        user_id = data.get('user_id')  # ID do usuário que está enviando
        sender = data.get('sender')  # Sender do frontend (human/agent)
        
        if not message_content:
            return jsonify({
                "success": False,
                "error": "Campo 'content' é obrigatório e não pode estar vazio"
            }), 400
        
        if not sender:
            return jsonify({
                "success": False,
                "error": "Campo 'sender' é obrigatório"
            }), 400
        
        # Buscar account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "success": False,
                "error": "account_id não encontrado no token"
            }), 401
        
        # Verificar se a conversa existe e pertence ao account
        conversation = db_manager.get_conversation_by_id(conversation_id)
        if not conversation:
            return jsonify({
                "success": False,
                "error": "Conversa não encontrada"
            }), 404
        
        # Verificar propriedade da conversa
        contact = db_manager.get_contact_by_id(conversation['contact_id'])
        if not contact or contact['account_id'] != account_id:
            return jsonify({
                "success": False,
                "error": "Conversa não pertence ao account do usuário"
            }), 403
        
        # Salvar mensagem no banco primeiro
        message_id = db_manager.insert_conversation_message(
            conversation_id=conversation_id,
            message_text=message_content,
            sender=sender,  # Usar sender do frontend (human/agent)
            message_type='text',
            timestamp=datetime.now(),
            user_id=user_id,
            notify_websocket=True  # Notificar outros clientes WebSocket
        )
        
        if not message_id:
            return jsonify({
                "success": False,
                "error": "Falha ao salvar mensagem no banco de dados"
            }), 500
        
        # Determinar o nome para o prefixo baseado no sender
        prefix_name = None
        try:
            if sender == "human" and user_id:
                # Se é humano, buscar nome do usuário pelo user_id
                user_name = get_user_name_by_id(user_id)
                prefix_name = user_name if user_name else "Atendente"
                logger.info(f"💬 Mensagem de humano - user_id: {user_id}, nome: {prefix_name}")
                
            elif sender == "agent":
                # Se é agent (bot), buscar agent_name do bot
                if conversation.get('channel_id'):
                    channel = db_manager.get_channel(conversation['channel_id'])
                    if channel and channel.get('bot_id'):
                        bot = db_manager.get_bot(channel['bot_id'])
                        if bot and bot.get('agent_name'):
                            prefix_name = bot['agent_name']
                logger.info(f"🤖 Mensagem de bot - agent_name: {prefix_name}")
                
        except Exception as e:
            logger.warning(f"⚠️ Erro ao buscar nome para prefixo: {e}")
        
        # Enviar mensagem para o canal (WhatsApp)
        send_success = False
        try:
            from whatsapp_service import whatsapp_service
            
            # Usar o telefone do contato para envio
            contact_phone = contact.get('whatsapp_phone_number')
            if not contact_phone:
                logger.error(f"❌ Contato {contact['id']} não tem número do WhatsApp")
                return jsonify({
                    "success": False,
                    "error": "Contato não tem número do WhatsApp configurado"
                }), 400
            
            # Enviar via WhatsApp com o nome apropriado para o prefixo
            result = whatsapp_service.process_outgoing_message(contact_phone, message_content, prefix_name)
            if result:
                send_success = True
                logger.info(f"✅ Mensagem enviada via WhatsApp para {contact_phone}")
            else:
                logger.error(f"❌ Falha ao enviar mensagem via WhatsApp para {contact_phone}")
        
        except Exception as whatsapp_error:
            logger.error(f"❌ Erro ao enviar mensagem WhatsApp: {whatsapp_error}")
        
        # Retornar resposta
        if send_success:
            return jsonify({
                "success": True,
                "message": "Mensagem enviada com sucesso",
                "data": {
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "sent_to_channel": True,
                    "channel_type": "whatsapp"
                },
                "status": "success"
            }), 200
        else:
            # Mensagem foi salva mas não enviada para o canal
            return jsonify({
                "success": False,
                "error": "Mensagem salva no banco mas falha ao enviar para WhatsApp",
                "data": {
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "sent_to_channel": False
                },
                "status": "error"
            }), 500
    
    except Exception as e:
        logger.error(f"❌ Erro ao enviar mensagem para conversa {conversation_id}: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": "Erro interno do servidor",
            "status": "error"
        }), 500

@app.route('/conversations/<conversation_id>/close', methods=['PUT'])
@jwt_required
def close_conversation(conversation_id):
    """Encerra uma conversa definindo status = 'closed' e ended_at"""
    try:
        # Validar conversation_id como int
        try:
            conversation_id = int(conversation_id)
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "conversation_id deve ser um número inteiro"
            }), 400
        
        # Extrair payload (opcional)
        data = request.get_json() or {}
        user_id = data.get('user_id')  # ID do usuário que está encerrando (para logs)
        
        # Buscar account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "success": False,
                "error": "account_id não encontrado no token"
            }), 401
        
        # Verificar se a conversa existe e pertence ao account
        conversation = db_manager.get_conversation_by_id(conversation_id)
        if not conversation:
            return jsonify({
                "success": False,
                "error": "Conversa não encontrada"
            }), 404
        
        # Verificar se a conversa já está encerrada
        if conversation.get('status') == 'closed':
            return jsonify({
                "success": True,
                "message": "Conversa já está encerrada",
                "data": {
                    "conversation_id": conversation_id,
                    "status": "closed",
                    "already_closed": True,
                    "ended_at": conversation.get('ended_at').isoformat() if conversation.get('ended_at') else None
                },
                "status": "success"
            }), 200
        
        # Verificar propriedade da conversa
        contact = db_manager.get_contact_by_id(conversation['contact_id'])
        if not contact or contact['account_id'] != account_id:
            return jsonify({
                "success": False,
                "error": "Conversa não pertence ao account do usuário"
            }), 403
        
        # Apenas encerrar a conversa - não salvar mensagem
        
        # Encerrar a conversa (status = closed, ended_at = NOW)
        close_success = db_manager.close_conversation(conversation_id)
        
        if not close_success:
            return jsonify({
                "success": False,
                "error": "Falha ao encerrar conversa no banco de dados"
            }), 500
        
        # Buscar conversa atualizada para retornar
        updated_conversation = db_manager.get_conversation_by_id(conversation_id)
        
        # Log de auditoria
        user_email = request.current_user.get('email', 'unknown')
        logger.info(f"🔚 CONVERSA ENCERRADA - ID: {conversation_id}, User: {user_email}, User ID: {user_id or 'N/A'}")
        
        # Retornar sucesso
        return jsonify({
            "success": True,
            "message": "Conversa encerrada com sucesso",
            "data": {
                "conversation_id": conversation_id,
                "status": "closed",
                "ended_at": updated_conversation.get('ended_at').isoformat() if updated_conversation.get('ended_at') else None,
                "closed_by_user_id": user_id
            },
            "status": "success"
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao encerrar conversa {conversation_id}: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": "Erro interno do servidor",
            "status": "error"
        }), 500

# ==================== CHANNELS ENDPOINTS ====================

@app.route('/channels', methods=['GET'])
@jwt_required
def get_channels():
    """
    Lista todos os canais da conta do usuário autenticado
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            logger.warning(f"⚠️ Tentativa de acesso sem account_id válido - usuário: {request.current_user.get('sub')}")
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Log de auditoria detalhado
        user_id = request.current_user.get('sub')
        user_email = request.current_user.get('email', 'unknown')
        logger.info(f"🔍 AUDITORIA: Usuário {user_id} ({user_email}) listando canais da conta {account_id}")
        
        # Parâmetros opcionais
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        
        # Buscar canais da conta (FILTRADOS POR ACCOUNT_ID)
        channels = db_manager.get_channels_by_account(account_id, active_only)
        
        # Log detalhado do resultado
        if channels:
            channel_ids = [ch['id'] for ch in channels]
            logger.info(f"✅ Retornando {len(channels)} canais para conta {account_id}: {channel_ids[:3]}{'...' if len(channel_ids) > 3 else ''}")
            
            # Validação extra: verificar se todos os canais pertencem à conta
            invalid_channels = [ch for ch in channels if ch.get('account_id') != account_id]
            if invalid_channels:
                logger.error(f"🚨 SEGURANÇA: Canais com account_id incorreto detectados: {invalid_channels}")
        else:
            logger.info(f"📭 Nenhum canal encontrado para conta {account_id}")
        
        return jsonify({
            "status": "success",
            "channels": channels,
            "total": len(channels),
            "security_info": {
                "filtered_by_account_id": account_id,
                "user_id": user_id,
                "user_email": user_email,
                "query_timestamp": datetime.now().isoformat()
            },
            "filters": {
                "account_id": account_id,
                "active_only": active_only
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_channels: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/channels', methods=['POST'])
@jwt_required
def create_channel():
    """
    Cria um novo canal de atendimento
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Obter dados do JSON
        data = request.get_json()
        
        # Validação dos dados obrigatórios
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        required_fields = ['id', 'type']
        for field in required_fields:
            if field not in data or data[field] is None:
                return jsonify({
                    "error": f"Campo '{field}' é obrigatório",
                    "status": "error"
                }), 400
        
        # Validar UUID do canal
        try:
            uuid.UUID(data['id'])
        except ValueError:
            return jsonify({
                "error": "Campo 'id' deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Validar tipo de canal
        valid_types = ['whatsapp', 'instagram', 'chat_widget']
        if data['type'] not in valid_types:
            return jsonify({
                "error": f"Tipo de canal inválido. Tipos válidos: {', '.join(valid_types)}",
                "status": "error"
            }), 400
        
        # Validar bot_id se fornecido
        bot_id = data.get('bot_id')
        if bot_id:
            try:
                uuid.UUID(bot_id)
            except ValueError:
                return jsonify({
                    "error": "Campo 'bot_id' deve ser um UUID válido",
                    "status": "error"
                }), 400
        
        # Verificar se o canal já existe
        existing_channel = db_manager.get_channel(data['id'])
        if existing_channel:
            return jsonify({
                "error": "Canal com este ID já existe",
                "status": "error",
                "existing_channel": existing_channel
            }), 409
        
        # Inserir novo canal
        success = db_manager.insert_channel(
            channel_id=data['id'],
            account_id=account_id,
            channel_type=data['type'],
            name=data.get('name'),
            bot_id=bot_id,
            active=data.get('active', True),
            phone_number=data.get('phone_number'),
            client_id=data.get('client_id'),
            client_secret=data.get('client_secret'),
            access_token=data.get('access_token')
        )
        
        if success:
            # Buscar o canal criado para retornar
            new_channel = db_manager.get_channel(data['id'])
            
            logger.info(f"✅ Novo canal criado: ID={data['id']}, Tipo={data['type']}, Conta={account_id}")
            
            return jsonify({
                "message": "Canal criado com sucesso",
                "status": "success",
                "channel": new_channel
            }), 201
        else:
            logger.error(f"❌ Falha ao criar canal: ID={data['id']}")
            return jsonify({
                "error": "Falha ao criar canal no banco de dados",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint create_channel: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/channels/<channel_id>', methods=['GET'])
@jwt_required
def get_channel_by_id(channel_id):
    """
    Busca um canal específico pelo ID
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar formato do UUID
        try:
            uuid.UUID(channel_id)
        except ValueError:
            return jsonify({
                "error": "ID deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Buscar canal
        channel = db_manager.get_channel(channel_id)
        
        if not channel:
            return jsonify({
                "error": "Canal não encontrado",
                "status": "error"
            }), 404
        
        # Verificar se o canal pertence à conta do usuário
        if channel['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - canal não pertence à sua conta",
                "status": "error"
            }), 403
        
        logger.info(f"✅ Usuário {request.current_user.get('sub')} acessou canal {channel_id}")
        
        return jsonify({
            "status": "success",
            "channel": channel
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_channel: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/channels/<channel_id>', methods=['PUT'])
@jwt_required
def update_channel(channel_id):
    """
    Atualiza um canal existente
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar formato do UUID
        try:
            uuid.UUID(channel_id)
        except ValueError:
            return jsonify({
                "error": "ID deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o canal existe e pertence à conta
        existing_channel = db_manager.get_channel_full(channel_id)
        if not existing_channel:
            return jsonify({
                "error": "Canal não encontrado",
                "status": "error"
            }), 404
        
        if existing_channel['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - canal não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Obter dados do JSON
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Validar campos opcionais
        update_params = {}
        
        if 'name' in data:
            update_params['name'] = data['name']
        
        if 'bot_id' in data:
            if data['bot_id'] is not None:
                try:
                    uuid.UUID(data['bot_id'])
                except ValueError:
                    return jsonify({
                        "error": "Campo 'bot_id' deve ser um UUID válido",
                        "status": "error"
                    }), 400
            update_params['bot_id'] = data['bot_id']
        
        if 'active' in data:
            if not isinstance(data['active'], bool):
                return jsonify({
                    "error": "Campo 'active' deve ser um booleano",
                    "status": "error"
                }), 400
            update_params['active'] = data['active']
        
        if 'type' in data:
            if data['type'] is not None:
                valid_types = ['whatsapp', 'instagram', 'chat_widget']
                if data['type'] not in valid_types:
                    return jsonify({
                        "error": f"Tipo de canal inválido. Tipos válidos: {', '.join(valid_types)}",
                        "status": "error"
                    }), 400
            update_params['channel_type'] = data['type']
        
        if 'phone_number' in data:
            update_params['phone_number'] = data['phone_number']
        
        if 'client_id' in data:
            update_params['client_id'] = data['client_id']
        
        if 'client_secret' in data:
            update_params['client_secret'] = data['client_secret']
        
        if 'access_token' in data:
            update_params['access_token'] = data['access_token']
        
        if not update_params:
            return jsonify({
                "error": "Nenhum campo válido fornecido para atualização",
                "status": "error"
            }), 400
        
        # Atualizar canal
        success = db_manager.update_channel(channel_id, account_id, **update_params)
        
        if success:
            # Buscar canal atualizado
            updated_channel = db_manager.get_channel(channel_id)
            
            logger.info(f"✅ Canal atualizado: ID={channel_id}, Campos={list(update_params.keys())}")
            
            return jsonify({
                "message": "Canal atualizado com sucesso",
                "status": "success",
                "channel": updated_channel,
                "updated_fields": list(update_params.keys())
            }), 200
        else:
            return jsonify({
                "error": "Falha ao atualizar canal",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint update_channel: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/channels/<channel_id>', methods=['DELETE'])
@jwt_required
def delete_channel(channel_id):
    """
    Deleta um canal permanentemente do banco de dados
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar formato do UUID
        try:
            uuid.UUID(channel_id)
        except ValueError:
            return jsonify({
                "error": "ID deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o canal existe e pertence à conta
        existing_channel = db_manager.get_channel_full(channel_id)
        if not existing_channel:
            return jsonify({
                "error": "Canal não encontrado",
                "status": "error"
            }), 404
        
        if existing_channel['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - canal não pertence à sua conta",
                "status": "error"
            }), 403
        
        # DELETE agora exclui permanentemente o registro
        success = db_manager.hard_delete_channel(channel_id, account_id)
        action = "deletado permanentemente"
        
        if success:
            logger.info(f"✅ Canal {action}: ID={channel_id}")
            
            return jsonify({
                "message": f"Canal {action} com sucesso",
                "status": "success",
                "channel_id": channel_id,
                "action": action
            }), 200
        else:
            return jsonify({
                "error": f"Falha ao {action.replace('o', 'ar')} canal",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint delete_channel: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

# ==================== BOTS ENDPOINTS ====================

@app.route('/bots', methods=['GET'])
@jwt_required
def get_bots():
    """
    Lista todos os bots da conta do usuário autenticado
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            logger.warning(f"⚠️ Tentativa de acesso BOTS sem account_id válido - usuário: {request.current_user.get('sub')}")
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Log de auditoria detalhado
        user_id = request.current_user.get('sub')
        user_email = request.current_user.get('email', 'unknown')
        logger.info(f"🔍 AUDITORIA BOTS: Usuário {user_id} ({user_email}) listando bots da conta {account_id}")
        
        # Buscar bots da conta (FILTRADOS POR ACCOUNT_ID)
        bots = db_manager.get_bots_by_account(account_id)
        
        # Log detalhado do resultado
        if bots:
            bot_ids = [bot['id'] for bot in bots]
            logger.info(f"✅ Retornando {len(bots)} bots para conta {account_id}: {bot_ids[:3]}{'...' if len(bot_ids) > 3 else ''}")
            
            # Validação extra: verificar se todos os bots pertencem à conta
            invalid_bots = [bot for bot in bots if bot.get('account_id') != account_id]
            if invalid_bots:
                logger.error(f"🚨 SEGURANÇA BOTS: Bots com account_id incorreto detectados: {invalid_bots}")
        else:
            logger.info(f"📭 Nenhum bot encontrado para conta {account_id}")
        
        return jsonify({
            "status": "success",
            "bots": bots,
            "total": len(bots),
            "security_info": {
                "filtered_by_account_id": account_id,
                "user_id": user_id,
                "user_email": user_email,
                "query_timestamp": datetime.now().isoformat()
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_bots: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots', methods=['POST'])
@jwt_required
def create_bot():
    """
    Cria um novo bot
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Obter dados do JSON
        data = request.get_json()
        
        # Validação dos dados obrigatórios
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        required_fields = ['id', 'name', 'system_prompt']
        for field in required_fields:
            if field not in data or data[field] is None:
                return jsonify({
                    "error": f"Campo '{field}' é obrigatório",
                    "status": "error"
                }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(data['id'])
        except ValueError:
            return jsonify({
                "error": "Campo 'id' deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Validar integration_id se fornecido
        integration_id = data.get('integration_id')
        if integration_id is not None:
            try:
                uuid.UUID(integration_id)
            except ValueError:
                return jsonify({
                    "error": "Campo 'integration_id' deve ser um UUID válido",
                    "status": "error"
                }), 400
        
        # Validar tamanho dos campos
        if len(data['name']) > 100:
            return jsonify({
                "error": "Campo 'name' deve ter no máximo 100 caracteres",
                "status": "error"
            }), 400
        
        if len(data['system_prompt']) > 10000:  # Limite razoável para TEXT
            return jsonify({
                "error": "Campo 'system_prompt' deve ter no máximo 10000 caracteres",
                "status": "error"
            }), 400
        
        # Validar agent_name se fornecido
        agent_name = data.get('agent_name')
        if agent_name is not None and len(agent_name) > 100:
            return jsonify({
                "error": "Campo 'agent_name' deve ter no máximo 100 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se o bot já existe
        existing_bot = db_manager.get_bot(data['id'])
        if existing_bot:
            return jsonify({
                "error": "Bot com este ID já existe",
                "status": "error",
                "existing_bot": {
                    "id": existing_bot['id'],
                    "name": existing_bot['name']
                }
            }), 409
        
        # Inserir novo bot
        success = db_manager.insert_bot(
            bot_id=data['id'],
            account_id=account_id,  # Usar account_id do token JWT
            name=data['name'],
            system_prompt=data['system_prompt'],
            integration_id=integration_id,
            agent_name=agent_name
        )
        
        if success:
            # Buscar o bot criado para retornar
            new_bot = db_manager.get_bot(data['id'])
            
            logger.info(f"✅ Novo bot criado: ID={data['id']}, Nome={data['name']}, Integration={integration_id}, Conta={account_id}")
            
            return jsonify({
                "message": "Bot criado com sucesso",
                "status": "success",
                "bot": new_bot
            }), 201
        else:
            logger.error(f"❌ Falha ao criar bot: ID={data['id']}")
            return jsonify({
                "error": "Falha ao criar bot no banco de dados",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint create_bot: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

# ==================== WEBSOCKET ENDPOINTS ====================

@app.route('/websocket/info', methods=['GET'])
def get_websocket_info():
    """Retorna informações de conexão WebSocket"""
    try:
        # Configuração para frontend conectar
        # URL correta baseada no ambiente
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            # Em produção no Kubernetes, usar o domínio configurado
            websocket_url = "wss://pluggyapi.pluggerbi.com/ws"  # HTTPS WebSocket
        else:
            # Em desenvolvimento local
            websocket_url = f"ws://localhost:8765"
            
        websocket_config = {
            "url": websocket_url,
            "authentication_required": True,
            "supported_events": [
                "new_message",
                "connection_confirmed",
                "subscription_updated",
                "messages_response"
            ],
            "client_events": [
                "authenticate",
                "subscribe_conversations", 
                "get_messages",
                "ping"
            ]
        }
        
        return jsonify({
            "status": "success",
            "data": websocket_config
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter info WebSocket: {e}")
        return jsonify({
            "error": "Erro interno do servidor", 
            "status": "error"
        }), 500

@app.route('/websocket/stats', methods=['GET'])
@jwt_required
def get_websocket_stats():
    """Retorna estatísticas das conexões WebSocket"""
    try:
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Importar servidor WebSocket
        from websocket_server import websocket_server
        
        stats = websocket_server.get_stats()
        
        # Filtrar apenas clientes da conta atual
        account_stats = {
            "connected_clients": 0,
            "clients": []
        }
        
        for client in stats["clients"]:
            if client["account_id"] == account_id:
                account_stats["connected_clients"] += 1
                account_stats["clients"].append(client)
        
        return jsonify({
            "status": "success",
            "data": account_stats
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter estatísticas WebSocket: {e}")
        return jsonify({
            "error": "Erro interno do servidor",
            "status": "error"
        }), 500

@app.route('/websocket/test', methods=['POST'])
@jwt_required
def test_websocket_notification():
    """Testa notificação WebSocket (desenvolvimento)"""
    try:
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        data = request.get_json()
        
        conversation_id = data.get('conversation_id')
        test_message = data.get('message', 'Mensagem de teste WebSocket')
        
        if not conversation_id:
            return jsonify({
                "error": "conversation_id é obrigatório",
                "status": "error"
            }), 400
        
        # Verificar se conversa pertence à conta
        conversation = db_manager.get_conversation_by_id(conversation_id)
        if not conversation:
            return jsonify({
                "error": "Conversa não encontrada",
                "status": "error"
            }), 404
        
        # Enviar notificação de teste
        from websocket_notifier import notify_message_saved
        
        test_data = {
            "id": "test_" + str(int(time.time())),
            "conversation_id": conversation_id,
            "message_text": test_message,
            "sender": "system",
            "message_type": "test",
            "timestamp": datetime.now().isoformat(),
            "tokens": 0,
            "contact": {
                "id": conversation.get('contact_id', 'unknown'),
                "name": "Teste WebSocket",
                "phone": "test"
            }
        }
        
        notify_message_saved(conversation_id, "test_id", test_message, "system", "test", 0)
        
        return jsonify({
            "status": "success",
            "message": "Notificação de teste enviada",
            "data": test_data
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro ao testar WebSocket: {e}")
        return jsonify({
            "error": "Erro interno do servidor",
            "status": "error"
        }), 500

# ==================== BOTS ENDPOINTS ====================

@app.route('/bots/<bot_id>', methods=['GET'])
@jwt_required
def get_bot_by_id(bot_id):
    """
    Busca um bot específico pelo ID
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar formato do UUID
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "ID deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Buscar bot
        bot = db_manager.get_bot(bot_id)
        
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        # Verificar se o bot pertence à conta do usuário
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        logger.info(f"✅ Usuário {request.current_user.get('sub')} acessou bot {bot_id}")
        
        return jsonify({
            "status": "success",
            "bot": bot
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_bot: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>', methods=['PUT'])
@jwt_required
def update_bot(bot_id):
    """
    Atualiza um bot existente
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar formato do UUID
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "ID deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        existing_bot = db_manager.get_bot(bot_id)
        if not existing_bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if existing_bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Obter dados do JSON
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Validar campos opcionais
        update_params = {}
        
        if 'name' in data:
            if not data['name'] or len(data['name']) > 100:
                return jsonify({
                    "error": "Campo 'name' deve ter entre 1 e 100 caracteres",
                    "status": "error"
                }), 400
            update_params['name'] = data['name']
        
        if 'integration_id' in data:
            if data['integration_id'] is not None:
                try:
                    uuid.UUID(data['integration_id'])
                except ValueError:
                    return jsonify({
                        "error": "Campo 'integration_id' deve ser um UUID válido",
                        "status": "error"
                    }), 400
            update_params['integration_id'] = data['integration_id']
        
        if 'system_prompt' in data:
            if not data['system_prompt'] or len(data['system_prompt']) > 10000:
                return jsonify({
                    "error": "Campo 'system_prompt' deve ter entre 1 e 10000 caracteres",
                    "status": "error"
                }), 400
            update_params['system_prompt'] = data['system_prompt']
        
        if 'agent_name' in data:
            if data['agent_name'] is not None and len(data['agent_name']) > 100:
                return jsonify({
                    "error": "Campo 'agent_name' deve ter no máximo 100 caracteres",
                    "status": "error"
                }), 400
            update_params['agent_name'] = data['agent_name']
        
        if not update_params:
            return jsonify({
                "error": "Nenhum campo válido fornecido para atualização",
                "status": "error"
            }), 400
        
        # Atualizar bot
        success = db_manager.update_bot(bot_id, account_id, **update_params)
        
        if success:
            # Buscar bot atualizado
            updated_bot = db_manager.get_bot(bot_id)
            
            logger.info(f"✅ Bot atualizado: ID={bot_id}, Campos={list(update_params.keys())}")
            
            return jsonify({
                "message": "Bot atualizado com sucesso",
                "status": "success",
                "bot": updated_bot,
                "updated_fields": list(update_params.keys())
            }), 200
        else:
            return jsonify({
                "error": "Falha ao atualizar bot",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint update_bot: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>', methods=['DELETE'])
@jwt_required
def delete_bot(bot_id):
    """
    Deleta um bot permanentemente do banco de dados
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar formato do UUID
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "ID deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        existing_bot = db_manager.get_bot(bot_id)
        if not existing_bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if existing_bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # DELETE exclui permanentemente o registro
        success = db_manager.delete_bot(bot_id, account_id)
        
        if success:
            logger.info(f"✅ Bot deletado permanentemente: ID={bot_id}")
            
            return jsonify({
                "message": "Bot deletado permanentemente com sucesso",
                "status": "success",
                "bot_id": bot_id,
                "action": "deletado permanentemente"
            }), 200
        else:
            return jsonify({
                "error": "Falha ao deletar bot",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint delete_bot: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/security/audit', methods=['GET'])
@jwt_required
def audit_bots_security():
    """
    Endpoint de auditoria para verificar se a filtragem por account_id está funcionando para bots
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Informações do usuário
        user_id = request.current_user.get('sub')
        user_email = request.current_user.get('email', 'unknown')
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        logger.info(f"🔍 AUDITORIA DE SEGURANÇA BOTS: Usuário {user_id} verificando isolamento da conta {account_id}")
        
        # Buscar bots da conta
        bots = db_manager.get_bots_by_account(account_id)
        
        # Análise de segurança
        analysis = {
            "total_bots_found": len(bots),
            "account_ids_in_results": [],
            "security_violations": [],
            "security_status": "UNKNOWN"
        }
        
        if bots:
            # Verificar todos os account_ids retornados
            account_ids_found = [bot.get('account_id') for bot in bots]
            unique_account_ids = list(set(account_ids_found))
            
            analysis["account_ids_in_results"] = unique_account_ids
            
            # Verificar violações de segurança
            if len(unique_account_ids) > 1:
                analysis["security_violations"].append(f"Múltiplas contas retornadas: {unique_account_ids}")
                analysis["security_status"] = "VIOLATED"
            elif unique_account_ids and unique_account_ids[0] != account_id:
                analysis["security_violations"].append(f"Conta incorreta retornada. Esperado: {account_id}, Encontrado: {unique_account_ids[0]}")
                analysis["security_status"] = "VIOLATED"
            else:
                analysis["security_status"] = "SECURE"
        else:
            analysis["security_status"] = "SECURE"
            analysis["account_ids_in_results"] = []
        
        # Log do resultado da auditoria
        if analysis["security_status"] == "VIOLATED":
            logger.error(f"🚨 AUDITORIA BOTS FALHOU: Violações de segurança detectadas para usuário {user_id}")
        else:
            logger.info(f"✅ AUDITORIA BOTS PASSOU: Segurança OK para usuário {user_id}")
        
        return jsonify({
            "audit_timestamp": datetime.now().isoformat(),
            "resource_type": "bots",
            "user_info": {
                "user_id": user_id,
                "user_email": user_email,
                "account_id": account_id
            },
            "security_analysis": analysis,
            "query_info": {
                "sql_filter": f"WHERE account_id = '{account_id}'",
                "parameter_binding": True,
                "prepared_statement": True
            },
            "bots_summary": [
                {
                    "id": bot.get('id'),
                    "account_id": bot.get('account_id'),
                    "name": bot.get('name'),
                    "type": bot.get('type')
                } for bot in bots
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint de auditoria bots: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

# ==================== BOTS PROMPTS ENDPOINTS ====================

@app.route('/bots/<bot_id>/prompts', methods=['GET'])
@jwt_required
def get_bot_prompts(bot_id):
    """
    Lista todos os prompts de um bot específico
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Buscar prompts do bot
        prompts = db_manager.get_bot_prompts(bot_id)
        
        return jsonify({
            "status": "success",
            "bot_id": bot_id,
            "prompts": prompts,
            "total": len(prompts)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_bot_prompts: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/prompts', methods=['POST'])
@jwt_required
def create_bot_prompt(bot_id):
    """
    Cria um novo prompt para um bot específico
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Obter dados do JSON
        data = request.get_json()
        
        # Validação dos dados obrigatórios
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        required_fields = ['id', 'prompt']
        for field in required_fields:
            if field not in data or data[field] is None:
                return jsonify({
                    "error": f"Campo '{field}' é obrigatório",
                    "status": "error"
                }), 400
        
        # Validar UUID do prompt id
        try:
            uuid.UUID(data['id'])
        except ValueError:
            return jsonify({
                "error": "Campo 'id' deve ser um UUID válido",
                "status": "error"
            }), 400
        
        if len(data['prompt']) > 65535:  # TEXT limit
            return jsonify({
                "error": "Campo 'prompt' é muito longo",
                "status": "error"
            }), 400
        
        if 'description' in data and data['description'] and len(data['description']) > 255:
            return jsonify({
                "error": "Campo 'description' deve ter no máximo 255 caracteres",
                "status": "error"
            }), 400
        
        # Validar rule_display se fornecido
        if 'rule_display' in data and data['rule_display']:
            valid_rules = ['first contact', 'every time', 'email not informed']
            if data['rule_display'] not in valid_rules:
                return jsonify({
                    "error": f"Campo 'rule_display' inválido. Valores válidos: {', '.join(valid_rules)}",
                    "status": "error"
                }), 400
        
        # Verificar se o prompt já existe para este bot
        existing_prompt = db_manager.get_bot_prompt(bot_id, data['id'])
        if existing_prompt:
            return jsonify({
                "error": "Prompt com este ID já existe para este bot",
                "status": "error"
            }), 409
        
        # Inserir novo prompt
        success = db_manager.insert_bot_prompt(
            bot_id=bot_id,
            prompt_id=data['id'],
            prompt=data['prompt'],
            description=data.get('description'),
            rule_display=data.get('rule_display')
        )
        
        if success:
            # Buscar o prompt criado para retornar
            created_prompt = db_manager.get_bot_prompt(bot_id, data['id'])
            return jsonify({
                "message": "Prompt criado com sucesso",
                "status": "success",
                "prompt": created_prompt
            }), 201
        else:
            return jsonify({
                "error": "Falha ao criar prompt",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint create_bot_prompt: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/prompts/<prompt_id>', methods=['PUT'])
@jwt_required
def update_bot_prompt(bot_id, prompt_id):
    """
    Atualiza um prompt específico de um bot
    """
    try:
        logger.info(f"🔄 INICIO update_bot_prompt: bot_id={bot_id}, prompt_id={prompt_id}")
        
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            logger.error("❌ Banco de dados não está habilitado")
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        logger.info("✅ Banco de dados está habilitado")
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        logger.info(f"🔍 account_id obtido do token: {account_id}")
        
        if not account_id:
            logger.error("❌ Token JWT não contém account_id válido")
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
            logger.info(f"✅ bot_id é um UUID válido: {bot_id}")
        except ValueError:
            logger.error(f"❌ bot_id inválido: {bot_id}")
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Validar UUID do prompt_id
        try:
            uuid.UUID(prompt_id)
            logger.info(f"✅ prompt_id é um UUID válido: {prompt_id}")
        except ValueError:
            logger.error(f"❌ prompt_id inválido: {prompt_id}")
            return jsonify({
                "error": "prompt_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        logger.info(f"🔍 Buscando bot no banco: {bot_id}")
        bot = db_manager.get_bot(bot_id)
        
        if not bot:
            logger.error(f"❌ Bot não encontrado: {bot_id}")
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        logger.info(f"✅ Bot encontrado: {bot['id']}, account_id: {bot['account_id']}")
        
        if bot['account_id'] != account_id:
            logger.error(f"❌ Acesso negado - bot account_id: {bot['account_id']}, user account_id: {account_id}")
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        logger.info("✅ Bot pertence à conta do usuário")
        
        # Verificar se o prompt existe
        logger.info(f"🔍 Buscando prompt no banco: bot_id={bot_id}, prompt_id={prompt_id}")
        existing_prompt = db_manager.get_bot_prompt(bot_id, prompt_id)
        
        if not existing_prompt:
            logger.error(f"❌ Prompt não encontrado: {prompt_id}")
            return jsonify({
                "error": "Prompt não encontrado",
                "status": "error"
            }), 404
        
        logger.info(f"✅ Prompt encontrado: {existing_prompt['id']}")
        
        # Obter dados do JSON
        data = request.get_json()
        logger.info(f"📥 Dados recebidos: {data}")
        
        # Validação básica
        if not data:
            logger.error("❌ Dados JSON não fornecidos")
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Validações dos campos opcionais
        update_params = {}
        
        if 'prompt' in data:
            if not data['prompt']:
                return jsonify({
                    "error": "Campo 'prompt' não pode estar vazio",
                    "status": "error"
                }), 400
            if len(data['prompt']) > 65535:
                return jsonify({
                    "error": "Campo 'prompt' é muito longo",
                    "status": "error"
                }), 400
            update_params['prompt'] = data['prompt']
        
        if 'description' in data:
            if data['description'] and len(data['description']) > 255:
                return jsonify({
                    "error": "Campo 'description' deve ter no máximo 255 caracteres",
                    "status": "error"
                }), 400
            update_params['description'] = data['description']
        
        if 'rule_display' in data:
            if data['rule_display']:
                valid_rules = ['first contact', 'every time', 'email not informed']
                if data['rule_display'] not in valid_rules:
                    return jsonify({
                        "error": f"Campo 'rule_display' inválido. Valores válidos: {', '.join(valid_rules)}",
                        "status": "error"
                    }), 400
            update_params['rule_display'] = data['rule_display']
        
        if not update_params:
            logger.error("❌ Nenhum campo válido fornecido para atualização")
            return jsonify({
                "error": "Nenhum campo válido fornecido para atualização",
                "status": "error"
            }), 400
        
        logger.info(f"📝 Parâmetros para atualização: {update_params}")
        
        # Atualizar prompt
        logger.info(f"💾 Chamando db_manager.update_bot_prompt...")
        success = db_manager.update_bot_prompt(
            bot_id=bot_id,
            prompt_id=prompt_id,
            **update_params
        )
        
        logger.info(f"📊 Resultado da atualização: {success}")
        
        if success:
            logger.info("🔍 Buscando prompt atualizado...")
            # Buscar o prompt atualizado
            updated_prompt = db_manager.get_bot_prompt(bot_id, prompt_id)
            logger.info(f"✅ Prompt atualizado com sucesso: {updated_prompt}")
            
            return jsonify({
                "message": "Prompt atualizado com sucesso",
                "status": "success",
                "prompt": updated_prompt,
                "updated_fields": list(update_params.keys())
            }), 200
        else:
            logger.error("❌ db_manager.update_bot_prompt retornou False")
            return jsonify({
                "error": "Falha ao atualizar prompt",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ EXCEÇÃO no endpoint update_bot_prompt: {e}")
        logger.error(f"❌ Tipo da exceção: {type(e).__name__}")
        logger.error(f"❌ Args da exceção: {e.args}")
        import traceback
        logger.error(f"❌ Traceback completo: {traceback.format_exc()}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/prompts/<prompt_id>', methods=['DELETE'])
@jwt_required
def delete_bot_prompt(bot_id, prompt_id):
    """
    Deleta permanentemente um prompt específico de um bot
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Validar UUID do prompt_id
        try:
            uuid.UUID(prompt_id)
        except ValueError:
            return jsonify({
                "error": "prompt_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se o prompt existe
        existing_prompt = db_manager.get_bot_prompt(bot_id, prompt_id)
        if not existing_prompt:
            return jsonify({
                "error": "Prompt não encontrado",
                "status": "error"
            }), 404
        
        # Deletar prompt
        success = db_manager.delete_bot_prompt(bot_id, prompt_id)
        
        if success:
            return jsonify({
                "message": "Prompt deletado permanentemente com sucesso",
                "status": "success",
                "bot_id": bot_id,
                "prompt_id": prompt_id,
                "action": "deletado permanentemente"
            }), 200
        else:
            return jsonify({
                "error": "Falha ao deletar prompt",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint delete_bot_prompt: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

# ==================== BOTS PROMPTS FUNCTIONS ENDPOINTS ====================

@app.route('/bots/<bot_id>/prompts/<prompt_id>/functions', methods=['GET'])
@jwt_required
def get_prompt_functions(bot_id, prompt_id):
    """
    Lista todas as funções associadas a um prompt específico
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUIDs
        try:
            uuid.UUID(bot_id)
            uuid.UUID(prompt_id)
        except ValueError:
            return jsonify({
                "error": "bot_id e prompt_id devem ser UUIDs válidos",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se o prompt existe
        existing_prompt = db_manager.get_bot_prompt(bot_id, prompt_id)
        if not existing_prompt:
            return jsonify({
                "error": "Prompt não encontrado",
                "status": "error"
            }), 404
        
        # Buscar funções do prompt
        functions = db_manager.get_prompt_functions(account_id, prompt_id)
        
        return jsonify({
            "status": "success",
            "bot_id": bot_id,
            "prompt_id": prompt_id,
            "functions": functions,
            "total": len(functions)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_prompt_functions: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/prompts/<prompt_id>/functions', methods=['POST'])
@jwt_required
def create_prompt_function(bot_id, prompt_id):
    """
    Associa uma função a um prompt específico
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUIDs
        try:
            uuid.UUID(bot_id)
            uuid.UUID(prompt_id)
        except ValueError:
            return jsonify({
                "error": "bot_id e prompt_id devem ser UUIDs válidos",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se o prompt existe
        existing_prompt = db_manager.get_bot_prompt(bot_id, prompt_id)
        if not existing_prompt:
            return jsonify({
                "error": "Prompt não encontrado",
                "status": "error"
            }), 404
        
        # Obter dados do JSON
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Validar campo obrigatório
        if 'function_id' not in data or not data['function_id']:
            return jsonify({
                "error": "Campo 'function_id' é obrigatório",
                "status": "error"
            }), 400
        
        function_id = data['function_id']
        
        # Validar tamanho do function_id
        if len(function_id) > 150:
            return jsonify({
                "error": "Campo 'function_id' deve ter no máximo 150 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se a função existe para este bot
        existing_function = db_manager.get_bot_function(bot_id, function_id)
        if not existing_function:
            return jsonify({
                "error": "Função não encontrada para este bot",
                "status": "error"
            }), 404
        
        # Verificar se a associação já existe
        exists = db_manager.check_prompt_function_exists(account_id, prompt_id, function_id)
        if exists:
            return jsonify({
                "error": "Associação entre prompt e função já existe",
                "status": "error"
            }), 409
        
        # Criar associação
        success = db_manager.insert_prompt_function(account_id, bot_id, prompt_id, function_id)
        
        if success:
            return jsonify({
                "message": "Função associada ao prompt com sucesso",
                "status": "success",
                "bot_id": bot_id,
                "prompt_id": prompt_id,
                "function_id": function_id
            }), 201
        else:
            return jsonify({
                "error": "Falha ao associar função ao prompt",
                "status": "error"
            }), 500
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint create_prompt_function: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/prompts/<prompt_id>/functions/<function_id>', methods=['DELETE'])
@jwt_required
def delete_prompt_function(bot_id, prompt_id, function_id):
    """
    Remove uma função específica de um prompt
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUIDs
        try:
            uuid.UUID(bot_id)
            uuid.UUID(prompt_id)
        except ValueError:
            return jsonify({
                "error": "bot_id e prompt_id devem ser UUIDs válidos",
                "status": "error"
            }), 400
        
        # Validar function_id (não é UUID, mas string)
        if len(function_id) > 150:
            return jsonify({
                "error": "function_id deve ter no máximo 150 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se o prompt existe
        existing_prompt = db_manager.get_bot_prompt(bot_id, prompt_id)
        if not existing_prompt:
            return jsonify({
                "error": "Prompt não encontrado",
                "status": "error"
            }), 404
        
        # Verificar se a associação existe
        exists = db_manager.check_prompt_function_exists(account_id, prompt_id, function_id)
        if not exists:
            return jsonify({
                "error": "Associação entre prompt e função não encontrada",
                "status": "error"
            }), 404
        
        # Remover associação
        success = db_manager.delete_prompt_function(account_id, prompt_id, function_id)
        
        if success:
            return jsonify({
                "message": "Função removida do prompt com sucesso",
                "status": "success",
                "bot_id": bot_id,
                "prompt_id": prompt_id,
                "function_id": function_id
            }), 200
        else:
            return jsonify({
                "error": "Falha ao remover função do prompt",
                "status": "error"
            }), 500
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint delete_prompt_function: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

# ==================== BOT LINKED FUNCTIONS ENDPOINTS ====================

@app.route('/bots/<bot_id>/linked-functions', methods=['GET'])
@jwt_required
def get_bot_linked_functions(bot_id):
    """
    Lista todas as funções associadas diretamente a um bot
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Buscar funções associadas ao bot
        functions = db_manager.get_bot_function_associations(account_id, bot_id)
        
        return jsonify({
            "status": "success",
            "bot_id": bot_id,
            "linked_functions": functions,
            "total": len(functions)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_bot_linked_functions: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/linked-functions', methods=['POST'])
@jwt_required
def create_bot_linked_function(bot_id):
    """
    Associa uma função diretamente a um bot
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Obter dados do JSON
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Validar campo obrigatório
        if 'function_id' not in data or not data['function_id']:
            return jsonify({
                "error": "Campo 'function_id' é obrigatório",
                "status": "error"
            }), 400
        
        function_id = data['function_id']
        
        # Validar tamanho do function_id
        if len(function_id) > 150:
            return jsonify({
                "error": "Campo 'function_id' deve ter no máximo 150 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se a função existe para este bot
        existing_function = db_manager.get_bot_function(bot_id, function_id)
        if not existing_function:
            return jsonify({
                "error": "Função não encontrada para este bot",
                "status": "error"
            }), 404
        
        # Verificar se a associação já existe
        exists = db_manager.check_bot_function_association_exists(account_id, bot_id, function_id)
        if exists:
            return jsonify({
                "error": "Associação entre bot e função já existe",
                "status": "error"
            }), 409
        
        # Criar associação
        success = db_manager.insert_bot_function_association(account_id, bot_id, function_id)
        
        if success:
            return jsonify({
                "message": "Função associada ao bot com sucesso",
                "status": "success",
                "bot_id": bot_id,
                "function_id": function_id
            }), 201
        else:
            return jsonify({
                "error": "Falha ao associar função ao bot",
                "status": "error"
            }), 500
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint create_bot_linked_function: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/linked-functions/<function_id>', methods=['DELETE'])
@jwt_required
def delete_bot_linked_function(bot_id, function_id):
    """
    Remove uma função específica de um bot
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Validar function_id (não é UUID, mas string)
        if len(function_id) > 150:
            return jsonify({
                "error": "function_id deve ter no máximo 150 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se a associação existe
        exists = db_manager.check_bot_function_association_exists(account_id, bot_id, function_id)
        if not exists:
            return jsonify({
                "error": "Associação entre bot e função não encontrada",
                "status": "error"
            }), 404
        
        # Remover associação
        success = db_manager.delete_bot_function_association(account_id, bot_id, function_id)
        
        if success:
            return jsonify({
                "message": "Função removida do bot com sucesso",
                "status": "success",
                "bot_id": bot_id,
                "function_id": function_id
            }), 200
        else:
            return jsonify({
                "error": "Falha ao remover função do bot",
                "status": "error"
            }), 500
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint delete_bot_linked_function: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

# ==================== BOTS FUNCTIONS ENDPOINTS ====================

@app.route('/bots/<bot_id>/functions', methods=['GET'])
@jwt_required
def get_bot_functions(bot_id):
    """
    Lista todas as funções de um bot específico
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Buscar funções do bot
        functions = db_manager.get_bot_functions(bot_id)
        
        return jsonify({
            "status": "success",
            "bot_id": bot_id,
            "functions": functions,
            "total": len(functions)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_bot_functions: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/functions/used', methods=['GET'])
@jwt_required
def get_bot_functions_with_usage(bot_id):
    """
    Lista todas as funções de um bot específico mostrando como estão sendo usadas
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Buscar funções do bot com informação de uso
        functions = db_manager.get_bot_functions_with_usage(bot_id)
        
        return jsonify({
            "status": "success",
            "bot_id": bot_id,
            "functions": functions,
            "total": len(functions)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_bot_functions_with_usage: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/functions', methods=['POST'])
@jwt_required
def create_bot_function(bot_id):
    """
    Cria uma nova função para um bot específico
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Obter dados do JSON
        data = request.get_json()
        
        # Validação dos dados obrigatórios
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        required_fields = ['function_id']
        for field in required_fields:
            if field not in data or data[field] is None:
                return jsonify({
                    "error": f"Campo '{field}' é obrigatório",
                    "status": "error"
                }), 400
        
        # Validação de tamanhos
        if len(data['function_id']) > 150:
            return jsonify({
                "error": "Campo 'function_id' deve ter no máximo 150 caracteres",
                "status": "error"
            }), 400
        
        if 'description' in data and data['description'] and len(data['description']) > 255:
            return jsonify({
                "error": "Campo 'description' deve ter no máximo 255 caracteres",
                "status": "error"
            }), 400
        
        if 'action' in data and data['action'] is not None and len(data['action']) > 255:
            return jsonify({
                "error": "Campo 'action' deve ter no máximo 255 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se a função já existe para este bot
        existing_function = db_manager.get_bot_function(bot_id, data['function_id'])
        if existing_function:
            return jsonify({
                "error": "Função com este function_id já existe para este bot",
                "status": "error"
            }), 409
        
        # Inserir nova função
        success = db_manager.insert_bot_function(
            bot_id=bot_id,
            function_id=data['function_id'],
            description=data.get('description'),
            action=data.get('action')
        )
        
        if success:
            # Buscar a função criada para retornar
            created_function = db_manager.get_bot_function(bot_id, data['function_id'])
            return jsonify({
                "message": "Função criada com sucesso",
                "status": "success",
                "function": created_function
            }), 201
        else:
            return jsonify({
                "error": "Falha ao criar função",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint create_bot_function: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/functions/<function_id>', methods=['PUT'])
@jwt_required
def update_bot_function(bot_id, function_id):
    """
    Atualiza uma função específica de um bot
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se a função existe
        existing_function = db_manager.get_bot_function(bot_id, function_id)
        if not existing_function:
            return jsonify({
                "error": "Função não encontrada",
                "status": "error"
            }), 404
        
        # Obter dados do JSON
        data = request.get_json()
        
        # Validação básica
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Validações dos campos opcionais
        update_params = {}
        
        if 'description' in data:
            if data['description'] and len(data['description']) > 255:
                return jsonify({
                    "error": "Campo 'description' deve ter no máximo 255 caracteres",
                    "status": "error"
                }), 400
            update_params['description'] = data['description']
        
        if 'action' in data:
            if data['action'] is not None and len(data['action']) > 255:
                return jsonify({
                    "error": "Campo 'action' deve ter no máximo 255 caracteres",
                    "status": "error"
                }), 400
            update_params['action'] = data['action']
        
        if not update_params:
            return jsonify({
                "error": "Nenhum campo válido fornecido para atualização",
                "status": "error"
            }), 400
        
        # Atualizar função
        logger.info(f"🔄 Atualizando função {function_id} do bot {bot_id} com parâmetros: {update_params}")
        
        try:
            success = db_manager.update_bot_function(
                bot_id=bot_id,
                function_id=function_id,
                **update_params
            )
            logger.info(f"✅ Resultado da atualização: {success}")
            
            if success:
                # Buscar a função atualizada
                logger.info(f"🔍 Buscando função atualizada: {function_id}")
                updated_function = db_manager.get_bot_function(bot_id, function_id)
                logger.info(f"✅ Função encontrada: {updated_function}")
                
                return jsonify({
                    "message": "Função atualizada com sucesso",
                    "status": "success",
                    "function": updated_function,
                    "updated_fields": list(update_params.keys())
                }), 200
            else:
                logger.error(f"❌ Falha ao atualizar função - success=False")
                return jsonify({
                    "error": "Falha ao atualizar função",
                    "status": "error"
                }), 500
        except Exception as db_error:
            logger.error(f"❌ Erro na operação do banco: {db_error}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return jsonify({
                "error": f"Erro na atualização: {str(db_error)}",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint update_bot_function: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/functions/<function_id>', methods=['DELETE'])
@jwt_required
def delete_bot_function(bot_id, function_id):
    """
    Deleta permanentemente uma função específica de um bot e todos os seus parâmetros
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se a função existe
        existing_function = db_manager.get_bot_function(bot_id, function_id)
        if not existing_function:
            return jsonify({
                "error": "Função não encontrada",
                "status": "error"
            }), 404
        
        # Deletar função (incluindo parâmetros automaticamente)
        success = db_manager.delete_bot_function(bot_id, function_id)
        
        if success:
            return jsonify({
                "message": "Função e seus parâmetros deletados permanentemente com sucesso",
                "status": "success",
                "bot_id": bot_id,
                "function_id": function_id,
                "action": "deletado permanentemente"
            }), 200
        else:
            return jsonify({
                "error": "Falha ao deletar função",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint delete_bot_function: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

# ==================== BOTS FUNCTIONS PARAMETERS ENDPOINTS ====================

@app.route('/bots/<bot_id>/functions/<function_id>/parameters', methods=['GET'])
@jwt_required
def get_bot_function_parameters(bot_id, function_id):
    """
    Lista todos os parâmetros de uma função específica
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Validar function_id (varchar 150)
        if not function_id or len(function_id) > 150:
            return jsonify({
                "error": "function_id deve ser uma string não vazia com máximo 150 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se a função existe
        function = db_manager.get_bot_function(bot_id, function_id)
        if not function:
            return jsonify({
                "error": "Função não encontrada",
                "status": "error"
            }), 404
        
        # Buscar parâmetros da função filtrados por bot_id
        parameters = db_manager.get_bot_function_parameters(function_id, bot_id)
        
        return jsonify({
            "status": "success",
            "bot_id": bot_id,
            "function_id": function_id,
            "parameters": parameters,
            "total": len(parameters)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_bot_function_parameters: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

def _validate_parameter(param_data, function_id, db_manager, bot_id=None):
    """
    Valida um parâmetro individual para criação. Retorna (is_valid, error_message)
    """
    # Campos obrigatórios
    required_fields = ['parameter_id', 'type']
    for field in required_fields:
        if field not in param_data or param_data[field] is None:
            return False, f"Campo '{field}' é obrigatório"
    
    # Validar tamanho do parameter_id
    if len(param_data['parameter_id']) > 100:
        return False, "Campo 'parameter_id' deve ter no máximo 100 caracteres"
    
    # Validar tipo de parâmetro
    valid_types = ['string', 'number', 'integer', 'boolean', 'object', 'array']
    if param_data['type'] not in valid_types:
        return False, f"Tipo de parâmetro inválido. Tipos válidos: {', '.join(valid_types)}"
    
    # Validar formato se fornecido
    if 'format' in param_data and param_data['format']:
        valid_formats = ['email', 'uri', 'date', 'date-time']
        if param_data['format'] not in valid_formats:
            return False, f"Formato inválido. Formatos válidos: {', '.join(valid_formats)}"
    
    # Validação de tamanhos
    if len(param_data['type']) > 20:
        return False, "Campo 'type' deve ter no máximo 20 caracteres"
    
    if 'default_value' in param_data and param_data['default_value'] and len(param_data['default_value']) > 100:
        return False, "Campo 'default_value' deve ter no máximo 100 caracteres"
    
    if 'format' in param_data and param_data['format'] and len(param_data['format']) > 15:
        return False, "Campo 'format' deve ter no máximo 15 caracteres"
    
    # Verificar se o parâmetro já existe para esta função
    existing_parameter = db_manager.get_bot_function_parameter(function_id, param_data['parameter_id'], bot_id)
    if existing_parameter:
        return False, f"Parâmetro '{param_data['parameter_id']}' já existe para esta função"
    
    return True, None

def _validate_parameter_update(param_data, function_id, db_manager, bot_id=None):
    """
    Valida um parâmetro individual para atualização. Retorna (is_valid, error_message)
    """
    # Para update, parameter_id é obrigatório mas type é opcional
    if 'parameter_id' not in param_data or param_data['parameter_id'] is None:
        return False, "Campo 'parameter_id' é obrigatório para identificar o parâmetro"
    
    # Validar tamanho do parameter_id
    if len(param_data['parameter_id']) > 100:
        return False, "Campo 'parameter_id' deve ter no máximo 100 caracteres"
    
    # Verificar se o parâmetro existe
    existing_parameter = db_manager.get_bot_function_parameter(function_id, param_data['parameter_id'], bot_id)
    if not existing_parameter:
        return False, f"Parâmetro '{param_data['parameter_id']}' não encontrado"
    
    # Validar tipo se fornecido
    if 'type' in param_data and param_data['type']:
        valid_types = ['string', 'number', 'integer', 'boolean', 'object', 'array']
        if param_data['type'] not in valid_types:
            return False, f"Tipo de parâmetro inválido. Tipos válidos: {', '.join(valid_types)}"
        if len(param_data['type']) > 20:
            return False, "Campo 'type' deve ter no máximo 20 caracteres"
    
    # Validar formato se fornecido
    if 'format' in param_data and param_data['format']:
        valid_formats = ['email', 'uri', 'date', 'date-time']
        if param_data['format'] not in valid_formats:
            return False, f"Formato inválido. Formatos válidos: {', '.join(valid_formats)}"
        if len(param_data['format']) > 15:
            return False, "Campo 'format' deve ter no máximo 15 caracteres"
    
    # Validar default_value se fornecido
    if 'default_value' in param_data and param_data['default_value'] and len(param_data['default_value']) > 100:
        return False, "Campo 'default_value' deve ter no máximo 100 caracteres"
    
    # Validar description se fornecida
    if 'description' in param_data and param_data['description'] is not None and not isinstance(param_data['description'], str):
        return False, "Campo 'description' deve ser uma string"
    
    return True, None

@app.route('/bots/<bot_id>/functions/<function_id>/parameters', methods=['POST'])
@jwt_required
def create_bot_function_parameter(bot_id, function_id):
    """
    Cria um ou múltiplos parâmetros para uma função específica.
    Aceita tanto um objeto único quanto um array de parâmetros.
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Validar function_id (varchar 150)
        if not function_id or len(function_id) > 150:
            return jsonify({
                "error": "function_id deve ser uma string não vazia com máximo 150 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se a função existe
        function = db_manager.get_bot_function(bot_id, function_id)
        if not function:
            return jsonify({
                "error": "Função não encontrada",
                "status": "error"
            }), 404
        
        # Obter dados do JSON
        data = request.get_json()
        
        # Validação dos dados obrigatórios
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Detectar se é um array de parâmetros ou um parâmetro único
        is_batch = isinstance(data, list)
        parameters_to_create = data if is_batch else [data]
        
        if not parameters_to_create:
            return jsonify({
                "error": "Lista de parâmetros não pode estar vazia",
                "status": "error"
            }), 400
        
        # Validar todos os parâmetros antes de inserir
        validation_errors = []
        for i, param_data in enumerate(parameters_to_create):
            is_valid, error_msg = _validate_parameter(param_data, function_id, db_manager, bot_id)
            if not is_valid:
                if is_batch:
                    validation_errors.append(f"Parâmetro {i+1}: {error_msg}")
                else:
                    return jsonify({
                        "error": error_msg,
                        "status": "error"
                    }), 400
        
        # Se há erros de validação no batch, retornar todos
        if validation_errors:
            return jsonify({
                "error": "Erros de validação encontrados",
                "status": "error",
                "validation_errors": validation_errors
            }), 400
        
        # Inserir todos os parâmetros
        created_parameters = []
        failed_parameters = []
        
        for param_data in parameters_to_create:
            success = db_manager.insert_bot_function_parameter(
                function_id=function_id,
                parameter_id=param_data['parameter_id'],
                param_type=param_data['type'],
                permited_values=param_data.get('permited_values'),
                default_value=param_data.get('default_value'),
                param_format=param_data.get('format'),
                description=param_data.get('description'),
                bot_id=bot_id
            )
            
            if success:
                # Buscar o parâmetro criado para retornar
                created_parameter = db_manager.get_bot_function_parameter(function_id, param_data['parameter_id'], bot_id)
                if created_parameter:
                    created_parameters.append(created_parameter)
            else:
                failed_parameters.append(param_data['parameter_id'])
        
        # Preparar resposta
        if failed_parameters:
            return jsonify({
                "error": f"Falha ao criar alguns parâmetros: {', '.join(failed_parameters)}",
                "status": "partial_error",
                "created_parameters": created_parameters,
                "failed_parameters": failed_parameters,
                "total_created": len(created_parameters),
                "total_failed": len(failed_parameters)
            }), 207  # Multi-Status
        
        # Sucesso total
        if is_batch:
            return jsonify({
                "message": f"{len(created_parameters)} parâmetros criados com sucesso",
                "status": "success",
                "parameters": created_parameters,
                "total_created": len(created_parameters)
            }), 201
        else:
            return jsonify({
                "message": "Parâmetro criado com sucesso",
                "status": "success",
                "parameter": created_parameters[0]
            }), 201
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint create_bot_function_parameter: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/functions/<function_id>/parameters', methods=['PUT'])
@jwt_required
def update_bot_function_parameters_batch(bot_id, function_id):
    """
    Atualiza múltiplos parâmetros de uma função específica.
    Aceita um array de objetos de parâmetros para atualização batch.
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Validar function_id (varchar 150)
        if not function_id or len(function_id) > 150:
            return jsonify({
                "error": "function_id deve ser uma string não vazia com máximo 150 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se a função existe
        function = db_manager.get_bot_function(bot_id, function_id)
        if not function:
            return jsonify({
                "error": "Função não encontrada",
                "status": "error"
            }), 404
        
        # Obter dados do JSON
        data = request.get_json()
        
        # Validação dos dados obrigatórios
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Deve ser um array para batch update
        if not isinstance(data, list):
            return jsonify({
                "error": "Para batch update, envie um array de parâmetros",
                "status": "error"
            }), 400
        
        if not data:
            return jsonify({
                "error": "Lista de parâmetros não pode estar vazia",
                "status": "error"
            }), 400
        
        # Validar todos os parâmetros antes de atualizar
        validation_errors = []
        for i, param_data in enumerate(data):
            is_valid, error_msg = _validate_parameter_update(param_data, function_id, db_manager, bot_id)
            if not is_valid:
                validation_errors.append(f"Parâmetro {i+1} ({param_data.get('parameter_id', 'ID não informado')}): {error_msg}")
        
        # Se há erros de validação, retornar todos
        if validation_errors:
            return jsonify({
                "error": "Erros de validação encontrados",
                "status": "error",
                "validation_errors": validation_errors
            }), 400
        
        # Atualizar todos os parâmetros
        updated_parameters = []
        failed_parameters = []
        
        for param_data in data:
            # Preparar campos para atualização
            update_fields = {}
            
            if 'type' in param_data:
                update_fields['param_type'] = param_data['type']
            if 'permited_values' in param_data:
                update_fields['permited_values'] = param_data['permited_values']
            if 'default_value' in param_data:
                update_fields['default_value'] = param_data['default_value']
            if 'format' in param_data:
                update_fields['param_format'] = param_data['format']
            if 'description' in param_data:
                update_fields['description'] = param_data['description']
            
            if update_fields:  # Só atualizar se há campos para atualizar
                success = db_manager.update_bot_function_parameter(
                    function_id=function_id,
                    parameter_id=param_data['parameter_id'],
                    bot_id=bot_id,
                    **update_fields
                )
                
                if success:
                    # Buscar o parâmetro atualizado
                    updated_parameter = db_manager.get_bot_function_parameter(function_id, param_data['parameter_id'], bot_id)
                    if updated_parameter:
                        updated_parameters.append(updated_parameter)
                else:
                    failed_parameters.append(param_data['parameter_id'])
            else:
                # Se não há campos para atualizar, considerar como "sucesso" mas buscar o parâmetro atual
                current_parameter = db_manager.get_bot_function_parameter(function_id, param_data['parameter_id'], bot_id)
                if current_parameter:
                    updated_parameters.append(current_parameter)
        
        # Preparar resposta
        if failed_parameters:
            return jsonify({
                "error": f"Falha ao atualizar alguns parâmetros: {', '.join(failed_parameters)}",
                "status": "partial_error",
                "updated_parameters": updated_parameters,
                "failed_parameters": failed_parameters,
                "total_updated": len(updated_parameters),
                "total_failed": len(failed_parameters)
            }), 207  # Multi-Status
        
        # Sucesso total
        return jsonify({
            "message": f"{len(updated_parameters)} parâmetros atualizados com sucesso",
            "status": "success",
            "parameters": updated_parameters,
            "total_updated": len(updated_parameters)
        }), 200
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint update_bot_function_parameters_batch: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/functions/<function_id>/parameters/<parameter_id>', methods=['PUT'])
@jwt_required
def update_bot_function_parameter(bot_id, function_id, parameter_id):
    """
    Atualiza um parâmetro específico de uma função
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Validar function_id (varchar 150)
        if not function_id or len(function_id) > 150:
            return jsonify({
                "error": "function_id deve ser uma string não vazia com máximo 150 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se a função existe
        function = db_manager.get_bot_function(bot_id, function_id)
        if not function:
            return jsonify({
                "error": "Função não encontrada",
                "status": "error"
            }), 404
        
        # Verificar se o parâmetro existe
        existing_parameter = db_manager.get_bot_function_parameter(function_id, parameter_id, bot_id)
        if not existing_parameter:
            return jsonify({
                "error": "Parâmetro não encontrado",
                "status": "error"
            }), 404
        
        # Obter dados do JSON
        data = request.get_json()
        
        # Validação básica
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Validações dos campos opcionais
        update_params = {}
        
        if 'type' in data:
            valid_types = ['string', 'number', 'integer', 'boolean', 'object', 'array']
            if data['type'] not in valid_types:
                return jsonify({
                    "error": f"Tipo de parâmetro inválido. Tipos válidos: {', '.join(valid_types)}",
                    "status": "error"
                }), 400
            update_params['param_type'] = data['type']
        
        if 'permited_values' in data:
            update_params['permited_values'] = data['permited_values']
        
        if 'default_value' in data:
            if data['default_value'] and len(data['default_value']) > 100:
                return jsonify({
                    "error": "Campo 'default_value' deve ter no máximo 100 caracteres",
                    "status": "error"
                }), 400
            update_params['default_value'] = data['default_value']
        
        if 'format' in data:
            if data['format']:
                valid_formats = ['email', 'uri', 'date', 'date-time']
                if data['format'] not in valid_formats:
                    return jsonify({
                        "error": f"Formato inválido. Formatos válidos: {', '.join(valid_formats)}",
                        "status": "error"
                    }), 400
                if len(data['format']) > 15:
                    return jsonify({
                        "error": "Campo 'format' deve ter no máximo 15 caracteres",
                        "status": "error"
                    }), 400
            update_params['param_format'] = data['format']
        
        if 'description' in data:
            # Campo TEXT - sem limite específico de tamanho, mas vamos validar se é string
            if data['description'] is not None and not isinstance(data['description'], str):
                return jsonify({
                    "error": "Campo 'description' deve ser uma string",
                    "status": "error"
                }), 400
            update_params['description'] = data['description']
        
        if not update_params:
            return jsonify({
                "error": "Nenhum campo válido fornecido para atualização",
                "status": "error"
            }), 400
        
        # Atualizar parâmetro
        success = db_manager.update_bot_function_parameter(
            function_id=function_id,
            parameter_id=parameter_id,
            bot_id=bot_id,
            **update_params
        )
        
        if success:
            # Buscar o parâmetro atualizado
            updated_parameter = db_manager.get_bot_function_parameter(function_id, parameter_id, bot_id)
            return jsonify({
                "message": "Parâmetro atualizado com sucesso",
                "status": "success",
                "parameter": updated_parameter,
                "updated_fields": list(update_params.keys())
            }), 200
        else:
            return jsonify({
                "error": "Falha ao atualizar parâmetro",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint update_bot_function_parameter: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/functions/<function_id>/parameters', methods=['DELETE'])
@jwt_required
def delete_bot_function_parameters_batch(bot_id, function_id):
    """
    Deleta múltiplos parâmetros de uma função específica.
    Aceita um array de parameter_ids no corpo da requisição.
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Validar function_id (varchar 150)
        if not function_id or len(function_id) > 150:
            return jsonify({
                "error": "function_id deve ser uma string não vazia com máximo 150 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se a função existe
        function = db_manager.get_bot_function(bot_id, function_id)
        if not function:
            return jsonify({
                "error": "Função não encontrada",
                "status": "error"
            }), 404
        
        # Obter dados do JSON
        data = request.get_json()
        
        # Validação dos dados obrigatórios
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Aceita duas estruturas:
        # 1. {"parameter_ids": ["param1", "param2", "param3"]}
        # 2. ["param1", "param2", "param3"]
        parameter_ids = []
        
        if isinstance(data, list):
            # Formato direto: array de parameter_ids
            parameter_ids = data
        elif isinstance(data, dict) and 'parameter_ids' in data:
            # Formato objeto com chave parameter_ids
            parameter_ids = data['parameter_ids']
        else:
            return jsonify({
                "error": "Formato inválido. Envie um array de parameter_ids ou um objeto com chave 'parameter_ids'",
                "status": "error"
            }), 400
        
        if not parameter_ids or not isinstance(parameter_ids, list):
            return jsonify({
                "error": "Lista de parameter_ids não pode estar vazia",
                "status": "error"
            }), 400
        
        # Validar todos os parameter_ids
        validation_errors = []
        for i, param_id in enumerate(parameter_ids):
            if not param_id or not isinstance(param_id, str):
                validation_errors.append(f"Parâmetro {i+1}: parameter_id deve ser uma string não vazia")
                continue
            
            if len(param_id) > 100:
                validation_errors.append(f"Parâmetro {i+1} ({param_id}): parameter_id deve ter no máximo 100 caracteres")
                continue
            
            # Verificar se o parâmetro existe
            existing_parameter = db_manager.get_bot_function_parameter(function_id, param_id, bot_id)
            if not existing_parameter:
                validation_errors.append(f"Parâmetro {i+1} ({param_id}): parâmetro não encontrado")
        
        # Se há erros de validação, retornar todos
        if validation_errors:
            return jsonify({
                "error": "Erros de validação encontrados",
                "status": "error",
                "validation_errors": validation_errors
            }), 400
        
        # Deletar todos os parâmetros
        deleted_parameters = []
        failed_parameters = []
        
        for param_id in parameter_ids:
            success = db_manager.delete_bot_function_parameter(function_id, param_id, bot_id)
            
            if success:
                deleted_parameters.append(param_id)
            else:
                failed_parameters.append(param_id)
        
        # Preparar resposta
        if failed_parameters:
            return jsonify({
                "error": f"Falha ao deletar alguns parâmetros: {', '.join(failed_parameters)}",
                "status": "partial_error",
                "deleted_parameters": deleted_parameters,
                "failed_parameters": failed_parameters,
                "total_deleted": len(deleted_parameters),
                "total_failed": len(failed_parameters)
            }), 207  # Multi-Status
        
        # Sucesso total
        return jsonify({
            "message": f"{len(deleted_parameters)} parâmetros deletados permanentemente com sucesso",
            "status": "success",
            "deleted_parameters": deleted_parameters,
            "total_deleted": len(deleted_parameters),
            "action": "deletado permanentemente"
        }), 200
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint delete_bot_function_parameters_batch: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/functions/<function_id>/parameters/<parameter_id>', methods=['DELETE'])
@jwt_required
def delete_bot_function_parameter(bot_id, function_id, parameter_id):
    """
    Deleta permanentemente um parâmetro específico de uma função
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "bot_id deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Validar function_id (varchar 150)
        if not function_id or len(function_id) > 150:
            return jsonify({
                "error": "function_id deve ser uma string não vazia com máximo 150 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se a função existe
        function = db_manager.get_bot_function(bot_id, function_id)
        if not function:
            return jsonify({
                "error": "Função não encontrada",
                "status": "error"
            }), 404
        
        # Verificar se o parâmetro existe
        existing_parameter = db_manager.get_bot_function_parameter(function_id, parameter_id, bot_id)
        if not existing_parameter:
            return jsonify({
                "error": "Parâmetro não encontrado",
                "status": "error"
            }), 404
        
        # Deletar parâmetro
        success = db_manager.delete_bot_function_parameter(function_id, parameter_id, bot_id)
        
        if success:
            return jsonify({
                "message": "Parâmetro deletado permanentemente com sucesso",
                "status": "success",
                "function_id": function_id,
                "parameter_id": parameter_id,
                "action": "deletado permanentemente"
            }), 200
        else:
            return jsonify({
                "error": "Falha ao deletar parâmetro",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint delete_bot_function_parameter: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

# ==================== WHATSAPP TOKEN MANAGEMENT ====================

@app.route('/whatsapp/token/optimize', methods=['POST'])
@jwt_required
def optimize_whatsapp_token():
    """
    Otimiza a estrutura do whatsapp_token removendo campos desnecessários
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter dados opcionais do JSON
        data = request.get_json() or {}
        
        phone_number_id = data.get('phone_number_id')
        display_phone_number = data.get('display_phone_number')
        
        # Otimizar token
        success = db_manager.optimize_whatsapp_token(phone_number_id, display_phone_number)
        
        if success:
            # Limpar cache do WhatsApp service
            from whatsapp_service import WhatsAppService
            whatsapp_service = WhatsAppService()
            whatsapp_service.refresh_phone_config()
            
            logger.info(f"✅ Token WhatsApp otimizado pelo usuário {request.current_user.get('sub')}")
            
            # Buscar token otimizado para retornar
            optimized_token = db_manager.get_config('whatsapp_token')
            
            return jsonify({
                "message": "Token WhatsApp otimizado com sucesso",
                "status": "success",
                "token_structure": {
                    "access_token": "***redacted***",
                    "expires_at": optimized_token.get('expires_at'),
                    "is_long_lived": optimized_token.get('is_long_lived'),
                    "phone_number_id": optimized_token.get('phone_number_id'),
                    "display_phone_number": optimized_token.get('display_phone_number'),
                    "version": optimized_token.get('version'),
                    "optimized_at": optimized_token.get('optimized_at')
                }
            }), 200
        else:
            return jsonify({
                "error": "Falha ao otimizar token WhatsApp",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint optimize_whatsapp_token: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/whatsapp/phone/config', methods=['GET'])
@jwt_required
def get_whatsapp_phone_config():
    """
    Retorna configuração do telefone WhatsApp (phone_number_id e display_phone_number)
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Buscar configuração
        phone_config = db_manager.get_whatsapp_phone_config()
        
        if phone_config:
            return jsonify({
                "status": "success",
                "phone_config": phone_config
            }), 200
        else:
            return jsonify({
                "error": "Configuração do telefone WhatsApp não encontrada",
                "status": "error"
            }), 404
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_whatsapp_phone_config: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/channels/security/audit', methods=['GET'])
@jwt_required
def audit_channels_security():
    """
    Endpoint de auditoria para verificar se a filtragem por account_id está funcionando
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Informações do usuário
        user_id = request.current_user.get('sub')
        user_email = request.current_user.get('email', 'unknown')
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        logger.info(f"🔍 AUDITORIA DE SEGURANÇA: Usuário {user_id} verificando isolamento da conta {account_id}")
        
        # Buscar canais da conta
        channels = db_manager.get_channels_by_account(account_id, False)
        
        # Análise de segurança
        analysis = {
            "total_channels_found": len(channels),
            "account_ids_in_results": [],
            "security_violations": [],
            "security_status": "UNKNOWN"
        }
        
        if channels:
            # Verificar todos os account_ids retornados
            account_ids_found = [ch.get('account_id') for ch in channels]
            unique_account_ids = list(set(account_ids_found))
            
            analysis["account_ids_in_results"] = unique_account_ids
            
            # Verificar violações de segurança
            if len(unique_account_ids) > 1:
                analysis["security_violations"].append(f"Múltiplas contas retornadas: {unique_account_ids}")
                analysis["security_status"] = "VIOLATED"
            elif unique_account_ids and unique_account_ids[0] != account_id:
                analysis["security_violations"].append(f"Conta incorreta retornada. Esperado: {account_id}, Encontrado: {unique_account_ids[0]}")
                analysis["security_status"] = "VIOLATED"
            else:
                analysis["security_status"] = "SECURE"
        else:
            analysis["security_status"] = "SECURE"
            analysis["account_ids_in_results"] = []
        
        # Log do resultado da auditoria
        if analysis["security_status"] == "VIOLATED":
            logger.error(f"🚨 AUDITORIA FALHOU: Violações de segurança detectadas para usuário {user_id}")
        else:
            logger.info(f"✅ AUDITORIA PASSOU: Segurança OK para usuário {user_id}")
        
        return jsonify({
            "audit_timestamp": datetime.now().isoformat(),
            "user_info": {
                "user_id": user_id,
                "user_email": user_email,
                "account_id": account_id
            },
            "security_analysis": analysis,
            "query_info": {
                "sql_filter": f"WHERE account_id = '{account_id}'",
                "parameter_binding": True,
                "prepared_statement": True
            },
            "channels_summary": [
                {
                    "id": ch.get('id'),
                    "account_id": ch.get('account_id'),
                    "type": ch.get('type'),
                    "name": ch.get('name'),
                    "active": ch.get('active')
                } for ch in channels
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint de auditoria: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

# ===== INTEGRATIONS ENDPOINTS =====

@app.route('/integrations', methods=['GET'])
@jwt_required
def get_integrations():
    """
    Lista todas as integrações de uma conta
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Verificar se deve filtrar apenas ativos
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        
        # Buscar integrações
        integrations = db_manager.get_integrations_by_account(account_id, active_only)
        
        return jsonify({
            "integrations": integrations,
            "total": len(integrations),
            "status": "success"
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar integrações: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/integrations', methods=['POST'])
@jwt_required
def create_integration_endpoint():
    """
    Cria uma nova integração
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar dados da requisição
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Dados JSON não fornecidos",
                "status": "error"
            }), 400
        
        # Campos obrigatórios
        required_fields = ['integration_type']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    "error": f"Campo obrigatório '{field}' não fornecido",
                    "status": "error"
                }), 400
        
        # Validar integration_type
        integration_type = data['integration_type']
        if not isinstance(integration_type, str) or len(integration_type.strip()) == 0:
            return jsonify({
                "error": "Campo 'integration_type' deve ser uma string não vazia",
                "status": "error"
            }), 400
        
        # Validar campos opcionais
        name = data.get('name')
        if name is not None and (not isinstance(name, str) or len(name) > 100):
            return jsonify({
                "error": "Campo 'name' deve ser uma string com até 100 caracteres",
                "status": "error"
            }), 400
        
        is_active = data.get('is_active', 1)
        if not isinstance(is_active, (int, bool)):
            return jsonify({
                "error": "Campo 'is_active' deve ser um boolean ou número",
                "status": "error"
            }), 400
        
        access_token = data.get('access_token')
        if access_token is not None and not isinstance(access_token, str):
            return jsonify({
                "error": "Campo 'access_token' deve ser uma string",
                "status": "error"
            }), 400
        
        client_id = data.get('client_id')
        if client_id is not None and not isinstance(client_id, str):
            return jsonify({
                "error": "Campo 'client_id' deve ser uma string",
                "status": "error"
            }), 400
        
        client_secret = data.get('client_secret')
        if client_secret is not None and not isinstance(client_secret, str):
            return jsonify({
                "error": "Campo 'client_secret' deve ser uma string",
                "status": "error"
            }), 400
        
        # Gerar UUID para o ID
        integration_id = str(uuid.uuid4())
        
        # Inserir no banco de dados
        success = db_manager.insert_integration(
            integration_id, account_id, integration_type, name, 
            int(is_active) if isinstance(is_active, bool) else is_active,
            access_token, client_id, client_secret
        )
        
        if success:
            # Buscar a integração criada para retornar
            integration = db_manager.get_integration(integration_id)
            return jsonify({
                "integration": integration,
                "message": "Integração criada com sucesso",
                "status": "success"
            }), 201
        else:
            return jsonify({
                "error": "Falha ao criar integração",
                "status": "error"
            }), 500
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar integração: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/integrations/<integration_id>', methods=['GET'])
@jwt_required
def get_integration_by_id(integration_id):
    """
    Busca uma integração específica pelo ID
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Validar UUID
        try:
            uuid.UUID(integration_id)
        except ValueError:
            return jsonify({
                "error": "ID da integração deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Buscar integração
        integration = db_manager.get_integration(integration_id)
        
        if not integration:
            return jsonify({
                "error": "Integração não encontrada",
                "status": "error"
            }), 404
        
        # Verificar se a integração pertence à conta do usuário
        if integration['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado à integração",
                "status": "error"
            }), 403
        
        return jsonify({
            "integration": integration,
            "status": "success"
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar integração: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/integrations/<integration_id>', methods=['PUT'])
@jwt_required
def update_integration_endpoint(integration_id):
    """
    Atualiza uma integração existente
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Validar UUID
        try:
            uuid.UUID(integration_id)
        except ValueError:
            return jsonify({
                "error": "ID da integração deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Verificar se a integração existe e pertence à conta
        existing_integration = db_manager.get_integration_full(integration_id)
        if not existing_integration:
            return jsonify({
                "error": "Integração não encontrada",
                "status": "error"
            }), 404
        
        if existing_integration['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado à integração",
                "status": "error"
            }), 403
        
        # Validar dados da requisição
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Dados JSON não fornecidos",
                "status": "error"
            }), 400
        
        # Validar campos opcionais
        integration_type = data.get('integration_type')
        if integration_type is not None and (not isinstance(integration_type, str) or len(integration_type.strip()) == 0):
            return jsonify({
                "error": "Campo 'integration_type' deve ser uma string não vazia",
                "status": "error"
            }), 400
        
        name = data.get('name')
        if name is not None and (not isinstance(name, str) or len(name) > 100):
            return jsonify({
                "error": "Campo 'name' deve ser uma string com até 100 caracteres",
                "status": "error"
            }), 400
        
        is_active = data.get('is_active')
        if is_active is not None and not isinstance(is_active, (int, bool)):
            return jsonify({
                "error": "Campo 'is_active' deve ser um boolean ou número",
                "status": "error"
            }), 400
        
        access_token = data.get('access_token', '__NOT_PROVIDED__')
        if access_token != '__NOT_PROVIDED__' and access_token is not None and not isinstance(access_token, str):
            return jsonify({
                "error": "Campo 'access_token' deve ser uma string",
                "status": "error"
            }), 400
        
        client_id = data.get('client_id', '__NOT_PROVIDED__')
        if client_id != '__NOT_PROVIDED__' and client_id is not None and not isinstance(client_id, str):
            return jsonify({
                "error": "Campo 'client_id' deve ser uma string",
                "status": "error"
            }), 400
        
        client_secret = data.get('client_secret', '__NOT_PROVIDED__')
        if client_secret != '__NOT_PROVIDED__' and client_secret is not None and not isinstance(client_secret, str):
            return jsonify({
                "error": "Campo 'client_secret' deve ser uma string",
                "status": "error"
            }), 400
        
        # Converter access_token, client_id, client_secret null para None
        if access_token == '__NOT_PROVIDED__':
            access_token = '__NOT_PROVIDED__'
        elif access_token is None:
            access_token = None
        
        if client_id == '__NOT_PROVIDED__':
            client_id = '__NOT_PROVIDED__'
        elif client_id is None:
            client_id = None
        
        if client_secret == '__NOT_PROVIDED__':
            client_secret = '__NOT_PROVIDED__'
        elif client_secret is None:
            client_secret = None
        
        # Converter is_active boolean para int
        if isinstance(is_active, bool):
            is_active = int(is_active)
        
        # Atualizar no banco de dados
        success = db_manager.update_integration(
            integration_id, account_id, integration_type, name, is_active,
            access_token, client_id, client_secret
        )
        
        if success:
            # Buscar a integração atualizada para retornar
            integration = db_manager.get_integration(integration_id)
            return jsonify({
                "integration": integration,
                "message": "Integração atualizada com sucesso",
                "status": "success"
            }), 200
        else:
            return jsonify({
                "error": "Falha ao atualizar integração",
                "status": "error"
            }), 500
        
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar integração: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/integrations/<integration_id>', methods=['DELETE'])
@jwt_required
def delete_integration_endpoint(integration_id):
    """
    Remove uma integração
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Validar UUID
        try:
            uuid.UUID(integration_id)
        except ValueError:
            return jsonify({
                "error": "ID da integração deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Verificar se a integração existe e pertence à conta
        existing_integration = db_manager.get_integration_full(integration_id)
        if not existing_integration:
            return jsonify({
                "error": "Integração não encontrada",
                "status": "error"
            }), 404
        
        if existing_integration['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado à integração",
                "status": "error"
            }), 403
        
        # Deletar do banco de dados
        success = db_manager.delete_integration(integration_id, account_id)
        
        if success:
            return jsonify({
                "message": "Integração removida com sucesso",
                "status": "success"
            }), 200
        else:
            return jsonify({
                "error": "Falha ao remover integração",
                "status": "error"
            }), 500
        
    except Exception as e:
        logger.error(f"❌ Erro ao remover integração: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/whatsapp/token/status', methods=['GET'])
@jwt_required
def get_whatsapp_token_status():
    """
    Retorna status detalhado do token WhatsApp
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Buscar token
        token_data = db_manager.get_config('whatsapp_token')
        
        if not token_data:
            return jsonify({
                "status": "not_found",
                "message": "Token WhatsApp não encontrado",
                "requires_setup": True
            }), 404
        
        # Verificar estrutura (se é otimizada)
        is_optimized = "version" in token_data and token_data.get("version") == "2.0"
        
        # Campos presentes
        present_fields = list(token_data.keys())
        
        # Campos obsoletos que podem ser removidos
        obsolete_fields = []
        for field in ['created_at', 'expires_in', 'token_type', 'raw_response']:
            if field in token_data:
                obsolete_fields.append(field)
        
        return jsonify({
            "status": "found",
            "is_optimized": is_optimized,
            "version": token_data.get("version", "1.0"),
            "present_fields": present_fields,
            "obsolete_fields": obsolete_fields,
            "phone_config": {
                "phone_number_id": token_data.get('phone_number_id'),
                "display_phone_number": token_data.get('display_phone_number')
            },
            "expires_at": token_data.get('expires_at'),
            "is_long_lived": token_data.get('is_long_lived'),
            "optimized_at": token_data.get('optimized_at')
        }), 200
            
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_whatsapp_token_status: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/auth/jwt/test', methods=['POST'])
@jwt_required
def test_jwt_validation():
    """
    Endpoint para testar validação JWT (útil para debug)
    """
    try:
        user_info = {
            "user_id": request.current_user.get('sub'),
            "email": request.current_user.get('email'),
            "role": request.current_user.get('role', 'user'),
            "exp": request.current_user.get('exp'),
            "iat": request.current_user.get('iat'),
            "iss": request.current_user.get('iss'),
            "aud": request.current_user.get('aud')
        }
        
        logger.info(f"✅ Teste JWT bem-sucedido para usuário: {user_info['user_id']}")
        
        return jsonify({
            "status": "success",
            "message": "Token JWT válido e autenticação funcionando",
            "jwt_payload": user_info,
            "supabase_config": {
                "url": SUPABASE_URL,
                "jwks_url": SUPABASE_JWKS_URL,
                "has_anon_key": bool(SUPABASE_ANON_KEY)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no teste JWT: {e}")
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "status": "error"
        }), 500

@app.route('/auth/jwt/status', methods=['GET'])
def jwt_status():
    """
    Endpoint público para verificar status da configuração JWT (sem autenticação)
    """
    try:
        status = {
            "local_auth": {
                "enabled": True,
                "issuer": AUTH_JWT_ISSUER,
                "audience": AUTH_JWT_AUDIENCE,
                "access_ttl_seconds": AUTH_JWT_ACCESS_TTL_SECONDS,
                "accept_supabase_tokens": AUTH_ACCEPT_SUPABASE_TOKENS,
            },
            "supabase_migration": {
                "supabase_url_configured": bool(SUPABASE_URL),
                "jwks_url": SUPABASE_JWKS_URL if SUPABASE_URL else "Não configurado",
            },
        }

        # Se ainda estiver aceitando Supabase, validar conectividade do JWKS para troubleshooting
        if AUTH_ACCEPT_SUPABASE_TOKENS and SUPABASE_JWKS_URL:
            try:
                response = requests.get(SUPABASE_JWKS_URL, timeout=5)
                status["supabase_migration"]["jwks_endpoint_accessible"] = response.status_code == 200
                if response.status_code == 200:
                    jwks_data = response.json()
                    status["supabase_migration"]["jwks_keys_count"] = len(jwks_data.get("keys", []))
                else:
                    status["supabase_migration"]["jwks_error"] = f"HTTP {response.status_code}"
            except Exception as e:
                status["supabase_migration"]["jwks_endpoint_accessible"] = False
                status["supabase_migration"]["jwks_error"] = str(e)
        
        return jsonify({
            "status": "success",
            "jwt_configuration": status
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar status JWT: {e}")
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "status": "error"
        }), 500

@app.route('/auth/jwt/decode', methods=['POST'])
def decode_jwt_info():
    """
    Endpoint para debug: mostra informações do token JWT sem validá-lo
    """
    try:
        token = _extract_bearer_token()
        if not token:
            return jsonify({
                "error": "Token de autorização é obrigatório",
                "status": "error"
            }), 400
        
        # Decodificar header sem validação
        try:
            header = jwt.get_unverified_header(token)
        except Exception as e:
            return jsonify({
                "error": f"Erro ao extrair header: {str(e)}",
                "status": "error"
            }), 400
        
        # Decodificar payload sem validação (apenas para ver conteúdo)
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
        except Exception as e:
            return jsonify({
                "error": f"Erro ao extrair payload: {str(e)}",
                "status": "error"
            }), 400
        
        return jsonify({
            "status": "success",
            "message": "Token decodificado com sucesso (não validado)",
            "token_info": {
                "header": header,
                "payload": {
                    "iss": payload.get('iss'),
                    "sub": payload.get('sub'),
                    "aud": payload.get('aud'),
                    "exp": payload.get('exp'),
                    "iat": payload.get('iat'),
                    "email": payload.get('email'),
                    "role": payload.get('role')
                },
                "expected_issuer": f"{SUPABASE_URL}/auth/v1",
                "jwks_url": SUPABASE_JWKS_URL
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no decode JWT: {e}")
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "status": "error"
        }), 500

@app.route('/health')
def health_check():
    """Endpoint de health check robusto para probes"""
    try:
        # Verificação básica de saúde
        health_status = {
            'status': 'healthy',
            'message': 'API está funcionando!',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'database': 'unknown',
            'rabbitmq': 'unknown'
        }
        
        # Verificar conexão com banco (opcional, não falha se não conseguir)
        if db_manager.enabled:
            try:
                # Verificação mais segura - não acessa connection diretamente
                if hasattr(db_manager, 'connection') and db_manager.connection:
                    if hasattr(db_manager.connection, 'is_connected') and db_manager.connection.is_connected():
                        health_status['database'] = 'connected'
                    else:
                        health_status['database'] = 'disconnected'
                else:
                    health_status['database'] = 'no_connection'
            except Exception as e:
                health_status['database'] = f'error: {str(e)}'
        else:
            health_status['database'] = 'disabled'
        
        # Verificar RabbitMQ (opcional, não falha se não conseguir)
        if rabbitmq_manager.enabled:
            try:
                rabbitmq_status = rabbitmq_manager.get_status()
                health_status['rabbitmq'] = rabbitmq_status.get('status', 'unknown')
            except Exception as e:
                health_status['rabbitmq'] = f'error: {str(e)}'
        else:
            health_status['rabbitmq'] = 'disabled'
        
        # Log da verificação de saúde
        logger.info(f"Health check realizado: {health_status['status']}, DB: {health_status['database']}, RabbitMQ: {health_status['rabbitmq']}")
        
        return jsonify(health_status), 200
        
    except Exception as e:
        logger.error(f"Erro no health check: {e}")
        return jsonify({
            'status': 'unhealthy',
            'message': f'Erro interno: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/logs')
def get_logs():
    """Endpoint para consultar logs salvos no banco"""
    try:
        # Usa o novo método execute_query que tem reconexão automática
        logs = db_manager.execute_query(
            "SELECT id, event_type, type, message, id_contact, created_at FROM logs ORDER BY created_at DESC LIMIT 100"
        )
        
        if logs is None:
            return jsonify({
                'error': 'Erro ao conectar com o banco de dados',
                'status': 'error'
            }), 500
        
        return jsonify({
            'logs': logs,
            'count': len(logs),
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar logs: {e}")
        return jsonify({
            'error': f'Erro interno: {str(e)}',
            'status': 'error'
        }), 500

@app.route('/logs/<event_type>')
def get_logs_by_type(event_type):
    """
    Endpoint para visualizar logs por tipo de evento
    """
    try:
        # Usar o método execute_query que já tem verificações de segurança
        logs = db_manager.execute_query(
            """
            SELECT id, event_type, type, message, id_contact, event_data, created_at 
            FROM logs 
            WHERE event_type = %s
            ORDER BY created_at DESC 
            LIMIT 50
            """,
            (event_type,)
        )
        
        if logs is None:
            return jsonify({
                "error": "Erro ao conectar com o banco de dados",
                "status": "error"
            }), 500
        
        # Converter JSON strings de volta para objetos
        for log in logs:
            if isinstance(log['event_data'], str):
                try:
                    log['event_data'] = json.loads(log['event_data'])
                except:
                    pass
                    
        return jsonify({
            "status": "success",
            "event_type": event_type,
            "count": len(logs),
            "logs": logs
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar logs por tipo: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/logs/migrate', methods=['POST'])
def migrate_logs():
    """Endpoint para migrar dados existentes para os novos campos estruturados"""
    try:
        # Executar migração
        success = db_manager.migrate_existing_data()
        
        if success:
            return jsonify({
                "status": "success",
                "message": "Migração de dados concluída com sucesso"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Falha ao executar migração de dados"
            }), 500
            
    except Exception as e:
        logger.error(f"Erro ao executar migração: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Erro interno: {str(e)}"
        }), 500

@app.route('/logs/by-type/<message_type>')
def get_logs_by_message_type(message_type):
    """Endpoint para buscar logs por tipo de mensagem (text, document, image, audio)"""
    try:
        logs = db_manager.execute_query(
            """
            SELECT id, event_type, type, message, id_contact, created_at 
            FROM logs 
            WHERE type = %s
            ORDER BY created_at DESC 
            LIMIT 50
            """,
            (message_type,)
        )
        
        if logs is None:
            return jsonify({
                "error": "Erro ao conectar com o banco de dados",
                "status": "error"
            }), 500
        
        return jsonify({
            "status": "success",
            "message_type": message_type,
            "count": len(logs),
            "logs": logs
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar logs por tipo de mensagem: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/logs/by-contact/<contact_id>')
def get_logs_by_contact(contact_id):
    """Endpoint para buscar logs por ID do contato"""
    try:
        logs = db_manager.execute_query(
            """
            SELECT id, event_type, type, message, id_contact, created_at 
            FROM logs 
            WHERE id_contact = %s
            ORDER BY created_at DESC 
            LIMIT 100
            """,
            (contact_id,)
        )
        
        if logs is None:
            return jsonify({
                "error": "Erro ao conectar com o banco de dados",
                "status": "error"
            }), 500
        
        return jsonify({
            "status": "success",
            "contact_id": contact_id,
            "count": len(logs),
            "logs": logs
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar logs por contato: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/rabbitmq/status')
def rabbitmq_status():
    """Endpoint para verificar status do RabbitMQ e suas filas"""
    try:
        status = rabbitmq_manager.get_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Erro ao obter status do RabbitMQ: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """
    Endpoint para verificação do webhook pelo WhatsApp Business API
    """
    # Parâmetros que o WhatsApp envia para verificar o webhook
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    logger.info(f"Verificação do webhook - Mode: {mode}, Token: {token}")
    
    # Salvar evento de verificação no banco
    verification_data = {
        'mode': mode,
        'token': token,
        'challenge': challenge,
        'timestamp': request.args.get('hub.timestamp'),
        'signature': request.args.get('hub.signature')
    }
    db_manager.save_webhook_event('webhook_verification', verification_data)
    
    # Verifica se o modo é 'subscribe' e se o token está correto
    if mode == 'subscribe' and token == WEBHOOK_VERIFY_TOKEN:
        logger.info("Webhook verificado com sucesso!")
        return challenge, 200
    else:
        logger.warning("Falha na verificação do webhook")
        return 'Forbidden', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Endpoint para receber eventos do WhatsApp Business API
    VERSÃO ROBUSTA - Não falha mesmo se o banco estiver indisponível
    """
    try:
        # Log do corpo da requisição para debug
        body = request.get_json()
        
        # Verificação básica se o body existe
        if body is None:
            logger.warning("Webhook recebido com body vazio ou inválido")
            return jsonify({"status": "error", "message": "Body vazio ou inválido"}), 400
        
        logger.info(f"Webhook recebido: {json.dumps(body, indent=2)}")
        
        # OUTBOX PATTERN: Salvar no banco + outbox em transação atômica
        outbox_saved = False
        try:
            if db_manager and db_manager.enabled:
                # Extrair message_id se disponível para rastreamento
                message_id = None
                if body.get('object') == 'whatsapp_business_account':
                    for entry in body.get('entry', []):
                        for change in entry.get('changes', []):
                            value = change.get('value', {})
                            if 'messages' in value and value['messages']:
                                message_id = value['messages'][0].get('id')
                                break
                
                # Verificar se há mensagens reais (não apenas status) antes de salvar no outbox
                has_user_messages = False
                logger.info(f"🔍 DEBUG: Verificando has_user_messages para body: {body}")
                if 'entry' in body:
                    for entry in body.get('entry', []):
                        logger.info(f"🔍 DEBUG: Processando entry: {entry}")
                        for change in entry.get('changes', []):
                            logger.info(f"🔍 DEBUG: Processando change: {change}")
                            messages = change.get('value', {}).get('messages')
                            logger.info(f"🔍 DEBUG: Messages encontradas: {messages}")
                            if messages:
                                has_user_messages = True
                                logger.info(f"🔍 DEBUG: has_user_messages = True!")
                                break
                        if has_user_messages:
                            break
                
                logger.info(f"🔍 DEBUG: RESULTADO FINAL has_user_messages = {has_user_messages}")
                
                if has_user_messages:
                    # Salvar atomicamente no banco + outbox apenas para mensagens de usuários
                    outbox_saved = db_manager.save_webhook_with_outbox('webhook_received', body, message_id)
                    if outbox_saved:
                        logger.info("✅ Webhook com mensagens de usuário salvo no banco + outbox atomicamente")
                    else:
                        logger.warning("⚠️ Falha ao salvar webhook no outbox")
                else:
                    # Apenas status updates - salvar no banco mas não no outbox
                    if db_manager and db_manager.enabled:
                        try:
                            db_manager.save_webhook_event('webhook_status_only', body)
                            logger.info("📊 Webhook apenas com status salvo no banco (sem outbox)")
                        except Exception as save_error:
                            logger.warning(f"⚠️ Falha ao salvar webhook de status: {save_error}")
                    else:
                        logger.debug("📊 Webhook apenas com status - banco desabilitado")
            else:
                logger.debug("Database desabilitado - webhook não salvo")
        except Exception as outbox_error:
            logger.error(f"❌ Erro crítico ao salvar no outbox: {outbox_error}")
            # Fallback: tentar salvar direto no RabbitMQ como antes
            try:
                if rabbitmq_manager and rabbitmq_manager.enabled:
                    rabbitmq_saved = rabbitmq_manager.publish_webhook_event('webhook_received', body)
                    if rabbitmq_saved:
                        logger.warning("⚠️ Fallback: Evento salvo diretamente no RabbitMQ")
            except Exception as fallback_error:
                logger.error(f"❌ Erro no fallback RabbitMQ: {fallback_error}")
        
        # Processa o webhook apenas se for válido
        webhook_processed = False
        
        # Verifica se é um evento do WhatsApp
        if 'object' in body and body['object'] == 'whatsapp_business_account':
            try:
                # Processa cada entrada do webhook
                for entry in body.get('entry', []):
                    # Processa cada mudança na entrada
                    for change in entry.get('changes', []):
                        # Verifica se é uma mudança de valor
                        if change.get('value'):
                            # Processa mensagens
                            if 'messages' in change['value']:
                                for message in change['value']['messages']:
                                    process_message_safe(message)
                                    webhook_processed = True
                            
                            # Processa status de entrega
                            if 'statuses' in change['value']:
                                for status in change['value']['statuses']:
                                    process_status_safe(status)
                                    webhook_processed = True
                
                if webhook_processed:
                    logger.info("Webhook processado com sucesso")
                else:
                    logger.info("Webhook recebido mas nenhum evento processado")
                    
            except Exception as processing_error:
                logger.error(f"Erro no processamento do webhook: {processing_error}")
                # Continua mesmo com erro de processamento
        else:
            logger.warning(f"Webhook recebido com object inválido: {body.get('object', 'N/A')}")
        
        # SEMPRE retorna sucesso para o WhatsApp (evita reenvios)
        return jsonify({"status": "success", "message": "Webhook processado"}), 200
        
    except json.JSONDecodeError as json_error:
        logger.error(f"Erro ao decodificar JSON do webhook: {json_error}")
        return jsonify({"status": "error", "message": "JSON inválido"}), 400
        
    except Exception as e:
        logger.error(f"Erro crítico no webhook: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Tenta salvar o erro (mas não falha se não conseguir)
        try:
            if db_manager and db_manager.enabled:
                error_data = {
                    'error': str(e),
                    'request_body': request.get_data(as_text=True),
                    'headers': dict(request.headers),
                    'traceback': traceback.format_exc()
                }
                db_manager.save_webhook_event('webhook_critical_error', error_data)
        except:
            logger.warning("Não foi possível salvar erro no banco")
        
        # Retorna erro 500 apenas para erros realmente críticos
        return jsonify({
            "status": "error", 
            "message": "Erro interno do servidor",
            "error_id": str(int(time.time()))  # ID para rastreamento
        }), 500

def process_message_safe(message):
    """
    Processa uma mensagem recebida do WhatsApp de forma segura
    """
    try:
        logger.info(f"Processando mensagem: {json.dumps(message, indent=2)}")
        
        # PRIORITÁRIO: Salvar no RabbitMQ
        # DESABILITADO: webhook_received já processa todas as mensagens, evitando duplicação
        # try:
        #     if rabbitmq_manager and rabbitmq_manager.enabled:
        #         rabbitmq_manager.publish_webhook_event('message_received', message)
        # except Exception as rabbitmq_error:
        #     logger.warning(f"Falha ao salvar mensagem no RabbitMQ: {rabbitmq_error}")
        logger.info(f"✅ Processamento message_received desabilitado - webhook_received já processa tudo")
        
        # Não salva no banco aqui - será salvo pelo worker para evitar duplicação
        
        # Processa a mensagem independente do banco
        message_type = message.get('type', 'unknown')
        from_number = message.get('from')
        timestamp = message.get('timestamp')
        
        logger.info(f"Mensagem do tipo {message_type} de {from_number} em {timestamp}")
        
        # Aqui você pode implementar a lógica para processar a mensagem
        # Por exemplo: salvar no banco de dados, responder automaticamente, etc.
        
    except Exception as e:
        logger.error(f"Erro ao processar mensagem (não crítico): {e}")

def process_status_safe(status):
    """
    Processa um status de entrega do WhatsApp de forma segura
    """
    try:
        logger.info(f"Processando status: {json.dumps(status, indent=2)}")
        
        # PRIORITÁRIO: Salvar no RabbitMQ
        try:
            if rabbitmq_manager and rabbitmq_manager.enabled:
                rabbitmq_manager.publish_webhook_event('status_update', status)
        except Exception as rabbitmq_error:
            logger.warning(f"Falha ao salvar status no RabbitMQ: {rabbitmq_error}")
        
        # Não salva no banco aqui - será salvo pelo worker para evitar duplicação
        
        # Processa o status independente do banco
        status_type = status.get('status')
        message_id = status.get('id')
        timestamp = status.get('timestamp')
        
        logger.info(f"Status {status_type} para mensagem {message_id} em {timestamp}")
        
        # Aqui você pode implementar a lógica para processar o status
        # Por exemplo: atualizar status no banco de dados, notificar usuário, etc.
        
    except Exception as e:
        logger.error(f"Erro ao processar status (não crítico): {e}")

# ===========================
# ENDPOINTS DO BOT CHATGPT
# ===========================

@app.route('/bot/oauth/start')
def start_oauth():
    """Inicia processo OAuth do WhatsApp"""
    try:
        # Importar aqui para evitar problemas de inicialização
        from whatsapp_service import whatsapp_service
        
        # URL de redirect (deve ser configurada no app Facebook)
        # Usar domínio público configurado
        redirect_uri = "https://pluggyapi.pluggerbi.com/bot/oauth/callback"
        
        # Gerar URL OAuth
        oauth_url = whatsapp_service.get_oauth_url(redirect_uri)
        
        # Página simples para iniciar OAuth
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Autorização WhatsApp Bot</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                .button { background-color: #25D366; color: white; padding: 15px 30px; 
                         text-decoration: none; border-radius: 5px; font-size: 18px; }
                .button:hover { background-color: #128C7E; }
            </style>
        </head>
        <body>
            <h1>🤖 WhatsApp Bot - Autorização</h1>
            <p>Para ativar o bot ChatGPT, é necessário autorizar o acesso ao WhatsApp Business.</p>
            <br>
            <a href="{{ oauth_url }}" class="button">
                📱 Autorizar WhatsApp
            </a>
            <br><br>
            <p><small>Você será redirecionado para o Facebook para autorizar as permissões.</small></p>
        </body>
        </html>
        """
        
        return render_template_string(html, oauth_url=oauth_url)
        
    except Exception as e:
        logger.error(f"Erro ao iniciar OAuth: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/bot/oauth/callback')
def oauth_callback():
    """Callback OAuth do WhatsApp"""
    try:
        # Importar aqui para evitar problemas de inicialização
        from whatsapp_service import whatsapp_service
        
        # Obter código da query string
        code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            logger.error(f"Erro OAuth: {error}")
            return f"❌ Erro na autorização: {error}", 400
        
        if not code:
            return "❌ Código de autorização não recebido", 400
        
        # URL de redirect (deve ser a mesma usada no início)  
        # Usar domínio público configurado
        redirect_uri = "https://pluggyapi.pluggerbi.com/bot/oauth/callback"
        
        # Trocar código por token
        result = whatsapp_service.exchange_code_for_token(code, redirect_uri)
        
        if result["success"]:
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Autorização Concluída</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; 
                           background-color: #f0f8ff; }
                    .success { color: #25D366; font-size: 24px; }
                    .info { background-color: white; padding: 20px; border-radius: 10px; 
                           margin: 20px auto; max-width: 600px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                </style>
            </head>
            <body>
                <h1 class="success">✅ Autorização Concluída!</h1>
                <div class="info">
                    <p>🤖 O bot ChatGPT foi autorizado com sucesso!</p>
                    <p>📱 Agora você pode enviar mensagens para o WhatsApp e o bot responderá automaticamente.</p>
                    <br>
                    <p><strong>Token salvo no banco de dados.</strong></p>
                    <p><small>Você pode fechar esta janela.</small></p>
                </div>
            </body>
            </html>
            """
            return html
        else:
            return f"❌ Erro ao obter token: {result['error']}", 500
        
    except Exception as e:
        logger.error(f"Erro no callback OAuth: {e}")
        return f"❌ Erro interno: {str(e)}", 500

@app.route('/bot/config/system-prompt', methods=['GET', 'POST'])
def manage_system_prompt():
    """Gerencia o prompt do sistema do ChatGPT"""
    try:
        if request.method == 'GET':
            # Buscar prompt atual
            system_prompt = db_manager.get_config('system_prompt')
            
            if system_prompt:
                return jsonify({
                    "status": "success",
                    "system_prompt": system_prompt
                })
            else:
                return jsonify({
                    "status": "success",
                    "system_prompt": {
                        "role": "system",
                        "content": "Prompt não configurado"
                    }
                })
        
        elif request.method == 'POST':
            # Definir novo prompt
            data = request.get_json()
            
            if not data or 'content' not in data:
                return jsonify({"error": "Campo 'content' é obrigatório"}), 400
            
            system_prompt = {
                "role": "system",
                "content": data['content']
            }
            
            success = db_manager.set_config(
                'system_prompt',
                system_prompt,
                'Prompt do sistema para ChatGPT'
            )
            
            if success:
                return jsonify({
                    "status": "success",
                    "message": "Prompt atualizado com sucesso",
                    "system_prompt": system_prompt
                })
            else:
                return jsonify({"error": "Falha ao salvar prompt"}), 500
                
    except Exception as e:
        logger.error(f"Erro ao gerenciar system prompt: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/bot/status')
def bot_status():
    """Verifica status do bot com timeouts e tratamento robusto de erros"""
    try:
        # Verificar token WhatsApp com timeout
        whatsapp_ready = False
        try:
            # Importar aqui para evitar problemas de inicialização
            from whatsapp_service import whatsapp_service
            
            # Verificar token WhatsApp com timeout limitado
            token = whatsapp_service.get_access_token()
            whatsapp_ready = token is not None
            
        except Exception as whatsapp_error:
            logger.warning(f"Erro ao verificar token WhatsApp: {whatsapp_error}")
            whatsapp_ready = False
        
        # Verificar system prompt com timeout e fallback
        chatgpt_ready = False
        try:
            # Verificar se o banco está acessível primeiro
            if db_manager.enabled:
                # Usar método rápido que não tenta reconectar
                system_prompt = db_manager.get_config_fast('system_prompt')
                chatgpt_ready = system_prompt is not None
            else:
                logger.info("Banco desabilitado - usando configuração padrão")
                chatgpt_ready = True  # Assume que tem prompt padrão
                
        except Exception as db_error:
            logger.warning(f"Erro ao verificar system prompt: {db_error}")
            # Em caso de erro no banco, assume que o ChatGPT pode funcionar com prompt padrão
            chatgpt_ready = True
        
        # Status geral
        bot_ready = whatsapp_ready and chatgpt_ready
        
        # Montar resposta
        response = {
            "status": "ready" if bot_ready else "configuration_needed",
            "whatsapp_authorized": whatsapp_ready,
            "chatgpt_configured": chatgpt_ready,
            "ready": bot_ready,
            "database_connected": db_manager.enabled and db_manager.connection is not None,
            "timestamp": datetime.now().isoformat()
        }
        
        # Adicionar OAuth URL se WhatsApp não estiver autorizado
        if not whatsapp_ready:
            response["oauth_url"] = f"{request.host_url}bot/oauth/start"
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Erro crítico ao verificar status do bot: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "whatsapp_authorized": False,
            "chatgpt_configured": False,
            "ready": False,
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/bot/token/status')
def token_status():
    """Verifica status detalhado do token WhatsApp"""
    try:
        from whatsapp_service import whatsapp_service
        
        token_status = whatsapp_service.get_token_status()
        return jsonify(token_status)
        
    except Exception as e:
        logger.error(f"Erro ao verificar status do token: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/bot/token/refresh', methods=['POST'])
def refresh_token():
    """Força renovação do token WhatsApp"""
    try:
        from whatsapp_service import whatsapp_service
        
        success = whatsapp_service.refresh_token_if_needed()
        
        if success:
            token_status = whatsapp_service.get_token_status()
            return jsonify({
                "success": True,
                "message": "Token verificado/renovado com sucesso",
                "token_status": token_status
            })
        else:
            return jsonify({
                "success": False,
                "message": "Falha ao renovar token - autorização OAuth necessária",
                "oauth_url": f"{request.host_url}bot/oauth/start"
            }), 400
            
    except Exception as e:
        logger.error(f"Erro ao renovar token: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/debug/database-status', methods=['GET'])
def debug_database_status():
    """
    Endpoint de diagnóstico para verificar status do banco de dados
    """
    try:
        import os
        from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_ENABLED
        
        # Verificar variáveis de ambiente
        env_db_enabled = os.getenv('DB_ENABLED', 'True')
        
        # Teste de conexão
        db_connection_status = db_manager.get_connection_status()
        
        diagnostic_info = {
            "database_status": {
                "db_manager_enabled": db_manager.enabled,
                "env_db_enabled_raw": env_db_enabled,
                "env_db_enabled_parsed": env_db_enabled.lower() == 'true',
                "connection_status": db_connection_status,
                "config": {
                    "host": DB_HOST,
                    "port": DB_PORT,
                    "database": DB_NAME,
                    "user": DB_USER
                }
            },
            "diagnosis": {
                "issue": "GET /channels returning 503 error",
                "cause": "Database manager is disabled",
                "solutions": []
            }
        }
        
        # Adicionar soluções baseadas no diagnóstico
        if not db_manager.enabled:
            if env_db_enabled.lower() != 'true':
                diagnostic_info["diagnosis"]["solutions"].append({
                    "problem": f"Environment variable DB_ENABLED='{env_db_enabled}' is not 'true'",
                    "solution": "Set DB_ENABLED environment variable to 'true' (case sensitive)"
                })
            
            if db_connection_status == "disconnected":
                diagnostic_info["diagnosis"]["solutions"].append({
                    "problem": "Cannot connect to database",
                    "solution": "Check database connection parameters and network connectivity"
                })
        
        return jsonify(diagnostic_info), 200
        
    except Exception as e:
                 return jsonify({
             "error": f"Diagnostic failed: {str(e)}",
             "status": "error"
         }), 500

@app.route('/debug/database-enable', methods=['POST'])
def debug_database_enable():
    """
    Endpoint de debug para forçar habilitação do banco (temporário)
    """
    try:
        data = request.get_json()
        force_enable = data.get('force_enable', False) if data else False
        
        if force_enable:
            # Forçar habilitação temporária
            db_manager.enabled = True
            
            # Testar conexão
            connection_test = db_manager.connect()
            
            return jsonify({
                "message": "Database temporarily enabled",
                "enabled": db_manager.enabled,
                "connection_test": connection_test,
                "warning": "This is a temporary fix - check environment variables"
            }), 200
        else:
            return jsonify({
                "error": "Missing force_enable parameter",
                "usage": "POST with JSON: {'force_enable': true}"
            }), 400
            
    except Exception as e:
        return jsonify({
            "error": f"Enable failed: {str(e)}",
            "status": "error"
        }), 500



# ==================== INTENTS ENDPOINTS ====================

@app.route('/bots/<bot_id>/intents', methods=['GET'])
@jwt_required
def get_bot_intents(bot_id):
    """
    Lista todas as intents de um bot específico
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar formato do UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "Bot ID deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta do usuário
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Buscar intents do bot
        intents = db_manager.get_intents_by_bot(bot_id)
        
        logger.info(f"✅ Usuário {request.current_user.get('sub')} listou {len(intents)} intents do bot {bot_id}")
        
        return jsonify({
            "status": "success",
            "intents": intents,
            "total": len(intents),
            "bot_id": bot_id
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_bot_intents: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/intents', methods=['POST'])
@jwt_required
def create_intent(bot_id):
    """
    Cria uma nova intent para um bot
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar formato do UUID do bot
        try:
            uuid.UUID(bot_id)
        except ValueError:
            return jsonify({
                "error": "Bot ID deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta do usuário
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Obter dados da requisição
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Validar campos obrigatórios
        intent_id = data.get('id')
        if not intent_id:
            return jsonify({
                "error": "Campo 'id' é obrigatório",
                "status": "error"
            }), 400
        
        # Validar formato do UUID
        try:
            uuid.UUID(intent_id)
        except ValueError:
            return jsonify({
                "error": "Campo 'id' deve ser um UUID válido",
                "status": "error"
            }), 400
        
        # Validar campos opcionais
        name = data.get('name')
        if name is not None and len(name) > 50:
            return jsonify({
                "error": "Campo 'name' deve ter no máximo 50 caracteres",
                "status": "error"
            }), 400
        
        intention = data.get('intention')
        active = data.get('active', True)
        prompt = data.get('prompt')
        function_id = data.get('function_id')
        
        # Validar function_id se fornecido
        if function_id is not None and len(function_id) > 150:
            return jsonify({
                "error": "Campo 'function_id' deve ter no máximo 150 caracteres",
                "status": "error"
            }), 400
        
        # Verificar se a intent já existe
        existing_intent = db_manager.get_intent(intent_id, bot_id)
        if existing_intent:
            return jsonify({
                "error": "Intent com este ID já existe para este bot",
                "status": "error"
            }), 409
        
        # Inserir intent
        success = db_manager.insert_intent(
            intent_id=intent_id,
            bot_id=bot_id,
            name=name,
            intention=intention,
            active=active,
            prompt=prompt,
            function_id=function_id
        )
        
        if not success:
            return jsonify({
                "error": "Falha ao criar intent",
                "status": "error"
            }), 500
        
        # Buscar a intent criada para retornar
        created_intent = db_manager.get_intent(intent_id, bot_id)
        
        logger.info(f"✅ Usuário {request.current_user.get('sub')} criou intent {intent_id} para bot {bot_id}")
        
        return jsonify({
            "message": "Intent criada com sucesso",
            "status": "success",
            "intent": created_intent
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint create_intent: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/intents/<intent_id>', methods=['GET'])
@jwt_required
def get_intent_by_id(bot_id, intent_id):
    """
    Busca uma intent específica pelo ID
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar formato dos UUIDs
        try:
            uuid.UUID(bot_id)
            uuid.UUID(intent_id)
        except ValueError:
            return jsonify({
                "error": "Bot ID e Intent ID devem ser UUIDs válidos",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta do usuário
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Buscar intent
        intent = db_manager.get_intent(intent_id, bot_id)
        if not intent:
            return jsonify({
                "error": "Intent não encontrada",
                "status": "error"
            }), 404
        
        logger.info(f"✅ Usuário {request.current_user.get('sub')} acessou intent {intent_id} do bot {bot_id}")
        
        return jsonify({
            "status": "success",
            "intent": intent
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_intent_by_id: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/intents/<intent_id>', methods=['PUT'])
@jwt_required
def update_intent(bot_id, intent_id):
    """
    Atualiza uma intent existente
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar formato dos UUIDs
        try:
            uuid.UUID(bot_id)
            uuid.UUID(intent_id)
        except ValueError:
            return jsonify({
                "error": "Bot ID e Intent ID devem ser UUIDs válidos",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta do usuário
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se a intent existe
        existing_intent = db_manager.get_intent(intent_id, bot_id)
        if not existing_intent:
            return jsonify({
                "error": "Intent não encontrada",
                "status": "error"
            }), 404
        
        # Obter dados da requisição
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        # Preparar parâmetros de atualização
        update_params = {}
        
        if 'name' in data:
            if data['name'] is not None and len(data['name']) > 50:
                return jsonify({
                    "error": "Campo 'name' deve ter no máximo 50 caracteres",
                    "status": "error"
                }), 400
            update_params['name'] = data['name']
        
        if 'intention' in data:
            update_params['intention'] = data['intention']
        
        if 'active' in data:
            update_params['active'] = data['active']
        
        if 'prompt' in data:
            update_params['prompt'] = data['prompt']
        
        if 'function_id' in data:
            if data['function_id'] is not None and len(data['function_id']) > 150:
                return jsonify({
                    "error": "Campo 'function_id' deve ter no máximo 150 caracteres",
                    "status": "error"
                }), 400
            update_params['function_id'] = data['function_id']
        
        if not update_params:
            return jsonify({
                "error": "Nenhum campo para atualizar foi fornecido",
                "status": "error"
            }), 400
        
        # Atualizar intent
        success = db_manager.update_intent(
            intent_id=intent_id,
            bot_id=bot_id,
            **update_params
        )
        
        if not success:
            return jsonify({
                "error": "Falha ao atualizar intent",
                "status": "error"
            }), 500
        
        # Buscar intent atualizada
        updated_intent = db_manager.get_intent(intent_id, bot_id)
        
        logger.info(f"✅ Usuário {request.current_user.get('sub')} atualizou intent {intent_id} do bot {bot_id}")
        
        return jsonify({
            "message": "Intent atualizada com sucesso",
            "status": "success",
            "intent": updated_intent,
            "updated_fields": list(update_params.keys())
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint update_intent: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

@app.route('/bots/<bot_id>/intents/<intent_id>', methods=['DELETE'])
@jwt_required
def delete_intent(bot_id, intent_id):
    """
    Deleta uma intent permanentemente
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Validar formato dos UUIDs
        try:
            uuid.UUID(bot_id)
            uuid.UUID(intent_id)
        except ValueError:
            return jsonify({
                "error": "Bot ID e Intent ID devem ser UUIDs válidos",
                "status": "error"
            }), 400
        
        # Verificar se o bot existe e pertence à conta do usuário
        bot = db_manager.get_bot(bot_id)
        if not bot:
            return jsonify({
                "error": "Bot não encontrado",
                "status": "error"
            }), 404
        
        if bot['account_id'] != account_id:
            return jsonify({
                "error": "Acesso negado - bot não pertence à sua conta",
                "status": "error"
            }), 403
        
        # Verificar se a intent existe
        existing_intent = db_manager.get_intent(intent_id, bot_id)
        if not existing_intent:
            return jsonify({
                "error": "Intent não encontrada",
                "status": "error"
            }), 404
        
        # Deletar intent
        success = db_manager.delete_intent(intent_id, bot_id)
        
        if not success:
            return jsonify({
                "error": "Falha ao deletar intent",
                "status": "error"
            }), 500
        
        logger.info(f"✅ Usuário {request.current_user.get('sub')} deletou intent {intent_id} do bot {bot_id}")
        
        return jsonify({
            "message": "Intent deletada permanentemente com sucesso",
            "status": "success",
            "intent_id": intent_id,
            "bot_id": bot_id,
            "action": "deletada permanentemente"
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint delete_intent: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500

# ==================== BOTS FUNCTIONS ACTIONS ENDPOINTS ====================

@app.route('/bots/functions/actions', methods=['GET'])
@jwt_required
def get_bots_functions_actions():
    """
    Lista todas as ações disponíveis para funções de bots
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT (para logs de auditoria)
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Parâmetro opcional para filtrar por tipo de integração
        integration_type = request.args.get('integration_type')
        
        # Buscar ações disponíveis
        actions = db_manager.get_bots_functions_actions(integration_type=integration_type)
        
        # Log de auditoria
        user_id = request.current_user.get('sub')
        user_email = request.current_user.get('email', 'unknown')
        filter_info = f" (filtradas por: {integration_type})" if integration_type else ""
        logger.info(f"✅ Usuário {user_id} ({user_email}) listou {len(actions)} ações de funções{filter_info}")
        
        return jsonify({
            "status": "success",
            "actions": actions,
            "total": len(actions),
            "filter": {
                "integration_type": integration_type
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no endpoint get_bots_functions_actions: {e}")
        return jsonify({
            "error": f"Erro interno do servidor: {str(e)}",
            "status": "error"
        }), 500



# ==================== CHANNELS ENDPOINTS ====================

if __name__ == '__main__':
    # Configurar logging detalhado
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/tmp/app.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # Log detalhado da inicialização
    logger.info("=" * 50)
    logger.info("🚀 INICIANDO APLICAÇÃO WHATSAPP WEBHOOK")
    logger.info("=" * 50)
    logger.info(f"Ambiente: {os.getenv('KUBERNETES_SERVICE_HOST', 'LOCAL')}")
    logger.info(f"Host: {HOST}, Port: {PORT}")
    logger.info(f"Debug: {DEBUG}")
    logger.info(f"Log Level: {LOG_LEVEL}")
    
    # Tentar conectar ao banco (mas não falhar se não conseguir)
    if db_manager.enabled:
        logger.info("📊 Tentando conectar ao banco de dados...")
        logger.info(f"DB Config: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        
        db_connected = db_manager.connect(initial_retry=True)
        
        if db_connected:
            logger.info("✅ Conectado ao banco de dados com sucesso!")
            # Criar tabela se não existir
            if db_manager.create_table_if_not_exists():
                logger.info("✅ Tabela de logs verificada/criada")
                
                # Executar migração de dados existentes
                # TEMPORÁRIO: Comentado devido a erro na migração
                # logger.info("🔄 Executando migração de dados existentes...")
                # migration_success = db_manager.migrate_existing_data()
                # if migration_success:
                #     logger.info("✅ Migração de dados concluída com sucesso")
                # else:
                #     logger.warning("⚠️ Migração de dados falhou ou não foi necessária")
            else:
                logger.warning("⚠️ Não foi possível criar/verificar tabela de logs")
        else:
            logger.warning("⚠️ Não foi possível conectar ao banco de dados na inicialização")
            logger.info("A aplicação continuará funcionando, mas os logs não serão salvos")
    else:
        logger.info("📊 Banco de dados desabilitado")
    
    # Tentar conectar ao RabbitMQ
    if rabbitmq_manager.enabled:
        logger.info("🐰 Tentando conectar ao RabbitMQ...")
        logger.info(f"RabbitMQ Config: {RABBITMQ_HOST}:{RABBITMQ_PORT}")
        
        rabbitmq_connected = rabbitmq_manager.connect()
        
        if rabbitmq_connected:
            logger.info("✅ Conectado ao RabbitMQ com sucesso!")
            logger.info("📬 Filas declaradas e prontas para uso")
        else:
            logger.warning("⚠️ Não foi possível conectar ao RabbitMQ na inicialização")
            logger.info("A aplicação continuará funcionando, mas sem mensageria")
    else:
        logger.info("🐰 RabbitMQ desabilitado")
    
@app.route('/api/conversations/search', methods=['POST'])
@jwt_required
def search_conversations():
    """
    API para pesquisar conversas por termos nas mensagens
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter dados do JSON
        data = request.get_json()
        
        # Validação dos dados obrigatórios
        if not data:
            return jsonify({
                "error": "Dados JSON são obrigatórios",
                "status": "error"
            }), 400
        
        if 'search_term' not in data or not data['search_term']:
            return jsonify({
                "error": "Campo 'search_term' é obrigatório",
                "status": "error"
            }), 400
        
        search_term = data['search_term'].strip()
        
        if len(search_term) < 3:
            return jsonify({
                "error": "Termo de busca deve ter pelo menos 3 caracteres",
                "status": "error"
            }), 400
        
        # Parâmetros opcionais
        limit = data.get('limit', 50)
        offset = data.get('offset', 0)
        account_id = data.get('account_id')  # Filtrar por conta específica
        
        # Validar limit
        if limit > 100:
            limit = 100
        
        logger.info(f"🔍 Pesquisando conversas com termo: '{search_term}' (limit: {limit}, offset: {offset})")
        
        # Buscar conversas com o termo
        conversations = db_manager.search_conversations_by_message(
            search_term=search_term,
            limit=limit,
            offset=offset,
            account_id=account_id
        )
        
        # Contar total de resultados para paginação
        total_count = db_manager.count_conversations_by_message(
            search_term=search_term,
            account_id=account_id
        )
        
        return jsonify({
            "success": True,
            "data": {
                "conversations": conversations,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_next": offset + limit < total_count
                },
                "search_info": {
                    "term": search_term,
                    "results_count": len(conversations)
                }
            },
            "status": "success"
        })
        
    except Exception as e:
        logger.error(f"❌ Erro na pesquisa de conversas: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "status": "error"
        }), 500

@app.route('/api/conversations/recent', methods=['GET'])
@jwt_required
def get_recent_conversations():
    """
    API para buscar conversas recentes com contatos para carregamento inicial do frontend
    Retorna as 50 conversas mais recentes (ativas e encerradas) com dados do contato
    """
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            return jsonify({
                "error": "Banco de dados não está habilitado",
                "status": "error"
            }), 503
        
        # Obter account_id do token JWT
        account_id = get_account_id_from_token()
        if not account_id:
            return jsonify({
                "error": "Token JWT não contém account_id válido",
                "status": "error"
            }), 400
        
        # Parâmetros opcionais
        limit = request.args.get('limit', 50, type=int)
        if limit > 100:
            limit = 100  # Máximo de 100 conversas
        
        include_closed = request.args.get('include_closed', 'true').lower() == 'true'
        
        logger.info(f"📋 Buscando conversas recentes para account {account_id} (limit: {limit}, include_closed: {include_closed})")
        
        # Buscar conversas recentes com dados completos
        def _get_recent_conversations_operation(connection):
            cursor = connection.cursor(dictionary=True)
            
            # Construir filtro de status
            status_filter = ""
            if not include_closed:
                status_filter = "AND c.status = 'active'"
            
            query = f"""
                SELECT 
                    c.id as conversation_id,
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
                    (SELECT cm.timestamp FROM conversation_message cm WHERE cm.conversation_id = c.id ORDER BY cm.timestamp DESC LIMIT 1) as last_message_time,
                    (SELECT cm.sender FROM conversation_message cm WHERE cm.conversation_id = c.id ORDER BY cm.timestamp DESC LIMIT 1) as last_message_sender
                FROM conversation c
                LEFT JOIN contacts ct ON c.contact_id = ct.id
                LEFT JOIN channels ch ON c.channel_id = ch.id
                LEFT JOIN bots b ON ch.bot_id = b.id
                WHERE ct.account_id = %s {status_filter}
                ORDER BY COALESCE(c.ended_at, c.started_at) DESC
                LIMIT %s
            """
            
            cursor.execute(query, (account_id, limit))
            conversations = cursor.fetchall()
            cursor.close()
            
            # Formatar dados para o frontend
            formatted_conversations = []
            for conv in conversations:
                # Formatar timestamps
                started_at = conv['started_at'].isoformat() if conv['started_at'] else None
                ended_at = conv['ended_at'].isoformat() if conv['ended_at'] else None
                last_message_time = conv['last_message_time'].isoformat() if conv['last_message_time'] else None
                
                formatted_conv = {
                    "conversation_id": conv['conversation_id'],
                    "status": conv['status'],
                    "status_attendance": conv['status_attendance'],
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "message_count": conv['message_count'] or 0,
                    "last_message": {
                        "text": conv['last_message'],
                        "sender": conv['last_message_sender'],
                        "timestamp": last_message_time
                    } if conv['last_message'] else None,
                    "contact": {
                        "id": conv['contact_id'],
                        "name": conv['contact_name'],
                        "phone": conv['contact_phone'],
                        "email": conv['contact_email']
                    },
                    "channel": {
                        "id": conv['channel_id'],
                        "name": conv['channel_name'],
                        "type": conv['channel_type']
                    },
                    "bot": {
                        "name": conv['bot_name'],
                        "agent_name": conv['bot_agent_name']
                    } if conv['bot_name'] else None
                }
                
                formatted_conversations.append(formatted_conv)
            
            return formatted_conversations
        
        conversations = db_manager._execute_with_fresh_connection(_get_recent_conversations_operation)
        
        return jsonify({
            "status": "success",
            "data": {
                "conversations": conversations,
                "pagination": {
                    "limit": limit,
                    "total": len(conversations),
                    "include_closed": include_closed
                },
                "account_id": account_id
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar conversas recentes: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "status": "error"
        }), 500

if __name__ == '__main__':
    # Iniciar servidor Flask
    logger.info(f"🌐 Iniciando servidor Flask em {HOST}:{PORT}")
    
    if USE_SSL and SSL_CERT_PATH and SSL_KEY_PATH:
        logger.info("🔒 Usando SSL/HTTPS")
        app.run(
            host=HOST, 
            port=PORT, 
            debug=DEBUG,
            ssl_context=(SSL_CERT_PATH, SSL_KEY_PATH)
        )
    else:
        logger.info("🌐 Usando HTTP")
        logger.info("🎯 Servidor pronto para receber requisições!")
        app.run(
            host=HOST, 
            port=PORT, 
            debug=DEBUG
        ) 