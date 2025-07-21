import mysql.connector
import json
import logging
import threading
import time
from mysql.connector import Error
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_ENABLED
from datetime import datetime, timezone

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
            
            # Criar tabela config
            create_config_table_query = """
            CREATE TABLE IF NOT EXISTS config (
                id VARCHAR(50) PRIMARY KEY,
                value JSON NOT NULL,
                description VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            cursor.execute(create_config_table_query)
            logger.info("Tabela config verificada/criada com sucesso")
            
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
                    # Extrair dados do JSON - verificar se já é dict ou se é string JSON
                    event_data = record['event_data']
                    
                    # Se é string, fazer parse JSON
                    if isinstance(event_data, str):
                        event_data = json.loads(event_data)
                    # Se já é dict, usar diretamente
                    elif isinstance(event_data, dict):
                        pass
                    else:
                        logger.warning(f"Tipo de dados desconhecido para record {record['id']}: {type(event_data)}")
                        continue
                    
                    message_type = event_data.get('type')
                    id_contact = event_data.get('from')
                    message_content = None
                    
                    # Extrair conteúdo da mensagem baseado no tipo
                    if message_type == 'text':
                        text_data = event_data.get('text')
                        if isinstance(text_data, dict):
                            message_content = text_data.get('body')
                        else:
                            message_content = text_data
                    elif message_type == 'document':
                        doc_data = event_data.get('document')
                        if isinstance(doc_data, dict):
                            message_content = doc_data.get('filename')
                        else:
                            message_content = event_data.get('filename')
                    elif message_type == 'image':
                        img_data = event_data.get('image')
                        if isinstance(img_data, dict):
                            message_content = img_data.get('caption')
                        else:
                            message_content = event_data.get('caption')
                    elif message_type == 'audio':
                        message_content = f"Audio message - {event_data.get('id', 'unknown')}"
                    
                    # Atualizar registro
                    cursor.execute(update_query, (message_type, message_content, id_contact, record['id']))
                    migrated_count += 1
                    
                except (json.JSONDecodeError, KeyError, AttributeError) as e:
                    logger.warning(f"Erro ao processar registro {record['id']}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Erro geral ao processar registro {record['id']}: {e}")
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
            
    def get_config(self, config_id):
        """Busca uma configuração por ID"""
        if not self.enabled:
            logger.warning("Banco de dados desabilitado")
            return None
            
        connection = self._get_connection()
        if not connection:
            logger.warning("Não foi possível conectar ao banco")
            return None
            
        try:
            cursor = connection.cursor(dictionary=True)
            
            query = "SELECT value FROM config WHERE id = %s"
            cursor.execute(query, (config_id,))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return json.loads(result['value']) if isinstance(result['value'], str) else result['value']
            return None
            
        except Error as e:
            logger.error(f"Erro ao buscar configuração {config_id}: {e}")
            return None
    
    def get_config_fast(self, config_id):
        """Busca uma configuração por ID sem tentar reconectar (para verificações rápidas)"""
        if not self.enabled:
            return None
            
        # Verifica apenas se há conexão existente e ativa
        try:
            if (self.connection and 
                hasattr(self.connection, 'is_connected') and 
                self.connection.is_connected()):
                
                cursor = self.connection.cursor(dictionary=True)
                query = "SELECT value FROM config WHERE id = %s"
                cursor.execute(query, (config_id,))
                result = cursor.fetchone()
                cursor.close()
                
                if result:
                    return json.loads(result['value']) if isinstance(result['value'], str) else result['value']
            
            return None
            
        except Exception as e:
            logger.warning(f"Erro rápido ao buscar configuração {config_id}: {e}")
            return None
            
    def set_config(self, config_id, value, description=None):
        """Define uma configuração"""
        if not self.enabled:
            logger.warning("Banco de dados desabilitado")
            return False
            
        connection = self._get_connection()
        if not connection:
            logger.warning("Não foi possível conectar ao banco")
            return False
            
        try:
            cursor = connection.cursor()
            
            upsert_query = """
            INSERT INTO config (id, value, description) 
            VALUES (%s, %s, %s) 
            ON DUPLICATE KEY UPDATE 
                value = VALUES(value),
                description = COALESCE(VALUES(description), description),
                updated_at = CURRENT_TIMESTAMP
            """
            
            json_value = json.dumps(value, ensure_ascii=False)
            cursor.execute(upsert_query, (config_id, json_value, description))
            connection.commit()
            cursor.close()
            
            logger.info(f"Configuração {config_id} salva com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar configuração {config_id}: {e}")
            return False
            
    def get_conversation_context(self, contact_id, limit=10):
        """Busca as últimas mensagens de um contato no dia atual"""
        if not self.enabled:
            logger.warning("Banco de dados desabilitado")
            return []
            
        connection = self._get_connection()
        if not connection:
            logger.warning("Não foi possível conectar ao banco")
            return []
            
        try:
            cursor = connection.cursor(dictionary=True)
            
            query = """
            SELECT type, message, event_type, created_at 
            FROM logs 
            WHERE id_contact = %s 
              AND DATE(created_at) = CURDATE()
              AND event_type IN ('message_received', 'message_sent')
              AND message IS NOT NULL
            ORDER BY created_at DESC 
            LIMIT %s
            """
            
            cursor.execute(query, (contact_id, limit))
            messages = cursor.fetchall()
            cursor.close()
            
            # Inverter para ordem cronológica (mais antiga primeiro)
            return list(reversed(messages))
            
        except Exception as e:
            logger.error(f"Erro ao buscar contexto da conversa para {contact_id}: {e}")
            return []
            
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

    def get_active_conversation(self, contact_id):
        """Busca a conversa ativa de um contato. Retorna o registro ou None."""
        if not self.enabled:
            return None
        connection = self._get_connection()
        if not connection:
            return None
        try:
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT * FROM conversation
                WHERE contact_id = %s AND status = 'active'
                ORDER BY started_at DESC LIMIT 1
            """
            cursor.execute(query, (contact_id,))
            result = cursor.fetchone()
            cursor.close()
            return result
        except Exception as e:
            logger.error(f"Erro ao buscar conversa ativa: {e}")
            return None

    def create_conversation(self, contact_id):
        """Cria uma nova conversa ativa para o contato e retorna o id."""
        if not self.enabled:
            return None
        connection = self._get_connection()
        if not connection:
            return None
        try:
            cursor = connection.cursor()
            query = """
                INSERT INTO conversation (contact_id, status, started_at)
                VALUES (%s, 'active', NOW())
            """
            cursor.execute(query, (contact_id,))
            conversation_id = cursor.lastrowid
            connection.commit()
            cursor.close()
            return conversation_id
        except Exception as e:
            logger.error(f"Erro ao criar conversa: {e}")
            return None

    def close_conversation(self, conversation_id):
        """Fecha uma conversa (status = closed, define ended_at)."""
        if not self.enabled:
            return False
        connection = self._get_connection()
        if not connection:
            return False
        try:
            cursor = connection.cursor()
            query = """
                UPDATE conversation SET status = 'closed', ended_at = NOW()
                WHERE id = %s
            """
            cursor.execute(query, (conversation_id,))
            connection.commit()
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"Erro ao fechar conversa: {e}")
            return False

    def insert_conversation_message(self, conversation_id, message_text, sender, message_type, timestamp=None):
        """Insere uma mensagem na tabela conversation_message."""
        if not self.enabled:
            return False
        connection = self._get_connection()
        if not connection:
            return False
        try:
            cursor = connection.cursor()
            query = """
                INSERT INTO conversation_message (conversation_id, message_text, sender, message_type, timestamp)
                VALUES (%s, %s, %s, %s, %s)
            """
            if not timestamp:
                timestamp = datetime.now(timezone.utc)
            cursor.execute(query, (conversation_id, message_text, sender, message_type, timestamp))
            connection.commit()
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"Erro ao inserir mensagem na conversa: {e}")
            return False

    def insert_conversation_attach(self, conversation_id, file_url, file_type, file_name=None):
        """Insere um anexo na tabela conversation_attach."""
        if not self.enabled:
            return False
        connection = self._get_connection()
        if not connection:
            return False
        try:
            cursor = connection.cursor()
            if file_name is not None:
                query = """
                    INSERT INTO conversation_attach (conversation_id, file_url, file_type, file_name)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query, (conversation_id, file_url, file_type, file_name))
            else:
                query = """
                    INSERT INTO conversation_attach (conversation_id, file_url, file_type)
                    VALUES (%s, %s, %s)
                """
                cursor.execute(query, (conversation_id, file_url, file_type))
            connection.commit()
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"Erro ao inserir anexo na conversa: {e}")
            return False

    def get_conversation_messages(self, conversation_id, limit=10):
        """Busca as últimas mensagens de uma conversa (ordem cronológica)."""
        if not self.enabled:
            return []
        connection = self._get_connection()
        if not connection:
            return []
        try:
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT sender, message_text, message_type, timestamp
                FROM conversation_message
                WHERE conversation_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """
            cursor.execute(query, (conversation_id, limit))
            messages = cursor.fetchall()
            cursor.close()
            # Retornar em ordem cronológica (mais antiga primeiro)
            return list(reversed(messages))
        except Exception as e:
            logger.error(f"Erro ao buscar mensagens da conversa: {e}")
            return []

    def get_last_user_messages(self, conversation_id, limit=1):
        """Busca as últimas mensagens do usuário (sender='user') de uma conversa."""
        if not self.enabled:
            return []
        connection = self._get_connection()
        if not connection:
            return []
        try:
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT sender, message_text, message_type, timestamp
                FROM conversation_message
                WHERE conversation_id = %s AND sender = 'user'
                ORDER BY timestamp DESC
                LIMIT %s
            """
            cursor.execute(query, (conversation_id, limit))
            messages = cursor.fetchall()
            cursor.close()
            return messages
        except Exception as e:
            logger.error(f"Erro ao buscar mensagens do usuário da conversa: {e}")
            return []

    def get_contact(self, contact_id):
        """Busca um contato pelo contact_id na tabela contacts."""
        if not self.enabled:
            return None
        connection = self._get_connection()
        if not connection:
            return None
        try:
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT * FROM contacts WHERE id = %s
            """
            cursor.execute(query, (contact_id,))
            contact = cursor.fetchone()
            cursor.close()
            return contact
        except Exception as e:
            logger.error(f"Erro ao buscar contato: {e}")
            return None

    def has_agent_response_for_contact(self, contact_id):
        """Verifica se o contato já recebeu alguma resposta do agente em qualquer conversa."""
        if not self.enabled:
            return False
        connection = self._get_connection()
        if not connection:
            return False
        try:
            cursor = connection.cursor()
            query = """
                SELECT 1
                FROM conversation_message cm
                JOIN conversation c ON cm.conversation_id = c.id
                WHERE c.contact_id = %s AND cm.sender = 'agent'
                LIMIT 1
            """
            cursor.execute(query, (contact_id,))
            result = cursor.fetchone()
            cursor.close()
            return result is not None
        except Exception as e:
            logger.error(f"Erro ao verificar se contato já tem resposta do agente: {e}")
            return False

# Instância global do gerenciador de banco
db_manager = DatabaseManager() 