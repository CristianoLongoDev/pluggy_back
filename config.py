import os
import socket

# Configurações do Webhook WhatsApp Business
WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN', 'seu_token_de_verificacao_aqui')

# Configurações da aplicação
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))

# Configurações de SSL/HTTPS
USE_SSL = os.getenv('USE_SSL', 'False').lower() == 'true'
SSL_CERT_PATH = os.getenv('SSL_CERT_PATH', 'cert.pem')
SSL_KEY_PATH = os.getenv('SSL_KEY_PATH', 'key.pem')

# Detecção automática do ambiente para configuração do banco MySQL
def detect_environment():
    """Detecta se está rodando localmente ou no Kubernetes"""
    # Verifica se está rodando no Kubernetes (presença de variáveis do K8s)
    if os.getenv('KUBERNETES_SERVICE_HOST') or os.getenv('KUBERNETES_PORT'):
        return 'kubernetes'
    
    # Verifica se está rodando em um container Docker
    if os.path.exists('/.dockerenv'):
        return 'docker'
    
    # Verifica o hostname para detectar ambiente local
    hostname = socket.gethostname()
    if 'localhost' in hostname.lower() or 'desktop' in hostname.lower() or 'laptop' in hostname.lower():
        return 'local'
    
    # Padrão: assume local se não conseguir detectar
    return 'local'

# Configurações do Banco de Dados MySQL com detecção automática de ambiente
ENVIRONMENT = detect_environment()

# IP do banco MySQL - usando IP externo para ambos os ambientes
# O IP interno 10.0.10.75 pode não estar acessível
DEFAULT_DB_HOST = '168.75.106.98'  # IP externo para todos os ambientes

DB_HOST = os.getenv('DB_HOST', DEFAULT_DB_HOST)
DB_PORT = int(os.getenv('DB_PORT', 6446))
DB_NAME = os.getenv('DB_NAME', 'atendimento')
DB_USER = os.getenv('DB_USER', 'atendimento')
DB_PASSWORD = os.getenv('DB_PASSWORD', '8/vLQv98vCmw%Ox1')
DB_ENABLED = os.getenv('DB_ENABLED', 'True').lower() == 'true'

# Configurações de logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO') 