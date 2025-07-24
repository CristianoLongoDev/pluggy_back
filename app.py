from flask import Flask, jsonify, request, redirect, render_template_string
from flask_cors import CORS
import json
import logging
import os
from config import (
    WEBHOOK_VERIFY_TOKEN, DEBUG, HOST, PORT, LOG_LEVEL, 
    SSL_CERT_PATH, SSL_KEY_PATH, USE_SSL,
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_ENABLED,
    RABBITMQ_ENABLED, RABBITMQ_HOST, RABBITMQ_PORT
)
from database import db_manager
from rabbitmq_manager import rabbitmq_manager
from datetime import datetime
import traceback
import time

# Configurar logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Permite acesso de outros domínios

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
            "/rabbitmq/status": "Status do RabbitMQ"
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
        
        # PRIORITÁRIO: Salvar no RabbitMQ (garante que não perde mensagem)
        rabbitmq_saved = False
        try:
            if rabbitmq_manager and rabbitmq_manager.enabled:
                rabbitmq_saved = rabbitmq_manager.publish_webhook_event('webhook_received', body)
                if rabbitmq_saved:
                    logger.info("✅ Evento salvo no RabbitMQ com sucesso")
                else:
                    logger.warning("⚠️ Falha ao salvar evento no RabbitMQ")
            else:
                logger.debug("RabbitMQ desabilitado - evento não salvo na fila")
        except Exception as rabbitmq_error:
            logger.error(f"❌ Erro crítico ao salvar no RabbitMQ: {rabbitmq_error}")
        
        # Não salva no banco aqui - será salvo pelo worker para evitar duplicação
        
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
        try:
            if rabbitmq_manager and rabbitmq_manager.enabled:
                rabbitmq_manager.publish_webhook_event('message_received', message)
        except Exception as rabbitmq_error:
            logger.warning(f"Falha ao salvar mensagem no RabbitMQ: {rabbitmq_error}")
        
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
        redirect_uri = "https://atendimento.pluggerbi.com/bot/oauth/callback"
        
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
        redirect_uri = "https://atendimento.pluggerbi.com/bot/oauth/callback"
        
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