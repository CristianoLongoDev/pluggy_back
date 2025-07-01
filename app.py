from flask import Flask, jsonify, request, send_from_directory
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
    Rota principal - sempre serve o frontend
    """
    return send_from_directory('frontend', 'index.html')

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
            "SELECT * FROM logs ORDER BY created_at DESC LIMIT 100"
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
            SELECT id, event_type, event_data, created_at 
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
        
        # SECUNDÁRIO: Tentativa de salvar evento no banco (não crítico)
        try:
            if db_manager and db_manager.enabled:
                db_manager.save_webhook_event('webhook_received', body)
                logger.debug("Evento salvo no banco com sucesso")
            else:
                logger.debug("Banco desabilitado - evento não salvo")
        except Exception as db_error:
            # Log do erro mas não falha o webhook
            logger.warning(f"Falha ao salvar evento no banco (não crítico): {db_error}")
        
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
        
        # SECUNDÁRIO: Tentativa de salvar mensagem no banco (não crítico)
        try:
            if db_manager and db_manager.enabled:
                db_manager.save_webhook_event('message_received', message)
        except Exception as db_error:
            logger.warning(f"Falha ao salvar mensagem no banco: {db_error}")
        
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
        
        # SECUNDÁRIO: Tentativa de salvar status no banco (não crítico)
        try:
            if db_manager and db_manager.enabled:
                db_manager.save_webhook_event('status_update', status)
        except Exception as db_error:
            logger.warning(f"Falha ao salvar status no banco: {db_error}")
        
        # Processa o status independente do banco
        status_type = status.get('status')
        message_id = status.get('id')
        timestamp = status.get('timestamp')
        
        logger.info(f"Status {status_type} para mensagem {message_id} em {timestamp}")
        
        # Aqui você pode implementar a lógica para processar o status
        # Por exemplo: atualizar status no banco de dados, notificar usuário, etc.
        
    except Exception as e:
        logger.error(f"Erro ao processar status (não crítico): {e}")

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