import mysql.connector
import json
import logging
import threading
import time
from mysql.connector import Error
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_ENABLED

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.enabled = DB_ENABLED
        self._lock = threading.Lock()  # Para thread safety
        
    def _get_connection(self, retry_count=0, max_retries=3):
        """Obtém uma conexão ativa, reconectando se necessário"""
        with self._lock:
            try:
                # Verifica se a conexão existe e está ativa
                if (self.connection and 
                    hasattr(self.connection, 'is_connected') and 
                    self.connection.is_connected() and 
                    self.connection.ping(reconnect=False, attempts=1)):
                    return self.connection
                
                # Se não está conectado, tenta reconectar
                if retry_count > 0:
                    logger.info(f"Tentativa {retry_count}/{max_retries} de reconexão...")
                else:
                    logger.info("Conexão perdida, tentando reconectar...")
                
                if self.connection:
                    try:
                        self.connection.close()
                    except:
                        pass
                
                # Cria nova conexão
                self.connection = mysql.connector.connect(
                    host=DB_HOST,
                    port=DB_PORT,
                    database=DB_NAME,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    charset='utf8mb4',
                    collation='utf8mb4_unicode_ci',
                    autocommit=True,  # Auto-commit para evitar problemas
                    pool_size=1,      # Pool simples
                    pool_reset_session=True,
                    connection_timeout=10  # Timeout de conexão
                )
                
                if self.connection and hasattr(self.connection, 'is_connected') and self.connection.is_connected():
                    logger.info("Reconectado ao banco MySQL com sucesso")
                    return self.connection
                else:
                    logger.error("Falha ao reconectar ao banco")
                    return None
                    
            except Error as e:
                logger.error(f"Erro ao obter conexão: {e}")
                
                # Se ainda tem tentativas, aguarda e tenta novamente
                if retry_count < max_retries:
                    wait_time = (retry_count + 1) * 5  # 5s, 10s, 15s
                    logger.info(f"Aguardando {wait_time}s antes da próxima tentativa...")
                    time.sleep(wait_time)
                    return self._get_connection(retry_count + 1, max_retries)
                
                return None
        
    def connect(self, initial_retry=True):
        """Estabelece conexão inicial com o banco MySQL"""
        if not self.enabled:
            logger.info("Banco de dados desabilitado")
            return False
        
        if initial_retry:
            logger.info("Iniciando conexão com o banco MySQL...")
            # Na inicialização, tenta por mais tempo
            max_retries = 10  # 10 tentativas na inicialização
            retry_count = 0
            
            while retry_count < max_retries:
                connection = self._get_connection(retry_count, max_retries)
                if connection:
                    logger.info("Conexão inicial estabelecida com sucesso!")
                    return True
                
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = retry_count * 3  # 3s, 6s, 9s, etc.
                    logger.info(f"Aguardando {wait_time}s antes da próxima tentativa de inicialização...")
                    time.sleep(wait_time)
            
            logger.error("Falha ao conectar no banco após todas as tentativas")
            return False
        else:
            connection = self._get_connection()
            return connection is not None
            
    def disconnect(self):
        """Fecha a conexão com o banco"""
        try:
            with self._lock:
                if self.connection and hasattr(self.connection, 'is_connected') and self.connection.is_connected():
                    self.connection.close()
                    logger.info("Conexão com o banco MySQL fechada")
                else:
                    logger.debug("Conexão já estava fechada ou inválida")
        except Exception as e:
            logger.error(f"Erro ao fechar conexão: {e}")
        
    def create_table_if_not_exists(self):
        """Cria a tabela logs se não existir"""
        if not self.enabled:
            return False
            
        connection = self._get_connection()
        if not connection:
            return False
            
        try:
            cursor = connection.cursor()
            
            create_table_query = """
            CREATE TABLE IF NOT EXISTS logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                event_data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_event_type (event_type),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            cursor.execute(create_table_query)
            connection.commit()
            cursor.close()
            
            logger.info("Tabela logs verificada/criada com sucesso")
            return True
            
        except Error as e:
            logger.error(f"Erro ao criar tabela: {e}")
            return False
            
    def save_webhook_event(self, event_type, event_data):
        """Salva um evento do webhook no banco"""
        if not self.enabled:
            logger.warning("Banco de dados desabilitado")
            return False
            
        connection = self._get_connection()
        if not connection or not hasattr(connection, 'is_connected') or not connection.is_connected():
            logger.warning("Não foi possível conectar ao banco ou conexão inválida")
            return False
            
        try:
            cursor = connection.cursor()
            
            insert_query = """
            INSERT INTO logs (event_type, event_data) 
            VALUES (%s, %s)
            """
            
            # Converter dados para JSON string
            json_data = json.dumps(event_data, ensure_ascii=False)
            
            cursor.execute(insert_query, (event_type, json_data))
            connection.commit()
            cursor.close()
            
            logger.info(f"Evento {event_type} salvo no banco com sucesso")
            return True
            
        except Error as e:
            logger.error(f"Erro ao salvar evento no banco: {e}")
            # Tenta reconectar em caso de erro
            try:
                if self.connection:
                    self.connection.close()
                    self.connection = None
            except:
                pass
            return False
        except Exception as e:
            logger.error(f"Erro geral ao salvar evento no banco: {e}")
            return False
            
    def execute_query(self, query, params=None):
        """Executa uma query genérica com reconexão automática"""
        if not self.enabled:
            return None
            
        connection = self._get_connection()
        if not connection or not hasattr(connection, 'is_connected') or not connection.is_connected():
            logger.warning("Não foi possível conectar ao banco ou conexão inválida")
            return None
            
        try:
            cursor = connection.cursor(dictionary=True)
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
                
            result = cursor.fetchall()
            cursor.close()
            
            return result
            
        except Error as e:
            logger.error(f"Erro ao executar query: {e}")
            # Tenta reconectar em caso de erro
            try:
                if self.connection:
                    self.connection.close()
                    self.connection = None
            except:
                pass
            return None
        except Exception as e:
            logger.error(f"Erro geral ao executar query: {e}")
            return None
            
    def get_connection_status(self):
        """Retorna o status da conexão"""
        if not self.enabled:
            return "disabled"
        
        connection = self._get_connection()
        if connection:
            return "connected"
        else:
            return "disconnected"

# Instância global do gerenciador de banco
db_manager = DatabaseManager() 