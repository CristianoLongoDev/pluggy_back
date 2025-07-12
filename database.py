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
        """Cria as tabelas logs e contacts se não existirem"""
        if not self.enabled:
            return False
            
        connection = self._get_connection()
        if not connection:
            return False
            
        try:
            cursor = connection.cursor()
            
            # Criar tabela logs
            create_logs_table_query = """
            CREATE TABLE IF NOT EXISTS logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                type VARCHAR(20) NULL,
                message TEXT NULL,
                id_contact VARCHAR(50) NULL,
                event_data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_event_type (event_type),
                INDEX idx_type (type),
                INDEX idx_id_contact (id_contact),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            cursor.execute(create_logs_table_query)
            logger.info("Tabela logs verificada/criada com sucesso")
            
            # Criar tabela contacts
            create_contacts_table_query = """
            CREATE TABLE IF NOT EXISTS contacts (
                id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_name (name),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            cursor.execute(create_contacts_table_query)
            logger.info("Tabela contacts verificada/criada com sucesso")
            
            connection.commit()
            cursor.close()
            
            # Verificar e adicionar novos campos se necessário
            self._update_table_structure()
            
            return True
            
        except Error as e:
            logger.error(f"Erro ao criar tabelas: {e}")
            return False
    
    def _update_table_structure(self):
        """Atualiza a estrutura da tabela logs adicionando novos campos se necessário"""
        if not self.enabled:
            return False
            
        connection = self._get_connection()
        if not connection:
            return False
            
        try:
            cursor = connection.cursor()
            
            # Verificar se os novos campos existem
            cursor.execute("DESCRIBE logs")
            existing_columns = [column[0] for column in cursor.fetchall()]
            
            # Adicionar campo 'type' se não existir
            if 'type' not in existing_columns:
                cursor.execute("ALTER TABLE logs ADD COLUMN type VARCHAR(20) NULL AFTER event_type")
                cursor.execute("ALTER TABLE logs ADD INDEX idx_type (type)")
                logger.info("Campo 'type' adicionado à tabela logs")
            
            # Adicionar campo 'message' se não existir
            if 'message' not in existing_columns:
                cursor.execute("ALTER TABLE logs ADD COLUMN message TEXT NULL AFTER type")
                logger.info("Campo 'message' adicionado à tabela logs")
            
            # Adicionar campo 'id_contact' se não existir
            if 'id_contact' not in existing_columns:
                cursor.execute("ALTER TABLE logs ADD COLUMN id_contact VARCHAR(50) NULL AFTER message")
                cursor.execute("ALTER TABLE logs ADD INDEX idx_id_contact (id_contact)")
                logger.info("Campo 'id_contact' adicionado à tabela logs")
            
            connection.commit()
            cursor.close()
            
            logger.info("Estrutura da tabela logs atualizada com sucesso")
            return True
            
        except Error as e:
            logger.error(f"Erro ao atualizar estrutura da tabela: {e}")
            return False
    
    def migrate_existing_data(self, limit=1000):
        """Migra dados existentes para os novos campos estruturados"""
        if not self.enabled:
            logger.warning("Banco de dados desabilitado")
            return False
            
        connection = self._get_connection()
        if not connection:
            logger.warning("Não foi possível conectar ao banco")
            return False
            
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Buscar registros que ainda não foram migrados (campos novos são NULL)
            select_query = """
            SELECT id, event_data 
            FROM logs 
            WHERE type IS NULL AND message IS NULL AND id_contact IS NULL
            AND JSON_VALID(event_data) = 1
            LIMIT %s
            """
            
            cursor.execute(select_query, (limit,))
            records = cursor.fetchall()
            
            if not records:
                logger.info("Nenhum registro encontrado para migração")
                return True
            
            logger.info(f"Iniciando migração de {len(records)} registros...")
            
            update_query = """
            UPDATE logs 
            SET type = %s, message = %s, id_contact = %s 
            WHERE id = %s
            """
            
            migrated_count = 0
            
            for record in records:
                try:
                    # Extrair dados do JSON
                    event_data = json.loads(record['event_data'])
                    
                    message_type = event_data.get('type')
                    id_contact = event_data.get('from')
                    message_content = None
                    
                    # Extrair conteúdo da mensagem baseado no tipo
                    if message_type == 'text':
                        message_content = event_data.get('text')
                    elif message_type == 'document':
                        message_content = event_data.get('filename')
                    elif message_type == 'image':
                        message_content = event_data.get('caption')
                    elif message_type == 'audio':
                        message_content = f"Audio message - {event_data.get('id', 'unknown')}"
                    
                    # Atualizar registro
                    cursor.execute(update_query, (message_type, message_content, id_contact, record['id']))
                    migrated_count += 1
                    
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Erro ao processar registro {record['id']}: {e}")
                    continue
            
            connection.commit()
            cursor.close()
            
            logger.info(f"Migração concluída: {migrated_count} registros atualizados")
            return True
            
        except Error as e:
            logger.error(f"Erro durante a migração: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro geral durante a migração: {e}")
            return False
            
    def upsert_contact(self, contact_id, contact_name=None):
        """Insere ou atualiza um contato na tabela contacts"""
        if not self.enabled:
            logger.warning("Banco de dados desabilitado")
            return False
            
        if not contact_id:
            logger.warning("ID do contato é obrigatório")
            return False
            
        connection = self._get_connection()
        if not connection or not hasattr(connection, 'is_connected') or not connection.is_connected():
            logger.warning("Não foi possível conectar ao banco ou conexão inválida")
            return False
            
        try:
            cursor = connection.cursor()
            
            # Usar INSERT ... ON DUPLICATE KEY UPDATE para fazer upsert
            upsert_query = """
            INSERT INTO contacts (id, name) 
            VALUES (%s, %s) 
            ON DUPLICATE KEY UPDATE 
                name = COALESCE(VALUES(name), name),
                updated_at = CURRENT_TIMESTAMP
            """
            
            cursor.execute(upsert_query, (contact_id, contact_name))
            connection.commit()
            cursor.close()
            
            logger.info(f"Contato {contact_id} (nome: {contact_name}) inserido/atualizado com sucesso")
            return True
            
        except Error as e:
            logger.error(f"Erro ao inserir/atualizar contato: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro geral ao inserir/atualizar contato: {e}")
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
            
            # Extrair campos específicos para mensagens do WhatsApp
            message_type = None
            message_content = None
            id_contact = None
            
            # Verificar se é uma mensagem do WhatsApp com estrutura específica
            if isinstance(event_data, dict):
                # CASO 1: Mensagem individual (event_type='message_received')
                if event_type == 'message_received' and 'type' in event_data:
                    # Extrair tipo da mensagem
                    message_type = event_data.get('type')
                    
                    # Extrair ID do contato
                    id_contact = event_data.get('from')
                    
                    # Extrair conteúdo da mensagem baseado no tipo
                    if message_type == 'text':
                        message_content = event_data.get('text', {}).get('body') if isinstance(event_data.get('text'), dict) else event_data.get('text')
                    elif message_type == 'document':
                        message_content = event_data.get('document', {}).get('filename') if isinstance(event_data.get('document'), dict) else event_data.get('filename')
                    elif message_type == 'image':
                        message_content = event_data.get('image', {}).get('caption') if isinstance(event_data.get('image'), dict) else event_data.get('caption')
                    elif message_type == 'audio':
                        # Para audio, vamos gravar apenas o tipo ou algum identificador
                        message_content = f"Audio message - {event_data.get('id', 'unknown')}"
                        
                    logger.info(f"Extraindo dados da mensagem individual - Tipo: {message_type}, De: {id_contact}, Conteúdo: {message_content}")
                    
                # CASO 2: Webhook completo (event_type='webhook_received')
                elif event_type == 'webhook_received' and 'entry' in event_data:
                    # Extrair primeira mensagem encontrada no webhook para os campos estruturados
                    try:
                        # Mapear contatos encontrados (ID -> Nome)
                        contacts_found = {}
                        first_message_found = False
                        
                        for entry in event_data.get('entry', []):
                            for change in entry.get('changes', []):
                                value = change.get('value', {})
                                
                                # Extrair dados dos contatos
                                if 'contacts' in value:
                                    for contact in value['contacts']:
                                        contact_id = contact.get('wa_id')
                                        contact_name = contact.get('profile', {}).get('name')
                                        
                                        if contact_id:
                                            contacts_found[contact_id] = contact_name
                                            logger.info(f"Contato encontrado: {contact_id} - {contact_name}")
                                
                                # Procurar por mensagens
                                if 'messages' in value:
                                    for message in value['messages']:
                                        # Extrair dados da mensagem
                                        msg_type = message.get('type')
                                        msg_from = message.get('from')
                                        
                                        # Adicionar remetente à lista de contatos se não estiver
                                        if msg_from and msg_from not in contacts_found:
                                            contacts_found[msg_from] = None
                                        
                                        # Usar a primeira mensagem encontrada para os logs
                                        if not first_message_found and msg_type:
                                            message_type = msg_type
                                            id_contact = msg_from
                                            
                                            if message_type == 'text':
                                                message_content = message.get('text', {}).get('body') if isinstance(message.get('text'), dict) else message.get('text')
                                            elif message_type == 'document':
                                                message_content = message.get('document', {}).get('filename') if isinstance(message.get('document'), dict) else message.get('filename')
                                            elif message_type == 'image':
                                                message_content = message.get('image', {}).get('caption') if isinstance(message.get('image'), dict) else message.get('caption')
                                            elif message_type == 'audio':
                                                message_content = f"Audio message - {message.get('id', 'unknown')}"
                                            
                                            logger.info(f"Extraindo dados do webhook completo - Tipo: {message_type}, De: {id_contact}, Conteúdo: {message_content}")
                                            first_message_found = True
                        
                        # Salvar/atualizar contatos encontrados
                        for contact_id, contact_name in contacts_found.items():
                            try:
                                self.upsert_contact(contact_id, contact_name)
                            except Exception as contact_error:
                                logger.warning(f"Erro ao salvar contato {contact_id}: {contact_error}")
                        
                        # Se não encontrou mensagem mas encontrou contatos, usar primeiro contato
                        if not first_message_found and contacts_found:
                            id_contact = list(contacts_found.keys())[0]
                            message_type = 'contact_update'
                            message_content = f"Contato atualizado - {contacts_found[id_contact]}"
                            
                    except Exception as e:
                        logger.warning(f"Erro ao extrair dados do webhook completo: {e}")
                        
                # CASO 3: Estrutura antiga ou outros eventos (manter compatibilidade)
                else:
                    # Tentar extrair diretamente (compatibilidade com estruturas antigas)
                    message_type = event_data.get('type')
                    id_contact = event_data.get('from')
                    
                    if message_type == 'text':
                        message_content = event_data.get('text')
                    elif message_type == 'document':
                        message_content = event_data.get('filename')
                    elif message_type == 'image':
                        message_content = event_data.get('caption')
                    elif message_type == 'audio':
                        message_content = f"Audio message - {event_data.get('id', 'unknown')}"
            
            insert_query = """
            INSERT INTO logs (event_type, type, message, id_contact, event_data) 
            VALUES (%s, %s, %s, %s, %s)
            """
            
            # Converter dados para JSON string
            json_data = json.dumps(event_data, ensure_ascii=False)
            
            cursor.execute(insert_query, (event_type, message_type, message_content, id_contact, json_data))
            connection.commit()
            cursor.close()
            
            logger.info(f"Evento {event_type} salvo no banco com sucesso - Tipo: {message_type}, De: {id_contact}, Mensagem: {message_content}")
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