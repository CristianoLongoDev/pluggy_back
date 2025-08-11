import mysql.connector
import json
import logging
import threading
import time
import uuid
from mysql.connector import Error
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_ENABLED
from datetime import datetime, timezone
import traceback

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.enabled = DB_ENABLED
        self._lock = threading.Lock()  # Para thread safety
        
    def _create_fresh_connection(self):
        """Cria uma nova conexão fresca para cada operação"""
        if not self.enabled:
            return None
            
        try:
            logger.debug("🔌 Criando nova conexão com o banco...")
            connection = mysql.connector.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci',
                autocommit=True,  # Auto-commit para evitar problemas
                connection_timeout=3,  # Timeout agressivo de 3s
                use_pure=True  # Usar implementação Python pura
            )
            
            if connection and connection.is_connected():
                logger.debug("✅ Nova conexão criada com sucesso")
                return connection
            else:
                logger.error("❌ Falha ao criar conexão")
                return None
                
        except Error as e:
            logger.error(f"❌ Erro ao criar conexão: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro geral ao criar conexão: {e}")
            return None
    
    def _execute_with_fresh_connection(self, operation, *args, **kwargs):
        """Executa uma operação usando conexão fresca"""
        connection = None
        try:
            connection = self._create_fresh_connection()
            if not connection:
                return None
                
            return operation(connection, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"❌ Erro na operação do banco: {e}")
            return None
        finally:
            if connection:
                try:
                    connection.close()
                    logger.debug("🔌 Conexão fechada")
                except:
                    pass
        
    def connect(self, initial_retry=True):
        """Testa se consegue conectar ao banco MySQL"""
        if not self.enabled:
            logger.info("Banco de dados desabilitado")
            return False
        
        logger.info("Testando conexão com o banco MySQL...")
        
        # Fazer teste de conexão simples
        connection = self._create_fresh_connection()
        if connection:
            try:
                connection.close()
                logger.info("✅ Teste de conexão bem-sucedido!")
                return True
            except:
                pass
        
        logger.error("❌ Falha no teste de conexão")
        return False
            
    def disconnect(self):
        """Não há mais conexão persistente para fechar"""
        logger.info("ℹ️ Usando conexões por demanda - nada para desconectar")
        
    def create_table_if_not_exists(self):
        """Cria as tabelas logs e contacts se não existirem"""
        def _create_tables_operation(connection):
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
                email VARCHAR(255) NULL,
                person_id VARCHAR(50) NULL,
                account_id VARCHAR(36) NULL,
                whatsapp_phone_number VARCHAR(20) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_name (name),
                INDEX idx_email (email),
                INDEX idx_person_id (person_id),
                INDEX idx_account_id (account_id),
                INDEX idx_whatsapp_phone_number (whatsapp_phone_number),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            cursor.execute(create_contacts_table_query)
            logger.info("Tabela contacts verificada/criada com sucesso")
            
            # Criar tabela company_relationship
            create_company_relationship_table_query = """
            CREATE TABLE IF NOT EXISTS company_relationship (
                id INT AUTO_INCREMENT PRIMARY KEY,
                domain VARCHAR(255) NOT NULL UNIQUE,
                company_id VARCHAR(50) NOT NULL,
                company_name VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_domain (domain),
                INDEX idx_company_id (company_id),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            cursor.execute(create_company_relationship_table_query)
            logger.info("Tabela company_relationship verificada/criada com sucesso")
            
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
            
            return True
            
        result = self._execute_with_fresh_connection(_create_tables_operation)
        return result is not None
    

    
    def migrate_existing_data(self, limit=1000):
        """Migra dados existentes para os novos campos estruturados"""
        if not self.enabled:
            logger.warning("Banco de dados desabilitado")
            return False
            
        def _migrate_existing_data_operation(connection):
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
            
        result = self._execute_with_fresh_connection(_migrate_existing_data_operation)
        return result is not None
    
    def _get_channel_by_phone(self, display_phone_number):
        """Busca canal pelo display_phone_number"""
        if not self.enabled:
            return None
        
        def _get_channel_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, account_id, bot_id, name, phone_number
                FROM channels 
                WHERE phone_number = %s AND active = 1
                LIMIT 1
            """
            cursor.execute(query, (display_phone_number,))
            result = cursor.fetchone()
            cursor.close()
            return result
        
        return self._execute_with_fresh_connection(_get_channel_operation)
    
    def _get_contact_by_phone_and_account(self, whatsapp_phone_number, account_id):
        """Busca contato pelo whatsapp_phone_number e account_id"""
        if not self.enabled:
            return None
        
        def _get_contact_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, name, email, whatsapp_phone_number, account_id
                FROM contacts 
                WHERE whatsapp_phone_number = %s AND account_id = %s
                LIMIT 1
            """
            cursor.execute(query, (whatsapp_phone_number, account_id))
            result = cursor.fetchone()
            cursor.close()
            return result
        
        return self._execute_with_fresh_connection(_get_contact_operation)
    
    def _get_bot_by_id(self, bot_id):
        """Busca bot pelo ID"""
        if not self.enabled:
            return None
        
        def _get_bot_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, account_id, name, system_prompt
                FROM bots 
                WHERE id = %s
                LIMIT 1
            """
            cursor.execute(query, (bot_id,))
            result = cursor.fetchone()
            cursor.close()
            return result
        
        return self._execute_with_fresh_connection(_get_bot_operation)
            
    def upsert_contact(self, contact_id, contact_name=None, account_id=None, whatsapp_phone_number=None):
        """Insere ou atualiza um contato na tabela contacts"""
        if not self.enabled:
            logger.warning("Banco de dados desabilitado")
            return False
            
        if not contact_id:
            logger.warning("ID do contato é obrigatório")
            return False
            
        def _upsert_contact_operation(connection):
            cursor = connection.cursor()
            
            # Usar INSERT ... ON DUPLICATE KEY UPDATE para fazer upsert
            if account_id and whatsapp_phone_number:
                # Versão completa com todos os campos
                upsert_query = """
                INSERT INTO contacts (id, name, account_id, whatsapp_phone_number) 
                VALUES (%s, %s, %s, %s) 
                ON DUPLICATE KEY UPDATE 
                    name = COALESCE(VALUES(name), name),
                    account_id = COALESCE(VALUES(account_id), account_id),
                    whatsapp_phone_number = COALESCE(VALUES(whatsapp_phone_number), whatsapp_phone_number),
                    updated_at = CURRENT_TIMESTAMP
                """
                cursor.execute(upsert_query, (contact_id, contact_name, account_id, whatsapp_phone_number))
                logger.info(f"Executando INSERT/UPDATE: id={contact_id}, name={contact_name}, account_id={account_id}, phone={whatsapp_phone_number}")
            else:
                # Versão compatível (só atualiza nome se não tiver os outros campos)
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
            
        result = self._execute_with_fresh_connection(_upsert_contact_operation)
        return result is not None
            
    def update_contact_email(self, contact_id, email, account_id=None, whatsapp_phone_number=None):
        """Atualiza o email de um contato na tabela contacts"""
        if not self.enabled:
            return False
            
        def _update_contact_email_operation(connection):
            cursor = connection.cursor()
            
            # Primeiro, verificar se o contato existe
            check_query = "SELECT id FROM contacts WHERE id = %s"
            cursor.execute(check_query, (contact_id,))
            contact_exists = cursor.fetchone()
            
            if not contact_exists:
                # Criar o contato se não existir
                if account_id and whatsapp_phone_number:
                    # Versão completa com todos os campos
                    insert_query = """
                        INSERT INTO contacts (id, email, account_id, whatsapp_phone_number, created_at) 
                        VALUES (%s, %s, %s, %s, NOW())
                    """
                    cursor.execute(insert_query, (contact_id, email, account_id, whatsapp_phone_number))
                else:
                    # Versão compatível
                    insert_query = """
                        INSERT INTO contacts (id, email, created_at) 
                        VALUES (%s, %s, NOW())
                    """
                    cursor.execute(insert_query, (contact_id, email))
                logger.info(f"Contato {contact_id} criado com email {email}")
            else:
                # Atualizar o email do contato existente
                if account_id and whatsapp_phone_number:
                    # Atualizar também os campos adicionais se fornecidos
                    update_query = """
                        UPDATE contacts 
                        SET email = %s, 
                            account_id = COALESCE(%s, account_id),
                            whatsapp_phone_number = COALESCE(%s, whatsapp_phone_number),
                            updated_at = NOW() 
                        WHERE id = %s
                    """
                    cursor.execute(update_query, (email, account_id, whatsapp_phone_number, contact_id))
                else:
                    # Só atualizar email
                    update_query = """
                        UPDATE contacts 
                        SET email = %s, updated_at = NOW() 
                        WHERE id = %s
                    """
                    cursor.execute(update_query, (email, contact_id))
                logger.info(f"Email do contato {contact_id} atualizado para {email}")
            
            connection.commit()
            cursor.close()
            return True
            
        result = self._execute_with_fresh_connection(_update_contact_email_operation)
        return result is not None
        
    def update_contact_person_id(self, contact_id, person_id):
        """Atualiza o person_id de um contato na tabela contacts"""
        if not self.enabled:
            return False
            
        def _update_contact_person_id_operation(connection):
            cursor = connection.cursor()
            
            update_query = """
                UPDATE contacts 
                SET person_id = %s, updated_at = NOW() 
                WHERE id = %s
            """
            cursor.execute(update_query, (person_id, contact_id))
            connection.commit()
            cursor.close()
            
            logger.info(f"Person_id {person_id} atualizado para contato {contact_id}")
            return True
            
        result = self._execute_with_fresh_connection(_update_contact_person_id_operation)
        return result is not None
            
    def get_config(self, config_id):
        """Busca uma configuração por ID"""
        if not self.enabled:
            logger.warning("Banco de dados desabilitado")
            return None
            
        def _get_config_operation(connection):
            cursor = connection.cursor(dictionary=True)
            
            query = "SELECT value FROM config WHERE id = %s"
            cursor.execute(query, (config_id,))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return json.loads(result['value']) if isinstance(result['value'], str) else result['value']
            return None
            
        result = self._execute_with_fresh_connection(_get_config_operation)
        return result
    
    def get_config_fast(self, config_id):
        """Busca uma configuração por ID (agora usa mesmo método que get_config)"""
        return self.get_config(config_id)
            
    def set_config(self, config_id, value, description=None):
        """Define uma configuração"""
        if not self.enabled:
            logger.warning("Banco de dados desabilitado")
            return False
            
        def _set_config_operation(connection):
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
            
        result = self._execute_with_fresh_connection(_set_config_operation)
        return result is not None
            
    def get_conversation_context(self, contact_id, limit=10):
        """Busca as últimas mensagens de um contato no dia atual"""
        if not self.enabled:
            logger.warning("Banco de dados desabilitado")
            return []
            
        def _get_conversation_context_operation(connection):
            cursor = connection.cursor(dictionary=True)
            
            # Buscar conversa ativa do contato
            conversation_query = """
            SELECT id FROM conversation 
            WHERE contact_id = %s AND status = 'active'
            ORDER BY started_at DESC LIMIT 1
            """
            cursor.execute(conversation_query, (contact_id,))
            conversation = cursor.fetchone()
            
            if not conversation:
                cursor.close()
                return []
                
            conversation_id = conversation['id']
            
            # Buscar mensagens da conversa
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
            
            # Inverter para ordem cronológica (mais antiga primeiro)
            return list(reversed(messages))
            
        result = self._execute_with_fresh_connection(_get_conversation_context_operation)
        return result
            
    def save_webhook_event(self, event_type, event_data):
        """Salva um evento do webhook no banco"""
        if not self.enabled:
            logger.warning("Banco de dados desabilitado")
            return False
            
        def _save_webhook_event_operation(connection):
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
                                            logger.info(f"Telefone extraído do webhook: {msg_from}")
                                        
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
                        
                        # Buscar canal pelo display_phone_number para obter account_id e bot_id
                        account_id = None
                        bot_id = None
                        system_prompt = None
                        
                        for entry in event_data.get('entry', []):
                            for change in entry.get('changes', []):
                                value = change.get('value', {})
                                metadata = value.get('metadata', {})
                                display_phone_number = metadata.get('display_phone_number')
                                
                                if display_phone_number:
                                    logger.info(f"Display phone number extraído: {display_phone_number}")
                                    channel = self._get_channel_by_phone(display_phone_number)
                                    if channel:
                                        account_id = channel.get('account_id')
                                        bot_id = channel.get('bot_id')
                                        logger.info(f"Canal encontrado: account_id={account_id}, bot_id={bot_id}")
                                        
                                        # Buscar bot para obter system_prompt
                                        if bot_id:
                                            bot = self._get_bot_by_id(bot_id)
                                            if bot:
                                                system_prompt = bot.get('system_prompt')
                                                logger.info(f"Bot encontrado: {bot['name']}, system_prompt presente: {bool(system_prompt)}")
                                            else:
                                                logger.warning(f"Bot não encontrado para bot_id: {bot_id}")
                                        
                                        break
                                    else:
                                        logger.warning(f"Canal não encontrado para: {display_phone_number}")
                            if account_id:
                                break
                        
                        # Salvar/atualizar contatos encontrados
                        for phone_number, contact_name in contacts_found.items():
                            try:
                                logger.info(f"Processando contato: phone={phone_number}, name={contact_name}, account_id={account_id}")
                                # Buscar se já existe contato com esse telefone + account_id
                                existing_contact = self._get_contact_by_phone_and_account(phone_number, account_id)
                                
                                if existing_contact:
                                    # Atualizar contato existente
                                    logger.info(f"📞 Contato existente encontrado: {existing_contact['id']} para {phone_number}")
                                    self.upsert_contact(existing_contact['id'], contact_name, account_id, phone_number)
                                else:
                                    # Criar novo contato com UUID
                                    new_contact_id = str(uuid.uuid4())
                                    logger.info(f"📞 Criando novo contato: {new_contact_id} para {phone_number}")
                                    self.upsert_contact(new_contact_id, contact_name, account_id, phone_number)
                                    
                            except Exception as contact_error:
                                logger.warning(f"Erro ao salvar contato {phone_number}: {contact_error}")
                        
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
            
        result = self._execute_with_fresh_connection(_save_webhook_event_operation)
        return result is not None
            
    def execute_query(self, query, params=None):
        """Executa uma query genérica com reconexão automática"""
        if not self.enabled:
            return None
            
        def _execute_query_operation(connection):
            cursor = connection.cursor(dictionary=True)
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
                
            result = cursor.fetchall()
            cursor.close()
            
            return result
            
        result = self._execute_with_fresh_connection(_execute_query_operation)
        return result
            
    def get_connection_status(self):
        """Retorna o status da conexão"""
        if not self.enabled:
            return "disabled"
        
        connection = self._create_fresh_connection()
        if connection:
            try:
                connection.close()
                return "connected"
            except:
                pass
        return "disconnected"

    def get_active_conversation(self, contact_id):
        """Busca a conversa ativa de um contato. Retorna o registro ou None."""
        if not self.enabled:
            return None
        def _get_active_conversation_operation(connection):
            # Timeout específico para esta consulta
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Timeout na consulta get_active_conversation")
            
            # Configurar timeout de 10 segundos
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(10)
            
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
            finally:
                signal.alarm(0)  # Cancelar timeout
                
        result = self._execute_with_fresh_connection(_get_active_conversation_operation)
        return result

    def create_conversation(self, contact_id):
        """Cria uma nova conversa ativa para o contato e retorna o id."""
        if not self.enabled:
            return None
        def _create_conversation_operation(connection):
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
        result = self._execute_with_fresh_connection(_create_conversation_operation)
        return result

    def close_conversation(self, conversation_id):
        """Fecha uma conversa (status = closed, define ended_at)."""
        if not self.enabled:
            return False
        def _close_conversation_operation(connection):
            cursor = connection.cursor()
            query = """
                UPDATE conversation SET status = 'closed', ended_at = NOW()
                WHERE id = %s
            """
            cursor.execute(query, (conversation_id,))
            connection.commit()
            cursor.close()
            return True
        result = self._execute_with_fresh_connection(_close_conversation_operation)
        return result is not None

    def insert_conversation_message(self, conversation_id, message_text, sender, message_type, timestamp=None, prompt=None, tokens=None, notify_websocket=True):
        """Insere uma mensagem na tabela conversation_message."""
        if not self.enabled:
            return False
        
        # Garantir que timestamp está definido antes de passar para a função interna
        if not timestamp:
            timestamp = datetime.now(timezone.utc)
            
        def _insert_conversation_message_operation(connection):
            cursor = connection.cursor()
            query = """
                INSERT INTO conversation_message (conversation_id, message_text, sender, message_type, timestamp, prompt, tokens)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (conversation_id, message_text, sender, message_type, timestamp, prompt, tokens))
            message_id = cursor.lastrowid
            connection.commit()
            cursor.close()
            return message_id
        
        result = self._execute_with_fresh_connection(_insert_conversation_message_operation)
        
        # Notificar via WebSocket se mensagem foi inserida com sucesso
        if result and notify_websocket:
            try:
                from websocket_notifier import notify_message_saved
                notify_message_saved(conversation_id, result, message_text, sender, message_type, tokens or 0)
            except Exception as e:
                logger.warning(f"⚠️ Falha ao notificar WebSocket: {e}")
        
        return result

    def insert_conversation_attach(self, conversation_id, file_url, file_type, file_name=None, file_extension=None):
        """Insere um anexo na tabela conversation_attach."""
        if not self.enabled:
            return False
        def _insert_conversation_attach_operation(connection):
            cursor = connection.cursor()
            
            # Query dinâmica baseada nos parâmetros fornecidos
            fields = ["conversation_id", "file_url", "file_type"]
            values = [conversation_id, file_url, file_type]
            placeholders = ["%s", "%s", "%s"]
            
            if file_name is not None:
                fields.append("file_name")
                values.append(file_name)
                placeholders.append("%s")
            
            if file_extension is not None:
                fields.append("file_extension")
                values.append(file_extension)
                placeholders.append("%s")
            
            query = f"""
                INSERT INTO conversation_attach ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
            """
            
            cursor.execute(query, values)
            connection.commit()
            cursor.close()
            return True
        result = self._execute_with_fresh_connection(_insert_conversation_attach_operation)
        return result is not None

    def get_conversation_messages(self, conversation_id, limit=10):
        """Busca as últimas mensagens de uma conversa (ordem cronológica)."""
        if not self.enabled:
            return []
        def _get_conversation_messages_operation(connection):
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
            # Retornar em ordem cronológica (mais antiga primeira)
            return list(reversed(messages))
        result = self._execute_with_fresh_connection(_get_conversation_messages_operation)
        return result

    def get_conversation_attachments(self, conversation_id):
        """Busca todos os anexos de uma conversa."""
        if not self.enabled:
            return []
        def _get_conversation_attachments_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT file_url, file_type, file_name, file_extension
                FROM conversation_attach
                WHERE conversation_id = %s
                ORDER BY id ASC
            """
            cursor.execute(query, (conversation_id,))
            attachments = cursor.fetchall()
            cursor.close()
            return attachments
        result = self._execute_with_fresh_connection(_get_conversation_attachments_operation)
        return result or []

    def get_last_user_messages(self, conversation_id, limit=1):
        """Busca as últimas mensagens do usuário (sender='user') de uma conversa."""
        if not self.enabled:
            return []
        def _get_last_user_messages_operation(connection):
            # Timeout específico para esta consulta
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Timeout na consulta get_last_user_messages")
            
            # Configurar timeout de 10 segundos
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(10)
            
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
            finally:
                signal.alarm(0)  # Cancelar timeout
                
        result = self._execute_with_fresh_connection(_get_last_user_messages_operation)
        return result

    def get_contact(self, contact_id):
        """Busca um contato pelo contact_id na tabela contacts."""
        if not self.enabled:
            return None
        def _get_contact_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT * FROM contacts WHERE id = %s
            """
            cursor.execute(query, (contact_id,))
            contact = cursor.fetchone()
            cursor.close()
            return contact
        result = self._execute_with_fresh_connection(_get_contact_operation)
        return result

    def has_agent_response_for_contact(self, contact_id):
        """Verifica se o contato já recebeu alguma resposta do agente em qualquer conversa."""
        if not self.enabled:
            return False
        def _has_agent_response_for_contact_operation(connection):
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
        result = self._execute_with_fresh_connection(_has_agent_response_for_contact_operation)
        return result is not None

    def insert_account(self, account_id, name):
        """Insere uma nova conta na tabela accounts."""
        if not self.enabled:
            return False
        
        def _insert_account_operation(connection):
            cursor = connection.cursor()
            query = """
                INSERT INTO accounts (id, name)
                VALUES (%s, %s)
            """
            cursor.execute(query, (account_id, name))
            connection.commit()
            cursor.close()
            return True
        
        result = self._execute_with_fresh_connection(_insert_account_operation)
        return result is not None

    def get_account(self, account_id):
        """Busca uma conta pelo ID na tabela accounts."""
        if not self.enabled:
            return None
        
        def _get_account_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT * FROM accounts WHERE id = %s
            """
            cursor.execute(query, (account_id,))
            account = cursor.fetchone()
            cursor.close()
            return account
        
        result = self._execute_with_fresh_connection(_get_account_operation)
        return result

    # ==================== CHANNELS CRUD ====================
    
    def insert_channel(self, channel_id, account_id, channel_type, name, bot_id=None, active=True, phone_number=None, client_id=None, client_secret=None, access_token=None):
        """Insere um novo canal na tabela channels."""
        if not self.enabled:
            return False
        
        def _insert_channel_operation(connection):
            cursor = connection.cursor()
            query = """
                INSERT INTO channels (id, account_id, bot_id, type, name, phone_number, client_id, client_secret, access_token, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (channel_id, account_id, bot_id, channel_type, name, phone_number, client_id, client_secret, access_token, active))
            connection.commit()
            cursor.close()
            return True
        
        result = self._execute_with_fresh_connection(_insert_channel_operation)
        return result is not None

    def get_channel(self, channel_id, exclude_sensitive=True):
        """Busca um canal pelo ID na tabela channels."""
        if not self.enabled:
            return None
        
        def _get_channel_operation(connection):
            cursor = connection.cursor(dictionary=True)
            if exclude_sensitive:
                query = """
                    SELECT id, account_id, bot_id, type, name, phone_number, active, created_at
                    FROM channels WHERE id = %s
                """
            else:
                query = """
                    SELECT id, account_id, bot_id, type, name, phone_number, client_id, client_secret, access_token, active, created_at
                    FROM channels WHERE id = %s
                """
            cursor.execute(query, (channel_id,))
            channel = cursor.fetchone()
            cursor.close()
            
            return channel
        
        result = self._execute_with_fresh_connection(_get_channel_operation)
        return result
    
    def get_channel_full(self, channel_id):
        """Busca um canal com todos os campos incluindo os sensíveis - para uso interno."""
        return self.get_channel(channel_id, exclude_sensitive=False)

    def get_channels_by_account(self, account_id, active_only=False):
        """Busca todos os canais de uma conta específica."""
        if not self.enabled:
            return []
        
        def _get_channels_by_account_operation(connection):
            cursor = connection.cursor(dictionary=True)
            
            if active_only:
                query = """
                    SELECT id, account_id, bot_id, type, name, phone_number, active, created_at
                    FROM channels WHERE account_id = %s AND active = 1
                    ORDER BY created_at DESC
                """
            else:
                query = """
                    SELECT id, account_id, bot_id, type, name, phone_number, active, created_at
                    FROM channels WHERE account_id = %s
                    ORDER BY created_at DESC
                """
            
            # Log de auditoria SQL
            logger.info(f"🔍 SQL AUDITORIA: Executando query para account_id={account_id}, active_only={active_only}")
            logger.debug(f"📝 Query SQL: {query.strip()}")
            
            cursor.execute(query, (account_id,))
            channels = cursor.fetchall()
            
            # Log do resultado da query
            if channels:
                returned_account_ids = list(set([ch['account_id'] for ch in channels]))
                logger.info(f"✅ SQL RESULTADO: {len(channels)} canais encontrados, account_ids únicos: {returned_account_ids}")
                
                # Validação crítica de segurança
                if len(returned_account_ids) > 1 or (returned_account_ids and returned_account_ids[0] != account_id):
                    logger.error(f"🚨 VIOLAÇÃO DE SEGURANÇA: Query retornou canais de contas diferentes! Expected: {account_id}, Found: {returned_account_ids}")
                else:
                    logger.info(f"🔒 SEGURANÇA OK: Todos os canais pertencem à conta {account_id}")
            else:
                logger.info(f"📭 SQL RESULTADO: Nenhum canal encontrado para account_id={account_id}")
            
            cursor.close()
            
            return channels
        
        result = self._execute_with_fresh_connection(_get_channels_by_account_operation)
        return result or []

    def check_whatsapp_phone_duplicate(self, whatsapp_phone_number, exclude_channel_id=None):
        """Verifica se já existe um canal WhatsApp ativo com o mesmo número de telefone"""
        if not self.enabled or not whatsapp_phone_number:
            return None
        
        def _check_duplicate_operation(connection):
            cursor = connection.cursor(dictionary=True)
            
            if exclude_channel_id:
                # Para atualização - excluir o próprio canal da verificação
                query = """
                    SELECT id, account_id, name, whatsapp_phone_number
                    FROM channels 
                    WHERE type = 'whatsapp' 
                    AND whatsapp_phone_number = %s 
                    AND active = 1 
                    AND id != %s
                    LIMIT 1
                """
                cursor.execute(query, (whatsapp_phone_number, exclude_channel_id))
            else:
                # Para criação - verificar se existe qualquer canal ativo com o número
                query = """
                    SELECT id, account_id, name, whatsapp_phone_number
                    FROM channels 
                    WHERE type = 'whatsapp' 
                    AND whatsapp_phone_number = %s 
                    AND active = 1
                    LIMIT 1
                """
                cursor.execute(query, (whatsapp_phone_number,))
            
            existing_channel = cursor.fetchone()
            cursor.close()
            return existing_channel
        
        result = self._execute_with_fresh_connection(_check_duplicate_operation)
        return result

    def update_channel(self, channel_id, account_id, name=None, bot_id=None, active=None, channel_type=None, phone_number=None, client_id=None, client_secret=None, access_token=None):
        """Atualiza um canal existente. Apenas os campos fornecidos são atualizados."""
        if not self.enabled:
            return False
        
        def _update_channel_operation(connection):
            cursor = connection.cursor()
            
            # Construir query dinâmica baseada nos campos fornecidos
            update_fields = []
            values = []
            
            if name is not None:
                update_fields.append("name = %s")
                values.append(name)
            
            if bot_id is not None:
                update_fields.append("bot_id = %s")
                values.append(bot_id)
            
            if active is not None:
                update_fields.append("active = %s")
                values.append(active)
            
            if channel_type is not None:
                update_fields.append("type = %s")
                values.append(channel_type)
            
            if phone_number is not None:
                update_fields.append("phone_number = %s")
                values.append(phone_number)
            
            if client_id is not None:
                update_fields.append("client_id = %s")
                values.append(client_id)
            
            if client_secret is not None:
                update_fields.append("client_secret = %s")
                values.append(client_secret)
            
            if access_token is not None:
                update_fields.append("access_token = %s")
                values.append(access_token)
            
            if not update_fields:
                return False  # Nada para atualizar
            
            query = f"""
                UPDATE channels 
                SET {', '.join(update_fields)}
                WHERE id = %s AND account_id = %s
            """
            values.extend([channel_id, account_id])
            
            cursor.execute(query, values)
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_update_channel_operation)
        return result is not None and result

    def delete_channel(self, channel_id, account_id):
        """Deleta um canal específico (soft delete - marca como inativo). 
        NOTA: Este método não é mais usado. O DELETE padrão agora é permanente."""
        if not self.enabled:
            return False
        
        def _delete_channel_operation(connection):
            cursor = connection.cursor()
            query = """
                UPDATE channels 
                SET active = 0
                WHERE id = %s AND account_id = %s
            """
            cursor.execute(query, (channel_id, account_id))
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_delete_channel_operation)
        return result is not None and result

    def hard_delete_channel(self, channel_id, account_id):
        """Deleta permanentemente um canal (hard delete)."""
        if not self.enabled:
            return False
        
        def _hard_delete_channel_operation(connection):
            cursor = connection.cursor()
            query = """
                DELETE FROM channels 
                WHERE id = %s AND account_id = %s
            """
            cursor.execute(query, (channel_id, account_id))
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_hard_delete_channel_operation)
        return result is not None and result

    # ==================== BOTS CRUD ====================
    
    def insert_bot(self, bot_id, account_id, name, system_prompt, integration_id=None, agent_name=None):
        """Insere um novo bot na tabela bots."""
        if not self.enabled:
            return False
        
        def _insert_bot_operation(connection):
            cursor = connection.cursor()
            query = """
                INSERT INTO bots (id, account_id, name, system_prompt, integration_id, agent_name)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            try:
                cursor.execute(query, (bot_id, account_id, name, system_prompt, integration_id, agent_name))
                connection.commit()
                cursor.close()
                return True
            except Exception as e:
                logger.error(f"❌ Erro ao inserir bot no banco: {e}")
                logger.error(f"Query: {query}")
                logger.error(f"Parâmetros: bot_id={bot_id}, account_id={account_id}, name={name}, system_prompt={system_prompt[:50]}..., integration_id={integration_id}, agent_name={agent_name}")
                cursor.close()
                raise e
        
        result = self._execute_with_fresh_connection(_insert_bot_operation)
        return result is not None

    def get_bot(self, bot_id):
        """Busca um bot pelo ID na tabela bots."""
        if not self.enabled:
            return None
        
        def _get_bot_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, account_id, name, system_prompt, integration_id, created_at
                FROM bots WHERE id = %s
            """
            cursor.execute(query, (bot_id,))
            bot = cursor.fetchone()
            cursor.close()
            return bot
        
        result = self._execute_with_fresh_connection(_get_bot_operation)
        return result

    def get_bots_by_account(self, account_id):
        """Busca todos os bots de uma conta específica."""
        if not self.enabled:
            return []
        
        def _get_bots_by_account_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, account_id, name, system_prompt, integration_id, created_at
                FROM bots WHERE account_id = %s
                ORDER BY created_at DESC
            """
            
            # Log de auditoria SQL
            logger.info(f"🔍 SQL AUDITORIA BOTS: Executando query para account_id={account_id}")
            logger.debug(f"📝 Query SQL BOTS: {query.strip()}")
            
            cursor.execute(query, (account_id,))
            bots = cursor.fetchall()
            
            # Log do resultado da query
            if bots:
                returned_account_ids = list(set([bot['account_id'] for bot in bots]))
                logger.info(f"✅ SQL RESULTADO BOTS: {len(bots)} bots encontrados, account_ids únicos: {returned_account_ids}")
                
                # Validação crítica de segurança
                if len(returned_account_ids) > 1 or (returned_account_ids and returned_account_ids[0] != account_id):
                    logger.error(f"🚨 VIOLAÇÃO DE SEGURANÇA BOTS: Query retornou bots de contas diferentes! Expected: {account_id}, Found: {returned_account_ids}")
                else:
                    logger.info(f"🔒 SEGURANÇA OK BOTS: Todos os bots pertencem à conta {account_id}")
            else:
                logger.info(f"📭 SQL RESULTADO BOTS: Nenhum bot encontrado para account_id={account_id}")
            
            cursor.close()
            return bots
        
        result = self._execute_with_fresh_connection(_get_bots_by_account_operation)
        return result or []

    def update_bot(self, bot_id, account_id, name=None, system_prompt=None, integration_id='__NOT_PROVIDED__', agent_name='__NOT_PROVIDED__'):
        """Atualiza um bot existente. Apenas os campos fornecidos são atualizados."""
        if not self.enabled:
            return False
        
        def _update_bot_operation(connection):
            cursor = connection.cursor()
            
            # Construir query dinâmica baseada nos campos fornecidos
            update_fields = []
            values = []
            
            if name is not None:
                update_fields.append("name = %s")
                values.append(name)
            
            if system_prompt is not None:
                update_fields.append("system_prompt = %s")
                values.append(system_prompt)
            
            if integration_id != '__NOT_PROVIDED__':
                update_fields.append("integration_id = %s")
                values.append(integration_id)
            
            if agent_name != '__NOT_PROVIDED__':
                update_fields.append("agent_name = %s")
                values.append(agent_name)
            
            if not update_fields:
                return False  # Nada para atualizar
            
            query = f"""
                UPDATE bots 
                SET {', '.join(update_fields)}
                WHERE id = %s AND account_id = %s
            """
            values.extend([bot_id, account_id])
            
            cursor.execute(query, values)
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_update_bot_operation)
        return result is not None and result

    def delete_bot(self, bot_id, account_id):
        """Deleta permanentemente um bot."""
        if not self.enabled:
            return False
        
        def _delete_bot_operation(connection):
            cursor = connection.cursor()
            query = """
                DELETE FROM bots 
                WHERE id = %s AND account_id = %s
            """
            cursor.execute(query, (bot_id, account_id))
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_delete_bot_operation)
        return result is not None and result

    # ==================== WHATSAPP TOKEN OPTIMIZATION ====================
    
    def optimize_whatsapp_token(self, phone_number_id=None, display_phone_number=None):
        """
        Otimiza a estrutura do whatsapp_token removendo campos desnecessários
        e incluindo novos campos importantes
        """
        if not self.enabled:
            return False
        
        try:
            # Buscar token atual
            current_token = self.get_config('whatsapp_token')
            if not current_token:
                logger.warning("Token whatsapp_token não encontrado para otimizar")
                return False
            
            # Estrutura otimizada - apenas campos necessários
            optimized_token = {
                # Campos essenciais para funcionamento
                "access_token": current_token.get('access_token'),
                "expires_at": current_token.get('expires_at'),
                "is_long_lived": current_token.get('is_long_lived', True),
                
                # Novos campos importantes
                "phone_number_id": phone_number_id or current_token.get('phone_number_id', "421769451025047"),
                "display_phone_number": display_phone_number or current_token.get('display_phone_number', "555437710014"),
                
                # Metadados úteis
                "optimized_at": datetime.now().isoformat(),
                "version": "2.0"
            }
            
            # Validar campos obrigatórios
            if not optimized_token['access_token']:
                logger.error("access_token é obrigatório para otimização")
                return False
            
            # Atualizar no banco
            success = self.set_config('whatsapp_token', optimized_token)
            
            if success:
                logger.info(f"✅ Token WhatsApp otimizado com sucesso")
                logger.info(f"📱 Phone Number ID: {optimized_token['phone_number_id']}")
                logger.info(f"📞 Display Phone: {optimized_token['display_phone_number']}")
                
                # Log campos removidos para auditoria
                removed_fields = []
                for field in ['created_at', 'expires_in', 'token_type', 'raw_response']:
                    if field in current_token:
                        removed_fields.append(field)
                
                if removed_fields:
                    logger.info(f"🗑️ Campos removidos: {', '.join(removed_fields)}")
                
                return True
            else:
                logger.error("Falha ao salvar token otimizado")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao otimizar whatsapp_token: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def get_whatsapp_phone_config(self):
        """
        Retorna configurações do telefone WhatsApp (phone_number_id e display_phone_number)
        """
        try:
            token_data = self.get_config('whatsapp_token')
            if not token_data:
                return None
            
            return {
                "phone_number_id": token_data.get('phone_number_id', "421769451025047"),
                "display_phone_number": token_data.get('display_phone_number', "555437710014")
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar configuração do telefone: {e}")
            return None

    # ==================== BOTS PROMPTS CRUD ====================
    
    def insert_bot_prompt(self, bot_id, prompt_id, prompt, description=None, rule_display=None):
        """Insere um novo prompt na tabela bots_prompts."""
        if not self.enabled:
            return False
        
        def _insert_bot_prompt_operation(connection):
            cursor = connection.cursor()
            query = """
                INSERT INTO bots_prompts (bot_id, id, prompt, description, rule_display)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (bot_id, prompt_id, prompt, description, rule_display))
            connection.commit()
            cursor.close()
            return True
        
        result = self._execute_with_fresh_connection(_insert_bot_prompt_operation)
        return result is not None
    
    def get_bot_prompts(self, bot_id):
        """Busca todos os prompts de um bot específico."""
        if not self.enabled:
            return []
        
        def _get_bot_prompts_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT bot_id, id, prompt, description, rule_display, created_at, updated_at
                FROM bots_prompts WHERE bot_id = %s
                ORDER BY created_at DESC
            """
            cursor.execute(query, (bot_id,))
            prompts = cursor.fetchall()
            cursor.close()
            return prompts
        
        result = self._execute_with_fresh_connection(_get_bot_prompts_operation)
        return result or []
    
    def get_bot_prompt(self, bot_id, prompt_id):
        """Busca um prompt específico pelo bot_id e prompt_id."""
        logger.info(f"🔍 DATABASE get_bot_prompt: bot_id={bot_id}, prompt_id={prompt_id}")
        
        if not self.enabled:
            logger.error("❌ DATABASE: Banco não habilitado")
            return None
        
        def _get_bot_prompt_operation(connection):
            try:
                cursor = connection.cursor(dictionary=True)
                logger.info("✅ DATABASE: Cursor criado para busca")
                
                query = """
                    SELECT bot_id, id, prompt, description, rule_display, created_at, updated_at
                    FROM bots_prompts WHERE bot_id = %s AND id = %s
                """
                
                logger.info(f"🗃️ DATABASE: Query busca prompt: {query}")
                logger.info(f"🗃️ DATABASE: Parâmetros busca: bot_id={bot_id}, prompt_id={prompt_id}")
                
                cursor.execute(query, (bot_id, prompt_id))
                prompt = cursor.fetchone()
                
                logger.info(f"📄 DATABASE: Prompt encontrado: {prompt is not None}")
                if prompt:
                    logger.info(f"📄 DATABASE: Dados do prompt: {prompt}")
                
                cursor.close()
                logger.info("✅ DATABASE: Cursor busca fechado")
                return prompt
                
            except Exception as e:
                logger.error(f"❌ DATABASE EXCEPTION busca: {e}")
                import traceback
                logger.error(f"❌ DATABASE TRACEBACK busca: {traceback.format_exc()}")
                raise e
        
        result = self._execute_with_fresh_connection(_get_bot_prompt_operation)
        logger.info(f"🏁 DATABASE: Resultado busca final: {result is not None}")
        return result
    
    def update_bot_prompt(self, bot_id, prompt_id, prompt=None, description=None, rule_display=None):
        """Atualiza um prompt existente. Apenas os campos fornecidos são atualizados."""
        logger.info(f"🔧 DATABASE update_bot_prompt: bot_id={bot_id}, prompt_id={prompt_id}")
        logger.info(f"🔧 DATABASE Parâmetros: prompt={prompt is not None}, description={description is not None}, rule_display={rule_display is not None}")
        
        if not self.enabled:
            logger.error("❌ DATABASE: Banco não habilitado")
            return False
        
        def _update_bot_prompt_operation(connection):
            try:
                cursor = connection.cursor()
                logger.info("✅ DATABASE: Cursor criado")
                
                # Construir query dinâmica baseada nos campos fornecidos
                update_fields = []
                values = []
                
                if prompt is not None:
                    update_fields.append("prompt = %s")
                    values.append(prompt)
                    logger.info(f"📝 DATABASE: Adicionado campo prompt")
                
                if description is not None:
                    update_fields.append("description = %s")
                    values.append(description)
                    logger.info(f"📝 DATABASE: Adicionado campo description")
                
                if rule_display is not None:
                    update_fields.append("rule_display = %s")
                    values.append(rule_display)
                    logger.info(f"📝 DATABASE: Adicionado campo rule_display")
                
                if not update_fields:
                    logger.error("❌ DATABASE: Nenhum campo para atualizar")
                    return False  # Nada para atualizar
                
                query = f"""
                    UPDATE bots_prompts 
                    SET {', '.join(update_fields)}
                    WHERE bot_id = %s AND id = %s
                """
                values.extend([bot_id, prompt_id])
                
                logger.info(f"🗃️ DATABASE: Query SQL: {query}")
                logger.info(f"🗃️ DATABASE: Valores: {values}")
                logger.info(f"🔍 DATABASE: bot_id para WHERE: '{bot_id}' (len={len(bot_id)})")
                logger.info(f"🔍 DATABASE: prompt_id para WHERE: '{prompt_id}' (len={len(prompt_id)})")
                
                # Testar primeiro se o registro existe com SELECT
                test_query = "SELECT COUNT(*) as total FROM bots_prompts WHERE bot_id = %s AND id = %s"
                cursor.execute(test_query, (bot_id, prompt_id))
                count_result = cursor.fetchone()
                logger.info(f"🧪 DATABASE: SELECT COUNT antes do UPDATE: {count_result}")
                
                cursor.execute(query, values)
                rows_affected = cursor.rowcount
                logger.info(f"📊 DATABASE: Linhas afetadas: {rows_affected}")
                
                connection.commit()
                logger.info("✅ DATABASE: Commit realizado")
                
                cursor.close()
                logger.info("✅ DATABASE: Cursor fechado")
                
                return rows_affected > 0
                
            except Exception as e:
                logger.error(f"❌ DATABASE EXCEPTION: {e}")
                logger.error(f"❌ DATABASE EXCEPTION tipo: {type(e).__name__}")
                import traceback
                logger.error(f"❌ DATABASE TRACEBACK: {traceback.format_exc()}")
                raise e
        
        result = self._execute_with_fresh_connection(_update_bot_prompt_operation)
        logger.info(f"🏁 DATABASE: Resultado final: {result}")
        return result is not None and result
    
    def delete_bot_prompt(self, bot_id, prompt_id):
        """Deleta permanentemente um prompt."""
        if not self.enabled:
            return False
        
        def _delete_bot_prompt_operation(connection):
            cursor = connection.cursor()
            query = """
                DELETE FROM bots_prompts 
                WHERE bot_id = %s AND id = %s
            """
            cursor.execute(query, (bot_id, prompt_id))
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_delete_bot_prompt_operation)
        return result is not None and result

    # ==================== BOTS FUNCTIONS CRUD ====================
    
    def insert_bot_function(self, bot_id, function_id, description=None, action=None):
        """Insere uma nova função na tabela bots_functions."""
        if not self.enabled:
            return False
        
        def _insert_bot_function_operation(connection):
            cursor = connection.cursor()
            query = """
                INSERT INTO bots_functions (bot_id, function_id, description, action)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (bot_id, function_id, description, action))
            connection.commit()
            cursor.close()
            return True
        
        result = self._execute_with_fresh_connection(_insert_bot_function_operation)
        return result is not None
    
    def get_bot_functions(self, bot_id):
        """Busca todas as funções de um bot específico."""
        if not self.enabled:
            return []
        
        def _get_bot_functions_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT f.bot_id, f.function_id, f.description, f.created_at, f.updated_at, f.action, i.integration_type
                FROM bots_functions f join bots b on (f.bot_id = b.id)
                                      join integrations i on (b.integration_id = i.id)
                WHERE b.id = %s
                ORDER BY created_at DESC
            """
            cursor.execute(query, (bot_id,))
            functions = cursor.fetchall()
            cursor.close()
            return functions
        
        result = self._execute_with_fresh_connection(_get_bot_functions_operation)
        return result or []
    
    def get_bot_function(self, bot_id, function_id):
        """Busca uma função específica pelo bot_id e function_id."""
        if not self.enabled:
            return None
        
        def _get_bot_function_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT bot_id, function_id, description, action, created_at, updated_at
                FROM bots_functions WHERE bot_id = %s AND function_id = %s
            """
            cursor.execute(query, (bot_id, function_id))
            function = cursor.fetchone()
            cursor.close()
            return function
        
        result = self._execute_with_fresh_connection(_get_bot_function_operation)
        return result
    
    def update_bot_function(self, bot_id, function_id, **kwargs):
        """Atualiza uma função existente. Apenas os campos fornecidos são atualizados."""
        if not self.enabled:
            return False
        
        def _update_bot_function_operation(connection):
            cursor = connection.cursor()
            
            # Construir query dinâmica baseada nos campos fornecidos
            update_fields = []
            values = []
            
            if 'description' in kwargs:
                update_fields.append("description = %s")
                values.append(kwargs['description'])
            
            if 'action' in kwargs:
                update_fields.append("action = %s")
                values.append(kwargs['action'])
            
            if not update_fields:
                return False  # Nada para atualizar
            
            query = f"""
                UPDATE bots_functions 
                SET {', '.join(update_fields)}
                WHERE bot_id = %s AND function_id = %s
            """
            values.extend([bot_id, function_id])
            
            cursor.execute(query, values)
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            # Considerar sucesso se a função existe (mesmo sem mudança real)
            return True
        
        result = self._execute_with_fresh_connection(_update_bot_function_operation)
        return result is not None and result
    
    def delete_bot_function(self, bot_id, function_id):
        """Deleta permanentemente uma função e todos os seus parâmetros."""
        if not self.enabled:
            return False
        
        def _delete_bot_function_operation(connection):
            cursor = connection.cursor()
            
            # Primeiro deletar todos os parâmetros da função
            delete_params_query = """
                DELETE FROM bots_functions_parameters 
                WHERE function_id = %s
            """
            cursor.execute(delete_params_query, (function_id,))
            
            # Depois deletar a função
            delete_function_query = """
                DELETE FROM bots_functions 
                WHERE bot_id = %s AND function_id = %s
            """
            cursor.execute(delete_function_query, (bot_id, function_id))
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_delete_bot_function_operation)
        return result is not None and result

    # ==================== BOTS FUNCTIONS PARAMETERS CRUD ====================
    
    def insert_bot_function_parameter(self, function_id, parameter_id, param_type, 
                                    permited_values=None, default_value=None, param_format=None, description=None, bot_id=None):
        """Insere um novo parâmetro na tabela bots_functions_parameters."""
        if not self.enabled:
            return False
        
        def _insert_bot_function_parameter_operation(connection):
            cursor = connection.cursor()
            query = """
                INSERT INTO bots_functions_parameters 
                (function_id, parameter_id, type, permited_values, default_value, format, description, bot_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (function_id, parameter_id, param_type, 
                                 permited_values, default_value, param_format, description, bot_id))
            connection.commit()
            cursor.close()
            return True
        
        result = self._execute_with_fresh_connection(_insert_bot_function_parameter_operation)
        return result is not None
    
    def get_bot_function_parameters(self, function_id, bot_id=None):
        """Busca todos os parâmetros de uma função específica, com filtro opcional por bot_id."""
        if not self.enabled:
            return []
        
        def _get_bot_function_parameters_operation(connection):
            cursor = connection.cursor(dictionary=True)
            if bot_id:
                query = """
                    SELECT function_id, parameter_id, type, permited_values, 
                           default_value, format, description, created_at, updated_at, bot_id
                    FROM bots_functions_parameters WHERE function_id = %s AND bot_id = %s
                    ORDER BY created_at DESC
                """
                cursor.execute(query, (function_id, bot_id))
            else:
                query = """
                    SELECT function_id, parameter_id, type, permited_values, 
                           default_value, format, description, created_at, updated_at, bot_id
                    FROM bots_functions_parameters WHERE function_id = %s
                    ORDER BY created_at DESC
                """
                cursor.execute(query, (function_id,))
            parameters = cursor.fetchall()
            cursor.close()
            return parameters
        
        result = self._execute_with_fresh_connection(_get_bot_function_parameters_operation)
        return result or []
    
    def get_bot_function_parameter(self, function_id, parameter_id, bot_id=None):
        """Busca um parâmetro específico pelo function_id e parameter_id, com filtro opcional por bot_id."""
        if not self.enabled:
            return None
        
        def _get_bot_function_parameter_operation(connection):
            cursor = connection.cursor(dictionary=True)
            if bot_id:
                query = """
                    SELECT function_id, parameter_id, type, permited_values, 
                           default_value, format, description, created_at, updated_at, bot_id
                    FROM bots_functions_parameters WHERE function_id = %s AND parameter_id = %s AND bot_id = %s
                """
                cursor.execute(query, (function_id, parameter_id, bot_id))
            else:
                query = """
                    SELECT function_id, parameter_id, type, permited_values, 
                           default_value, format, description, created_at, updated_at, bot_id
                    FROM bots_functions_parameters WHERE function_id = %s AND parameter_id = %s
                """
                cursor.execute(query, (function_id, parameter_id))
            parameter = cursor.fetchone()
            cursor.close()
            return parameter
        
        result = self._execute_with_fresh_connection(_get_bot_function_parameter_operation)
        return result
    
    def update_bot_function_parameter(self, function_id, parameter_id, param_type=None,
                                    permited_values=None, default_value=None, param_format=None, description=None, bot_id=None):
        """Atualiza um parâmetro existente. Apenas os campos fornecidos são atualizados."""
        if not self.enabled:
            return False
        
        def _update_bot_function_parameter_operation(connection):
            cursor = connection.cursor()
            
            # Construir query dinâmica baseada nos campos fornecidos
            update_fields = []
            values = []
            
            if param_type is not None:
                update_fields.append("type = %s")
                values.append(param_type)
            
            if permited_values is not None:
                update_fields.append("permited_values = %s")
                values.append(permited_values)
            
            if default_value is not None:
                update_fields.append("default_value = %s")
                values.append(default_value)
            
            if param_format is not None:
                update_fields.append("format = %s")
                values.append(param_format)
            
            if description is not None:
                update_fields.append("description = %s")
                values.append(description)
            
            if not update_fields:
                return False  # Nada para atualizar
            
            if bot_id:
                query = f"""
                    UPDATE bots_functions_parameters 
                    SET {', '.join(update_fields)}
                    WHERE function_id = %s AND parameter_id = %s AND bot_id = %s
                """
                values.extend([function_id, parameter_id, bot_id])
            else:
                query = f"""
                    UPDATE bots_functions_parameters 
                    SET {', '.join(update_fields)}
                    WHERE function_id = %s AND parameter_id = %s
                """
                values.extend([function_id, parameter_id])
            
            cursor.execute(query, values)
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_update_bot_function_parameter_operation)
        return result is not None and result
    
    def delete_bot_function_parameter(self, function_id, parameter_id, bot_id=None):
        """Deleta permanentemente um parâmetro, com filtro opcional por bot_id."""
        if not self.enabled:
            return False
        
        def _delete_bot_function_parameter_operation(connection):
            cursor = connection.cursor()
            if bot_id:
                query = """
                    DELETE FROM bots_functions_parameters 
                    WHERE function_id = %s AND parameter_id = %s AND bot_id = %s
                """
                cursor.execute(query, (function_id, parameter_id, bot_id))
            else:
                query = """
                    DELETE FROM bots_functions_parameters 
                    WHERE function_id = %s AND parameter_id = %s
                """
                cursor.execute(query, (function_id, parameter_id))
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_delete_bot_function_parameter_operation)
        return result is not None and result

    # ===== INTEGRATIONS METHODS =====
    
    def insert_integration(self, integration_id, account_id, integration_type, name=None, is_active=1, 
                          access_token=None, client_id=None, client_secret=None):
        """Insere uma nova integração na tabela integrations."""
        if not self.enabled:
            return False
        
        def _insert_integration_operation(connection):
            cursor = connection.cursor()
            query = """
                INSERT INTO integrations (id, account_id, integration_type, name, is_active, 
                                        access_token, client_id, client_secret)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (integration_id, account_id, integration_type, name, is_active,
                                 access_token, client_id, client_secret))
            connection.commit()
            cursor.close()
            return True
        
        result = self._execute_with_fresh_connection(_insert_integration_operation)
        return result is not None

    def get_integration(self, integration_id):
        """Busca uma integração pelo ID."""
        if not self.enabled:
            return None
        
        def _get_integration_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, account_id, integration_type, name, is_active, created_at, updated_at
                FROM integrations WHERE id = %s
            """
            cursor.execute(query, (integration_id,))
            integration = cursor.fetchone()
            cursor.close()
            
            return integration
        
        result = self._execute_with_fresh_connection(_get_integration_operation)
        return result

    def get_integration_full(self, integration_id):
        """Busca uma integração pelo ID com todos os campos (incluindo sensíveis) - uso interno."""
        if not self.enabled:
            return None
        
        def _get_integration_full_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, account_id, integration_type, name, is_active, created_at, updated_at,
                       access_token, client_id, client_secret
                FROM integrations WHERE id = %s
            """
            cursor.execute(query, (integration_id,))
            integration = cursor.fetchone()
            cursor.close()
            
            return integration
        
        result = self._execute_with_fresh_connection(_get_integration_full_operation)
        return result

    def get_integrations_by_account(self, account_id, active_only=False):
        """Busca todas as integrações de uma conta específica."""
        if not self.enabled:
            return []
        
        def _get_integrations_by_account_operation(connection):
            cursor = connection.cursor(dictionary=True)
            
            if active_only:
                query = """
                    SELECT id, account_id, integration_type, name, is_active, created_at, updated_at
                    FROM integrations WHERE account_id = %s AND is_active = 1
                    ORDER BY created_at DESC
                """
            else:
                query = """
                    SELECT id, account_id, integration_type, name, is_active, created_at, updated_at
                    FROM integrations WHERE account_id = %s
                    ORDER BY created_at DESC
                """
            
            # Log de auditoria SQL
            logger.info(f"🔍 SQL AUDITORIA: Executando query para account_id={account_id}, active_only={active_only}")
            logger.debug(f"📝 Query SQL: {query.strip()}")
            
            cursor.execute(query, (account_id,))
            integrations = cursor.fetchall()
            
            # Log do resultado da query
            if integrations:
                returned_account_ids = list(set([integration['account_id'] for integration in integrations]))
                logger.info(f"✅ SQL RESULTADO: {len(integrations)} integrações encontradas, account_ids únicos: {returned_account_ids}")
                
                # Validação crítica de segurança
                if len(returned_account_ids) > 1 or (returned_account_ids and returned_account_ids[0] != account_id):
                    logger.error(f"🚨 VIOLAÇÃO DE SEGURANÇA: Query retornou integrações de contas diferentes! Expected: {account_id}, Found: {returned_account_ids}")
                else:
                    logger.info(f"🔒 SEGURANÇA OK: Todas as integrações pertencem à conta {account_id}")
            else:
                logger.info(f"📭 SQL RESULTADO: Nenhuma integração encontrada para account_id={account_id}")
            
            cursor.close()
            
            return integrations
        
        result = self._execute_with_fresh_connection(_get_integrations_by_account_operation)
        return result or []

    def update_integration(self, integration_id, account_id, integration_type=None, name=None, is_active=None,
                          access_token='__NOT_PROVIDED__', client_id='__NOT_PROVIDED__', 
                          client_secret='__NOT_PROVIDED__'):
        """Atualiza uma integração existente. Apenas os campos fornecidos são atualizados."""
        if not self.enabled:
            return False
        
        def _update_integration_operation(connection):
            cursor = connection.cursor()
            
            # Construir query dinâmica baseada nos campos fornecidos
            update_fields = []
            values = []
            
            if integration_type is not None:
                update_fields.append("integration_type = %s")
                values.append(integration_type)
            
            if name is not None:
                update_fields.append("name = %s")
                values.append(name)
            
            if is_active is not None:
                update_fields.append("is_active = %s")
                values.append(is_active)
            
            if access_token != '__NOT_PROVIDED__':
                update_fields.append("access_token = %s")
                values.append(access_token)
            
            if client_id != '__NOT_PROVIDED__':
                update_fields.append("client_id = %s")
                values.append(client_id)
            
            if client_secret != '__NOT_PROVIDED__':
                update_fields.append("client_secret = %s")
                values.append(client_secret)
            
            if not update_fields:
                return False  # Nada para atualizar
            
            # Adicionar updated_at
            update_fields.append("updated_at = NOW()")
            
            query = f"""
                UPDATE integrations 
                SET {', '.join(update_fields)}
                WHERE id = %s AND account_id = %s
            """
            values.extend([integration_id, account_id])
            
            cursor.execute(query, values)
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_update_integration_operation)
        return result

    def delete_integration(self, integration_id, account_id):
        """Remove uma integração da tabela integrations."""
        if not self.enabled:
            return False
        
        def _delete_integration_operation(connection):
            cursor = connection.cursor()
            query = "DELETE FROM integrations WHERE id = %s AND account_id = %s"
            cursor.execute(query, (integration_id, account_id))
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_delete_integration_operation)
        return result

    # ===== BOTS PROMPTS FUNCTIONS METHODS =====
    
    def insert_prompt_function(self, account_id, bot_id, prompt_id, function_id):
        """Associa uma função a um prompt."""
        if not self.enabled:
            return False
        
        def _insert_prompt_function_operation(connection):
            cursor = connection.cursor()
            query = """
                INSERT INTO bots_prompts_functions (account_id, bot_id, prompt_id, function_id)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (account_id, bot_id, prompt_id, function_id))
            connection.commit()
            cursor.close()
            return True
        
        result = self._execute_with_fresh_connection(_insert_prompt_function_operation)
        return result is not None

    def get_prompt_functions(self, account_id, prompt_id):
        """Busca todas as funções associadas a um prompt."""
        if not self.enabled:
            return []
        
        def _get_prompt_functions_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, account_id, bot_id, prompt_id, function_id
                FROM bots_prompts_functions 
                WHERE account_id = %s AND prompt_id = %s AND prompt_id IS NOT NULL
                ORDER BY function_id
            """
            cursor.execute(query, (account_id, prompt_id))
            functions = cursor.fetchall()
            cursor.close()
            return functions
        
        result = self._execute_with_fresh_connection(_get_prompt_functions_operation)
        return result or []

    def delete_prompt_function(self, account_id, prompt_id, function_id):
        """Remove uma função específica de um prompt."""
        if not self.enabled:
            return False
        
        def _delete_prompt_function_operation(connection):
            cursor = connection.cursor()
            query = """
                DELETE FROM bots_prompts_functions 
                WHERE account_id = %s AND prompt_id = %s AND function_id = %s AND prompt_id IS NOT NULL
            """
            cursor.execute(query, (account_id, prompt_id, function_id))
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_delete_prompt_function_operation)
        return result

    def delete_all_prompt_functions(self, account_id, prompt_id):
        """Remove todas as funções associadas a um prompt."""
        if not self.enabled:
            return False
        
        def _delete_all_prompt_functions_operation(connection):
            cursor = connection.cursor()
            query = """
                DELETE FROM bots_prompts_functions 
                WHERE account_id = %s AND prompt_id = %s AND prompt_id IS NOT NULL
            """
            cursor.execute(query, (account_id, prompt_id))
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected
        
        result = self._execute_with_fresh_connection(_delete_all_prompt_functions_operation)
        return result if result is not None else 0

    def check_prompt_function_exists(self, account_id, prompt_id, function_id):
        """Verifica se uma associação prompt-função já existe."""
        if not self.enabled:
            return False
        
        def _check_prompt_function_exists_operation(connection):
            cursor = connection.cursor()
            query = """
                SELECT COUNT(*) as count FROM bots_prompts_functions 
                WHERE account_id = %s AND prompt_id = %s AND function_id = %s AND prompt_id IS NOT NULL
            """
            cursor.execute(query, (account_id, prompt_id, function_id))
            result = cursor.fetchone()
            cursor.close()
            
            return result[0] > 0 if result else False
        
        result = self._execute_with_fresh_connection(_check_prompt_function_exists_operation)
        return result

    # ===== BOT FUNCTIONS ASSOCIATION METHODS =====
    
    def insert_bot_function_association(self, account_id, bot_id, function_id):
        """Associa uma função diretamente a um bot (sem prompt específico)."""
        if not self.enabled:
            return False
        
        def _insert_bot_function_association_operation(connection):
            cursor = connection.cursor()
            query = """
                INSERT INTO bots_prompts_functions (account_id, bot_id, prompt_id, function_id)
                VALUES (%s, %s, NULL, %s)
            """
            cursor.execute(query, (account_id, bot_id, function_id))
            connection.commit()
            cursor.close()
            return True
        
        result = self._execute_with_fresh_connection(_insert_bot_function_association_operation)
        return result is not None

    def get_bot_function_associations(self, account_id, bot_id):
        """Busca todas as funções associadas diretamente a um bot."""
        if not self.enabled:
            return []
        
        def _get_bot_function_associations_operation(connection):
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT id, account_id, bot_id, function_id
                FROM bots_prompts_functions 
                WHERE account_id = %s AND bot_id = %s AND prompt_id IS NULL
                ORDER BY function_id
            """
            cursor.execute(query, (account_id, bot_id))
            functions = cursor.fetchall()
            cursor.close()
            return functions
        
        result = self._execute_with_fresh_connection(_get_bot_function_associations_operation)
        return result or []

    def delete_bot_function_association(self, account_id, bot_id, function_id):
        """Remove uma função específica de um bot."""
        if not self.enabled:
            return False
        
        def _delete_bot_function_association_operation(connection):
            cursor = connection.cursor()
            query = """
                DELETE FROM bots_prompts_functions 
                WHERE account_id = %s AND bot_id = %s AND function_id = %s AND prompt_id IS NULL
            """
            cursor.execute(query, (account_id, bot_id, function_id))
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected > 0
        
        result = self._execute_with_fresh_connection(_delete_bot_function_association_operation)
        return result

    def delete_all_bot_function_associations(self, account_id, bot_id):
        """Remove todas as funções associadas diretamente a um bot."""
        if not self.enabled:
            return False
        
        def _delete_all_bot_function_associations_operation(connection):
            cursor = connection.cursor()
            query = """
                DELETE FROM bots_prompts_functions 
                WHERE account_id = %s AND bot_id = %s AND prompt_id IS NULL
            """
            cursor.execute(query, (account_id, bot_id))
            rows_affected = cursor.rowcount
            connection.commit()
            cursor.close()
            
            return rows_affected
        
        result = self._execute_with_fresh_connection(_delete_all_bot_function_associations_operation)
        return result if result is not None else 0

    def check_bot_function_association_exists(self, account_id, bot_id, function_id):
        """Verifica se uma associação bot-função já existe."""
        if not self.enabled:
            return False
        
        def _check_bot_function_association_exists_operation(connection):
            cursor = connection.cursor()
            query = """
                SELECT COUNT(*) as count FROM bots_prompts_functions 
                WHERE account_id = %s AND bot_id = %s AND function_id = %s AND prompt_id IS NULL
            """
            cursor.execute(query, (account_id, bot_id, function_id))
            result = cursor.fetchone()
            cursor.close()
            
            return result[0] > 0 if result else False
        
        result = self._execute_with_fresh_connection(_check_bot_function_association_exists_operation)
        return result

    def get_bot_functions_with_usage(self, bot_id):
        """Busca todas as funções de um bot e mostra como estão sendo usadas."""
        if not self.enabled:
            return []
        
        def _get_bot_functions_with_usage_operation(connection):
            cursor = connection.cursor(dictionary=True)
            
            # Primeiro, buscar todas as funções do bot
            query_functions = """
                SELECT bot_id, function_id, description, created_at, updated_at
                FROM bots_functions 
                WHERE bot_id = %s
                ORDER BY created_at DESC
            """
            cursor.execute(query_functions, (bot_id,))
            functions = cursor.fetchall()
            
            # Para cada função, verificar como está sendo usada
            for function in functions:
                function_id = function['function_id']
                
                # Verificar se está associada a prompts
                query_prompt_usage = """
                    SELECT COUNT(*) as prompt_count 
                    FROM bots_prompts_functions 
                    WHERE bot_id = %s AND function_id = %s AND prompt_id IS NOT NULL
                """
                cursor.execute(query_prompt_usage, (bot_id, function_id))
                prompt_result = cursor.fetchone()
                prompt_count = prompt_result['prompt_count'] if prompt_result else 0
                
                # Verificar se está associada diretamente ao bot
                query_bot_usage = """
                    SELECT COUNT(*) as bot_count 
                    FROM bots_prompts_functions 
                    WHERE bot_id = %s AND function_id = %s AND prompt_id IS NULL
                """
                cursor.execute(query_bot_usage, (bot_id, function_id))
                bot_result = cursor.fetchone()
                bot_count = bot_result['bot_count'] if bot_result else 0
                
                # Determinar o status de uso
                if prompt_count > 0:
                    function['used'] = 'prompt'
                elif bot_count > 0:
                    function['used'] = 'bot'
                else:
                    function['used'] = None
            
            cursor.close()
            return functions
        
        result = self._execute_with_fresh_connection(_get_bot_functions_with_usage_operation)
        return result or []




# Instância global do DatabaseManager
db_manager = DatabaseManager() 