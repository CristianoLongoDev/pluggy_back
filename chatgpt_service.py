import requests
import json
import logging
from datetime import datetime, timedelta, timezone
from database import db_manager

logger = logging.getLogger(__name__)

class ChatGPTService:
    def __init__(self):
        self.api_key = "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"
        self.model = "gpt-4o"
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.max_tokens = 150  # Limite de tokens para resposta
        
        # Cache para emails registrados (evita consultas desnecessárias ao banco)
        self._email_cache = set()  # Set com contact_ids que já têm email registrado
        
    def build_conversation_context(self, contact_id, limit=10):
        """Monta o contexto da conversa com as últimas mensagens da conversa ativa. Se o contato for novo, inclui o first_contact_prompt no system_prompt."""
        conversation_list = []
        
        try:
            # System prompt base - usando padrão (bots customizados têm seu próprio system_prompt)
            system_prompt = {
                "role": "system",
                "content": "Você é um assistente útil."
            }
            
            # Buscar mensagens da conversa
            conversation_msgs = db_manager.get_conversation_context(contact_id, limit)

            # Verificar se system_prompt tem content válido
            if not system_prompt.get('content'):
                logger.error("System prompt sem content válido!")
                system_prompt['content'] = "Você é um assistente útil."
            
            conversation_list.append(system_prompt)
            # Adicionar mensagens do contexto
            logger.info(f"Mensagens encontradas na conversa: {len(conversation_msgs)}")
            for i, msg in enumerate(conversation_msgs):
                # Verificar se a mensagem tem dados válidos
                sender = msg.get('sender')
                message_text = msg.get('message_text')
                
                logger.info(f"Mensagem {i+1}: sender={sender}, message_text='{str(message_text)[:50] if message_text else None}...'")
                
                # Pular mensagens com dados inválidos
                if not sender or not message_text:
                    logger.warning(f"Mensagem {i+1} ignorada - sender ou message_text inválido")
                    continue
                
                if sender == 'user':
                    role = 'user'
                elif sender == 'agent':
                    role = 'assistant'
                    # Remover prefixo do assistente antes de enviar para ChatGPT para evitar duplicação
                    if message_text.startswith("*Plugger Assistente:*\n"):
                        message_text = message_text[len("*Plugger Assistente:*\n"):]
                        logger.debug(f"Prefixo removido da mensagem do agent para contexto ChatGPT")
                else:
                    logger.warning(f"Sender desconhecido '{sender}' na mensagem {i+1}, ignorando...")
                    continue  # Pular mensagens com sender inválido
                    
                conversation_list.append({
                    "role": role,
                    "content": str(message_text)
                })
            
            logger.info(f"Contexto montado para {contact_id}: {len(conversation_list)} mensagens")
            return conversation_list
            
        except Exception as e:
            logger.error(f"Erro ao montar contexto para {contact_id}: {e}")
            # Retornar contexto mínimo em caso de erro
            return [{"role": "system", "content": "Você é um assistente útil."}]
    
    def generate_response(self, contact_id, user_message=None, ignore_cache=False):
        """Gera resposta usando ChatGPT"""
        try:
            # Montar contexto da conversa
            conversation = self.build_conversation_context(contact_id)
            
            # Adicionar mensagem atual do usuário apenas se fornecida e não vazia
            if user_message and user_message.strip():
                conversation.append({
                    "role": "user",
                    "content": user_message
                })
            
            # Configurar headers
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Configurar payload base
            payload = {
                "model": self.model,
                "messages": conversation,
                "max_tokens": self.max_tokens,
                "temperature": 0.7,
                "top_p": 1,
                "frequency_penalty": 0,
                "presence_penalty": 0
            }
            
            # REMOVIDO: Sistema antigo de config - agora usa apenas sistema dinâmico de bots
            
            # Log detalhado das mensagens que serão enviadas ao ChatGPT
            logger.info("=== MENSAGENS PARA CHATGPT ===")
            for i, msg in enumerate(conversation):
                content_preview = msg.get('content', '')[:100] if msg.get('content') else 'NULL/EMPTY'
                logger.info(f"Msg {i+1}: role={msg.get('role')}, content='{content_preview}...'")
            logger.info("=== FIM MENSAGENS ===")
            
            logger.info(f"Enviando {len(conversation)} mensagens para ChatGPT")
            
            # Fazer requisição para ChatGPT
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Verificar resposta (apenas texto - sem functions no modo simples)
                message = result['choices'][0]['message']
                chatgpt_response = message['content'].strip()
                logger.info(f"ChatGPT respondeu para {contact_id}: {chatgpt_response[:50]}...")
                
                return {
                    "success": True,
                    "response": chatgpt_response,
                    "raw_data": result,
                    "tokens_used": result.get('usage', {}).get('total_tokens', 0)
                }
            
            else:
                logger.error(f"Erro na API ChatGPT: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API Error: {response.status_code}",
                    "raw_data": response.text
                }
                
        except Exception as e:
            logger.error(f"Erro ao gerar resposta ChatGPT para {contact_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "raw_data": None
            }
    

    
    def _get_bot_integration_type(self, contact_id):
        """Busca o tipo de integração do bot associado ao contato"""
        try:
            def _get_integration_type_operation(connection):
                cursor = connection.cursor(dictionary=True)
                query = """
                    SELECT i.integration_type 
                    FROM contacts co
                    JOIN conversation conv ON co.id = conv.contact_id AND conv.status = 'active'
                    JOIN channels ch ON conv.channel_id = ch.id
                    JOIN bots b ON ch.bot_id = b.id
                    LEFT JOIN integrations i ON b.integration_id = i.id
                    WHERE co.id = %s
                    LIMIT 1
                """
                cursor.execute(query, (contact_id,))
                result = cursor.fetchone()
                cursor.close()
                return result
            
            integration_result = db_manager._execute_with_fresh_connection(_get_integration_type_operation)
            if integration_result:
                integration_type = integration_result.get('integration_type')
                logger.info(f"🔍 Tipo de integração do bot para contato {contact_id}: {integration_type}")
                return integration_type
            else:
                logger.info(f"🔍 Nenhuma integração encontrada para contato {contact_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar tipo de integração: {e}")
            return None
    
    def _process_registrar_email(self, contact_id, function_args, result):
        """Processa a function registrar_email_cliente"""
        try:
            import json
            from datetime import datetime
            
            # Parse dos argumentos da function
            args = json.loads(function_args)
            # ChatGPT pode enviar 'email' ou 'e-mail'
            email = args.get('email') or args.get('e-mail')
            
            if not email:
                logger.error("Email não encontrado nos argumentos da function")
                return {
                    "success": False,
                    "error": "Email não fornecido",
                    "raw_data": result
                }
            
            # Validar formato do email básico
            if '@' not in email or '.' not in email:
                logger.error(f"Email inválido fornecido: {email}")
                return {
                    "success": False,
                    "error": "Email em formato inválido",
                    "raw_data": result
                }
            
            # Salvar email no banco
            success = db_manager.update_contact_email(contact_id, email)
            
            if success:
                logger.info(f"Email {email} salvo com sucesso para contato {contact_id}")
                
                # Verificar se o bot tem integração com Movidesk antes de integrar
                integration_type = self._get_bot_integration_type(contact_id)
                
                if integration_type == 'movidesk':
                # Integração com Movidesk - buscar ou criar pessoa
                    logger.info(f"🔗 INICIANDO integração Movidesk para {email} (bot com integração movidesk)")
                try:
                    from movidesk_service import movidesk_service
                    logger.info(f"🔗 Movidesk service importado com sucesso")
                    
                    # Verificar se token está configurado
                    if not movidesk_service.token:
                        logger.error(f"🔗 ❌ Token da Movidesk não configurado - pulando integração")
                    else:
                        logger.info(f"🔗 ✅ Token da Movidesk configurado")
                        
                        # Obter nome do contato para a Movidesk
                        contact = db_manager.get_contact(contact_id)
                        if contact and contact.get('name'):
                            contact_name = contact.get('name')
                        else:
                            contact_name = 'Usuário WhatsApp'
                        logger.info(f"🔗 Nome do contato: {contact_name}")
                        
                        # Buscar ou criar pessoa na Movidesk
                        logger.info(f"🔗 Chamando get_or_create_person({contact_name}, {email})")
                        person_id = movidesk_service.get_or_create_person(contact_name, email)
                        
                        if person_id:
                            logger.info(f"🔗 ✅ Person_id obtido da Movidesk: {person_id}")
                            # Atualizar person_id no banco
                            person_update_success = db_manager.update_contact_person_id(contact_id, person_id)
                            if person_update_success:
                                logger.info(f"🔗 ✅ Person_id {person_id} da Movidesk salvo para contato {contact_id}")
                            else:
                                logger.error(f"🔗 ❌ Falha ao salvar person_id da Movidesk para contato {contact_id}")
                        else:
                            logger.error(f"🔗 ❌ Não foi possível obter person_id da Movidesk para {email}")
                        
                except Exception as movidesk_error:
                    logger.error(f"🔗 ❌ ERRO na integração com Movidesk para {email}: {movidesk_error}")
                    import traceback
                    logger.error(f"🔗 ❌ Traceback: {traceback.format_exc()}")
                    # Não falha o processo principal, apenas log do erro
                else:
                    logger.info(f"🔗 Bot não tem integração Movidesk (tipo: {integration_type}) - pulando integração")
                
                # Adicionar ao cache para evitar futuras consultas ao banco
                self._email_cache.add(contact_id)
                logger.info(f"Email registrado - adicionando {contact_id} ao cache")
                
                # Email registrado com sucesso - processo interno transparente
                logger.info(f"✅ Email {email} registrado silenciosamente para contato {contact_id}")
                
                # Salvar mensagem de função no contexto (sender='function') - não envia WhatsApp
                try:
                    conversation = db_manager.get_active_conversation(contact_id)
                    if conversation:
                        function_message = f"Email do usuario registrado: {email}"
                        tokens_used = result.get('usage', {}).get('total_tokens', 0) if result else 0
                        
                        success_save = db_manager.insert_conversation_message(
                            conversation_id=conversation['id'],
                            message_text=function_message,
                            sender='function',  # Tipo especial para contexto apenas
                            message_type='function_result',
                            timestamp=datetime.now(),
                            tokens=tokens_used
                        )
                        
                        if success_save:
                            logger.info(f"💾 Mensagem de função salva para contexto: {function_message}")
                        else:
                            logger.warning(f"⚠️ Falha ao salvar mensagem de função")
                except Exception as save_error:
                    logger.error(f"❌ Erro ao salvar mensagem de função: {save_error}")
                
                # Retornar sem resposta para registro completamente silencioso
                return {
                        "success": True,
                    "response": None,  # Nenhuma mensagem - registro totalmente silencioso
                        "raw_data": result,
                    "tokens_used": result.get('usage', {}).get('total_tokens', 0) if result else 0,
                    "function_executed": False,  # IMPORTANTE: False = ChatGPT continua a conversa
                    "email_registered": email
                    }
            else:
                logger.error(f"Erro ao salvar email no banco para {contact_id}")
                return {
                    "success": False,
                    "error": "Erro ao salvar email no banco",
                    "raw_data": result
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao fazer parse dos argumentos da function: {e}")
            return {
                "success": False,
                "error": "Argumentos da function inválidos",
                "raw_data": result
            }
        except Exception as e:
            logger.error(f"Erro ao processar registrar_email_cliente: {e}")
            return {
                "success": False,
                "error": str(e),
                "raw_data": result
            }
    
    def _process_criar_ticket(self, contact_id, function_args, result):
        """Processa a function criar_ticket_atendimento"""
        try:
            import json
            import requests
            from config import MOVIDESK_TOKEN
            
            # Parse dos argumentos da function
            args = json.loads(function_args)
            assunto = args.get('assunto')
            solicitacao = args.get('solicitacao')
            servico = args.get('servico')
            
            logger.info(f"🎫 Criando ticket - Assunto: {assunto}, Serviço: {servico}")
            
            if not all([assunto, solicitacao, servico]):
                logger.error("Dados insuficientes para criar ticket")
                return {
                    "success": False,
                    "error": "Dados insuficientes para criar ticket",
                    "raw_data": result
                }
            
            # Validar tipo de serviço
            servicos_validos = ['Problema', 'Auxílio com Dúvidas', 'Solicitação de Customizações']
            if servico not in servicos_validos:
                logger.error(f"Tipo de serviço inválido: {servico}")
                return {
                    "success": False,
                    "error": f"Tipo de serviço inválido: {servico}",
                    "raw_data": result
                }
            
            # Obter informações do contato
            contact = db_manager.get_contact(contact_id)
            if not contact or not contact.get('person_id'):
                logger.error(f"Contato {contact_id} não tem person_id cadastrado")
                return {
                    "success": False,
                    "error": "Contato não possui person_id para criação de ticket",
                    "raw_data": result
                }
            
            person_id = contact['person_id']
            logger.info(f"🎫 Person ID encontrado: {person_id}")
            
            # Configurar urgência baseada no tipo de serviço
            urgency = "01 - Urgente" if servico == "Problema" else "02 - Alta"
            
            # Configurar serviceFirstLevelId baseado no tipo de serviço
            service_mapping = {
                "Auxílio com Dúvidas": 1010545,
                "Solicitação de Customizações": 28607,
                "Problema": 1010496
            }
            service_first_level_id = service_mapping[servico]
            
            # Montar payload para API do Movidesk
            ticket_payload = {
                "type": 2,
                "subject": assunto,
                "urgency": urgency,
                "status": "Novo",
                "origin": 18,
                "serviceFirstLevelId": service_first_level_id,
                "createdBy": {
                    "id": person_id
                },
                "clients": [
                    {
                        "id": person_id
                    }
                ],
                "actions": [
                    {
                        "type": 2,
                        "origin": 9,
                        "description": solicitacao,
                        "createdBy": {
                            "id": person_id
                        }
                    }
                ]
            }
            
            # Fazer requisição para API do Movidesk
            headers = {
                "Content-Type": "application/json"
            }
            
            movidesk_url = f"https://api.movidesk.com/public/v1/tickets?token={MOVIDESK_TOKEN}"
            
            logger.info(f"🎫 Enviando ticket para Movidesk...")
            logger.info(f"🎫 URL: {movidesk_url[:50]}...")
            logger.info(f"🎫 Payload: {json.dumps(ticket_payload, indent=2)}")
            
            response = requests.post(
                movidesk_url,
                headers=headers,
                json=ticket_payload,
                timeout=30
            )
            
            if response.status_code == 200 or response.status_code == 201:
                ticket_response = response.json()
                ticket_id = ticket_response.get('id')
                
                if ticket_id:
                    logger.info(f"🎫 ✅ Ticket {ticket_id} criado com sucesso!")
                    
                    # Upload de anexos se existirem
                    try:
                        conversation = db_manager.get_active_conversation(contact_id)
                        if conversation:
                            conversation_id = conversation['id']
                            attachments = db_manager.get_conversation_attachments(conversation_id)
                            
                            if attachments:
                                logger.info(f"📎 Encontrados {len(attachments)} anexos para fazer upload")
                                self._upload_attachments_to_movidesk(ticket_id, attachments)
                            else:
                                logger.info(f"📎 Nenhum anexo encontrado para o ticket {ticket_id}")
                        else:
                            logger.warning(f"⚠️ Conversa ativa não encontrada para buscar anexos")
                    except Exception as attach_error:
                        logger.error(f"❌ Erro ao processar anexos: {attach_error}")
                        # Não falhar o processo principal por erro nos anexos
                    
                    # Enviar mensagem de confirmação no WhatsApp
                    mensagem_confirmacao = f"Pronto! ✅ Ticket {ticket_id} incluído com sucesso! 👍 Sua solicitação será analisada e em breve receberá retorno. Atendimento finalizado."
                    
                    # Importar serviço WhatsApp e enviar mensagem
                    try:
                        from whatsapp_service import whatsapp_service
                        enviado = whatsapp_service.process_outgoing_message(contact_id, mensagem_confirmacao)
                        if enviado:
                            logger.info(f"📤 Mensagem de confirmação enviada para {contact_id}")
                        else:
                            logger.error(f"❌ Falha ao enviar mensagem de confirmação para {contact_id}")
                    except Exception as whatsapp_error:
                        logger.error(f"❌ Erro ao enviar mensagem WhatsApp: {whatsapp_error}")
                    
                    # Fechar a conversa
                    try:
                        conversation = db_manager.get_active_conversation(contact_id)
                        if conversation:
                            conversation_id = conversation['id']
                            
                            # Salvar a mensagem de confirmação na conversa (com prefixo)
                            mensagem_confirmacao_with_prefix = f"*Plugger Assistente:*\n{mensagem_confirmacao}"
                            db_manager.insert_conversation_message(
                                conversation_id=conversation_id,
                                message_text=mensagem_confirmacao_with_prefix,
                                sender='agent',
                                message_type='text',
                                timestamp=datetime.now()
                            )
                            
                            # Fechar a conversa
                            fechou = db_manager.close_conversation(conversation_id)
                            if fechou:
                                logger.info(f"🔒 Conversa {conversation_id} fechada com sucesso")
                            else:
                                logger.error(f"❌ Erro ao fechar conversa {conversation_id}")
                        else:
                            logger.warning(f"⚠️ Nenhuma conversa ativa encontrada para fechar para {contact_id}")
                    except Exception as close_error:
                        logger.error(f"❌ Erro ao fechar conversa: {close_error}")
                    
                    return {
                        "success": True,
                        "response": mensagem_confirmacao,
                        "raw_data": result,
                        "tokens_used": result.get('usage', {}).get('total_tokens', 0),
                        "function_executed": True,
                        "ticket_id": ticket_id
                    }
                else:
                    logger.error(f"❌ Ticket criado mas ID não retornado: {ticket_response}")
                    return {
                        "success": False,
                        "error": "Ticket criado mas ID não retornado",
                        "raw_data": result
                    }
            else:
                logger.error(f"❌ Erro na API Movidesk: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Erro na API Movidesk: {response.status_code}",
                    "raw_data": result
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erro ao fazer parse dos argumentos da function: {e}")
            return {
                "success": False,
                "error": "Argumentos da function inválidos",
                "raw_data": result
            }
        except Exception as e:
            logger.error(f"❌ Erro ao processar criar_ticket_atendimento: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "raw_data": result
            }
    
    def _get_function_action(self, contact_id, function_name):
        """Busca a ação de uma função no banco de dados"""
        try:
            # Primeiro, buscar o bot_id através do contact_id
            contact = db_manager.get_contact(contact_id)
            if not contact:
                logger.error(f"Contato {contact_id} não encontrado")
                return None
                
            # Buscar conversa ativa para obter o bot_id
            def _get_bot_id_operation(connection):
                cursor = connection.cursor(dictionary=True)
                query = """
                    SELECT ch.bot_id 
                    FROM conversation conv
                    JOIN channels ch ON conv.channel_id = ch.id
                    WHERE conv.contact_id = %s 
                    AND conv.status = 'active'
                    ORDER BY conv.started_at DESC
                    LIMIT 1
                """
                cursor.execute(query, (contact_id,))
                result = cursor.fetchone()
                cursor.close()
                return result
            
            bot_result = db_manager._execute_with_fresh_connection(_get_bot_id_operation)
            if not bot_result:
                logger.error(f"Bot ID não encontrado para contato {contact_id}")
                return None
                
            bot_id = bot_result['bot_id']
            logger.info(f"🔍 Bot ID encontrado: {bot_id} para função {function_name}")
            
            # Buscar a ação na tabela bots_functions
            def _get_function_action_operation(connection):
                cursor = connection.cursor(dictionary=True)
                query = """
                    SELECT action 
                    FROM bots_functions 
                    WHERE bot_id = %s AND function_id = %s
                """
                cursor.execute(query, (bot_id, function_name))
                result = cursor.fetchone()
                cursor.close()
                return result
            
            action_result = db_manager._execute_with_fresh_connection(_get_function_action_operation)
            if action_result:
                action = action_result['action']
                logger.info(f"🎯 Ação encontrada para função {function_name}: {action}")
                return action
            else:
                logger.warning(f"❌ Ação não encontrada para função {function_name} no bot {bot_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar ação da função {function_name}: {e}")
            return None
    
    def _process_function_by_action(self, contact_id, function_name, function_args, result):
        """Processa função baseado no campo action do banco"""
        try:
            logger.info(f"🚀 Processando função {function_name} baseado na ação do banco")
            
            # Buscar ação da função no banco
            action = self._get_function_action(contact_id, function_name)
            
            if not action:
                logger.warning(f"⚠️ Função {function_name} sem ação definida, executando simulação")
                return self._execute_generic_function(function_name, function_args, result)
            
            logger.info(f"🎯 Executando ação: {action} para função {function_name}")
            
            # Dispatcher de ações
            if action == "cria_ticket_movidesk":
                return self._execute_action_cria_ticket_movidesk(contact_id, function_args, result)
            elif action == "registrar_email_cliente":
                return self._process_registrar_email(contact_id, function_args, result)
            else:
                logger.warning(f"⚠️ Ação '{action}' não implementada para função {function_name}")
                return self._execute_generic_function(function_name, function_args, result)
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar função {function_name} por ação: {e}")
            return {
                "success": False,
                "error": f"Erro ao processar função: {str(e)}",
                "raw_data": result
            }
    
    def _execute_action_cria_ticket_movidesk(self, contact_id, function_args, result):
        """Executa a ação de criar ticket no Movidesk"""
        logger.info(f"🎫 Executando ação: cria_ticket_movidesk")
        
        # Verificar se o bot tem integração com Movidesk
        integration_type = self._get_bot_integration_type(contact_id)
        
        if integration_type != 'movidesk':
            logger.error(f"❌ Tentativa de criar ticket Movidesk com bot de integração '{integration_type}' - operação não permitida")
            return {
                "success": False,
                "error": f"Bot não tem integração Movidesk (tipo: {integration_type})",
                "raw_data": result
            }
        
        # Verificar se contato tem person_id, se não tiver, buscar/criar na Movidesk
        contact = db_manager.get_contact(contact_id)
        if not contact:
            logger.error(f"Contato {contact_id} não encontrado")
            return {
                "success": False,
                "error": "Contato não encontrado",
                "raw_data": result
            }
        
        person_id = contact.get('person_id')
        
        # Se não tem person_id, tentar buscar/criar na Movidesk usando o email
        if not person_id and contact.get('email'):
            logger.info(f"🔗 Contato sem person_id, buscando/criando na Movidesk para {contact['email']}")
            from movidesk_service import MovideskService
            movidesk_service = MovideskService()
            
            contact_name = contact.get('name', 'Usuário WhatsApp')
            person_id = movidesk_service.get_or_create_person(contact_name, contact['email'])
            
            if person_id:
                logger.info(f"🔗 ✅ Person_id obtido da Movidesk: {person_id}")
                # Atualizar person_id no banco
                person_update_success = db_manager.update_contact_person_id(contact_id, person_id)
                if person_update_success:
                    logger.info(f"🔗 ✅ Person_id {person_id} da Movidesk salvo para contato {contact_id}")
                else:
                    logger.error(f"🔗 ❌ Falha ao salvar person_id da Movidesk para contato {contact_id}")
            else:
                logger.error(f"🔗 ❌ Não foi possível obter person_id da Movidesk para {contact['email']}")
        
        # Agora chamar a função original de criar ticket
        return self._process_criar_ticket(contact_id, function_args, result)
    
    def _execute_generic_function(self, function_name, function_args, result):
        """Executa função genérica quando não há ação específica implementada"""
        logger.info(f"🔧 Executando função genérica: {function_name}")
        
        try:
            import json
            args_dict = json.loads(function_args) if isinstance(function_args, str) else function_args
            response_text = f"Função {function_name} executada com os parâmetros: {args_dict}"
        except:
            response_text = f"Função {function_name} executada com sucesso."
        
        return {
            "success": True,
            "response": response_text,
            "function_executed": True,
            "function_name": function_name,
            "raw_data": result,
            "tokens_used": result.get('usage', {}).get('total_tokens', 0) if result else 0,
            "request_payload": {}
            }
    
    def process_message(self, contact_id, message_text=None):
        """Processa uma mensagem e retorna resposta do ChatGPT"""
        logger.info(f"Processando mensagem de {contact_id}: {str(message_text)[:50] if message_text else 'None'}...")
        # Gerar resposta
        result = self.generate_response(contact_id, message_text)
        if result and result.get("success"):
            logger.info(f"Resposta ChatGPT gerada para {contact_id}")
            return result  # Retornar objeto completo em vez de apenas a string
        else:
            logger.error(f"Falha ao gerar resposta ChatGPT: {result.get('error', 'Erro desconhecido') if result else 'Erro desconhecido'}")
            return {
                "success": False,
                "response": "Desculpe, não consegui processar sua mensagem no momento. Tente novamente.",
                "error": result.get('error', 'Erro desconhecido') if result else 'Erro desconhecido'
            }
    
    def process_message_with_config(self, contact_id, message_text=None, system_prompt=None, chatgpt_functions=None):
        """Processa uma mensagem com configuração customizada (system_prompt e funções do bot)"""
        logger.info(f"Processando mensagem customizada de {contact_id}: {str(message_text)[:50] if message_text else 'None'}...")
        logger.info(f"System prompt customizado: {bool(system_prompt)}, Funções: {len(chatgpt_functions or [])}")
        
        # Gerar resposta com configuração customizada
        result = self.generate_response_with_config(contact_id, message_text, system_prompt, chatgpt_functions)
        if result and result.get("success"):
            logger.info(f"Resposta ChatGPT customizada gerada para {contact_id}")
            return result
        else:
            logger.error(f"Falha ao gerar resposta ChatGPT customizada: {result.get('error', 'Erro desconhecido') if result else 'Erro desconhecido'}")
            return {
                "success": False,
                "response": "Desculpe, não consegui processar sua mensagem no momento. Tente novamente.",
                "error": result.get('error', 'Erro desconhecido') if result else 'Erro desconhecido'
            }
    
    def generate_response_with_config(self, contact_id, user_message=None, system_prompt=None, chatgpt_functions=None):
        """Gera resposta usando configuração customizada do bot"""
        try:
            # Montar contexto da conversa usando system_prompt customizado
            conversation = []
            
            # System prompt customizado do bot
            if system_prompt:
                # Verificar se system_prompt já é JSON formatado
                try:
                    import json
                    if isinstance(system_prompt, str) and system_prompt.startswith('{"role":'):
                        # JSON pronto, usar diretamente
                        system_prompt_obj = json.loads(system_prompt)
                        conversation.append(system_prompt_obj)
                        logger.info(f"Usando system prompt JSON pronto ({len(system_prompt)} caracteres)")
                    else:
                        # Formato antigo (texto), formatar para JSON
                        conversation.append({
                            "role": "system",
                            "content": system_prompt
                        })
                        logger.info(f"Usando system prompt customizado ({len(system_prompt)} caracteres)")
                except (json.JSONDecodeError, TypeError):
                    # Fallback para formato antigo
                    conversation.append({
                        "role": "system",
                        "content": system_prompt
                    })
                    logger.info(f"Usando system prompt customizado (fallback) ({len(system_prompt)} caracteres)")
            else:
                # Fallback para system prompt padrão
                conversation.append({
                    "role": "system",
                    "content": "Você é um assistente útil."
                })
                logger.info("Usando system prompt padrão (fallback)")
            
            # Buscar histórico da conversa
            try:
                conversation_msgs = db_manager.get_conversation_context(contact_id, limit=10)
                
                for msg in conversation_msgs:
                    if msg['sender'] == 'user':
                        conversation.append({
                            "role": "user",
                            "content": msg['message_text']
                        })
                    elif msg['sender'] == 'agent':
                        # Remover prefixo antes de adicionar ao contexto
                        content = msg['message_text']
                        if content.startswith("*Plugger Assistente:*\n"):
                            content = content[len("*Plugger Assistente:*\n"):]
                        conversation.append({
                            "role": "assistant",
                            "content": content
                        })
                
                logger.info(f"Adicionadas {len(conversation_msgs)} mensagens do histórico")
                
            except Exception as e:
                logger.warning(f"Erro ao buscar contexto da conversa: {e}")
            
            # Adicionar mensagem atual do usuário
            if user_message and user_message.strip():
                conversation.append({
                    "role": "user",
                    "content": user_message
                })
            
            # Configurar headers
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Configurar payload base
            payload = {
                "model": self.model,
                "messages": conversation,
                "max_tokens": self.max_tokens,
                "temperature": 0.7,
                "top_p": 1,
                "frequency_penalty": 0,
                "presence_penalty": 0
            }
            
            # Adicionar tools customizadas do bot (novo formato ChatGPT)
            if chatgpt_functions and len(chatgpt_functions) > 0:
                payload["tools"] = chatgpt_functions
                payload["tool_choice"] = "auto"
                logger.info(f"Adicionadas {len(chatgpt_functions)} tools customizadas do bot")
                
                # Log das tools para debug
                for tool in chatgpt_functions:
                    if tool.get('type') == 'function' and 'function' in tool:
                        func_name = tool['function'].get('name', 'N/A')
                        func_desc = tool['function'].get('description', 'N/A')[:50]
                        logger.info(f"  Tool: {func_name} - {func_desc}...")
                    else:
                        # Fallback para formato antigo
                        func_name = tool.get('name', 'N/A')
                        func_desc = tool.get('description', 'N/A')[:50]
                        logger.info(f"  Tool (formato antigo): {func_name} - {func_desc}...")
            
            # Log detalhado das mensagens
            logger.info("=== MENSAGENS CUSTOMIZADAS PARA CHATGPT ===")
            for i, msg in enumerate(conversation):
                content_preview = msg.get('content', '')[:100] if msg.get('content') else 'NULL/EMPTY'
                logger.info(f"Msg {i+1}: role={msg.get('role')}, content='{content_preview}...'")
            
            logger.info(f"Enviando {len(conversation)} mensagens customizadas para ChatGPT")
            
            # Fazer requisição para ChatGPT
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Verificar se há tool_calls na resposta (formato moderno)
                message = result['choices'][0]['message']
                
                if 'tool_calls' in message and message['tool_calls']:
                    tool_call = message['tool_calls'][0]  # Primeira tool call
                    logger.info(f"ChatGPT retornou tool_call: {tool_call['function']['name']}")
                    return self._process_custom_tool_call(contact_id, message, result, chatgpt_functions)
                else:
                    # Resposta normal de texto
                    chatgpt_response = message['content'].strip()
                    logger.info(f"ChatGPT customizado respondeu para {contact_id}: {chatgpt_response[:50]}...")
                
                return {
                    "success": True,
                    "response": chatgpt_response,
                    "raw_data": result,
                    "tokens_used": result.get('usage', {}).get('total_tokens', 0),
                    "request_payload": payload
                }
            
            else:
                logger.error(f"Erro na API ChatGPT customizada: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API Error: {response.status_code}",
                    "raw_data": response.text
                }
                
        except Exception as e:
            logger.error(f"Erro ao gerar resposta ChatGPT customizada para {contact_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "raw_data": None
            }
    
    def _process_custom_tool_call(self, contact_id, message, result, available_functions):
        """Processa tool_calls customizadas do bot (novo formato ChatGPT)"""
        try:
            import json
            tool_call = message['tool_calls'][0]  # Primeira tool call
            function_name = tool_call['function']['name']
            function_args = tool_call['function']['arguments']
            
            logger.info(f"Processando tool_call customizada: {function_name} com args: {function_args}")
            
            # Verificar se a função está disponível
            function_found = False
            for tool in available_functions or []:
                if tool.get('type') == 'function' and 'function' in tool:
                    if tool['function'].get('name') == function_name:
                        function_found = True
                        break
                elif tool.get('name') == function_name:  # Fallback para formato antigo
                    function_found = True
                    break
            
            if not function_found:
                logger.warning(f"Tool customizada não encontrada: {function_name}")
                return {
                    "success": False,
                    "error": f"Tool não reconhecida: {function_name}",
                    "raw_data": result
                }
            
            # Buscar ação da função no banco e processar dinamicamente
            return self._process_function_by_action(contact_id, function_name, function_args, result)
                
        except Exception as e:
            logger.error(f"Erro ao processar tool_call customizada: {e}")
            return {
                "success": False,
                "error": str(e),
                "raw_data": result
            }



    def _upload_attachments_to_movidesk(self, ticket_id, attachments):
        """Faz upload dos anexos para o ticket no Movidesk"""
        try:
            import requests
            import tempfile
            import os
            from config import MOVIDESK_TOKEN
            
            logger.info(f"📎 Iniciando upload de {len(attachments)} anexos para ticket {ticket_id}")
            
            # Importar serviços necessários
            from whatsapp_service import whatsapp_service
            
            # Obter token de acesso do WhatsApp
            access_token = whatsapp_service.get_access_token()
            if not access_token:
                logger.error("❌ Token WhatsApp não disponível para download de anexos")
                return
            
            uploaded_count = 0
            image_counter = 0  # Contador para imagens
            
            for i, attachment in enumerate(attachments, 1):
                try:
                    file_url = attachment.get('file_url')
                    file_type = attachment.get('file_type')
                    file_name = attachment.get('file_name')
                    file_extension = attachment.get('file_extension')
                    
                    # Determinar nome do arquivo baseado no tipo
                    if file_type == 'document' and file_name:
                        # Para documentos: usar o nome original do arquivo
                        upload_filename = file_name
                    elif file_type == 'image':
                        # Para imagens: usar image1, image2, etc + extensão
                        image_counter += 1
                        if file_extension and file_extension.startswith('.'):
                            upload_filename = f"image{image_counter}{file_extension}"
                        else:
                            upload_filename = f"image{image_counter}.jpg"  # fallback
                    elif file_type == 'audio':
                        # Para áudios: usar audio1, audio2, etc + extensão
                        if file_extension and file_extension.startswith('.'):
                            upload_filename = f"audio{i}{file_extension}"
                        else:
                            upload_filename = f"audio{i}.ogg"  # fallback
                    else:
                        # Fallback genérico
                        upload_filename = file_name or f"anexo_{i}.{file_type}"
                    
                    logger.info(f"📎 Processando anexo {i}/{len(attachments)}: {upload_filename} (tipo: {file_type})")
                    
                    # 1. Fazer download do arquivo do WhatsApp
                    temp_file_path = self._download_whatsapp_file(file_url, access_token, upload_filename)
                    if not temp_file_path:
                        logger.error(f"❌ Falha no download do anexo {i}")
                        continue
                    
                    # 2. Fazer upload para Movidesk
                    upload_success = self._upload_file_to_movidesk(ticket_id, temp_file_path, upload_filename)
                    
                    # 3. Limpar arquivo temporário
                    try:
                        os.unlink(temp_file_path)
                        logger.debug(f"🧹 Arquivo temporário removido: {temp_file_path}")
                    except:
                        pass
                    
                    if upload_success:
                        uploaded_count += 1
                        logger.info(f"✅ Anexo {i} enviado com sucesso: {upload_filename}")
                    else:
                        logger.error(f"❌ Falha no upload do anexo {i}: {upload_filename}")
                        
                except Exception as attach_error:
                    logger.error(f"❌ Erro ao processar anexo {i}: {attach_error}")
                    continue
            
            logger.info(f"📎 Upload concluído: {uploaded_count}/{len(attachments)} anexos enviados")
            
        except Exception as e:
            logger.error(f"❌ Erro geral no upload de anexos: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")

    def _download_whatsapp_file(self, file_url, access_token, file_name):
        """Faz download de arquivo do WhatsApp usando credenciais"""
        try:
            import requests
            import tempfile
            import os
            
            logger.info(f"⬇️ Fazendo download de: {file_url[:50]}...")
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(file_url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            
            # Criar arquivo temporário com extensão correta
            file_extension = os.path.splitext(file_name)[1] or '.tmp'
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
            
            # Baixar em chunks
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
            
            temp_file.close()
            
            file_size = os.path.getsize(temp_file.name)
            logger.info(f"✅ Download concluído: {file_size/1024:.1f}KB")
            
            return temp_file.name
            
        except Exception as e:
            logger.error(f"❌ Erro no download: {e}")
            return None

    def _upload_file_to_movidesk(self, ticket_id, file_path, file_name):
        """Faz upload do arquivo para o Movidesk"""
        try:
            import requests
            from config import MOVIDESK_TOKEN
            
            logger.info(f"⬆️ Fazendo upload para Movidesk: {file_name}")
            
            # URL do endpoint de upload
            upload_url = f"https://api.movidesk.com/public/v1/ticketFileUpload?token={MOVIDESK_TOKEN}&id={ticket_id}&actionId=1"
            
            # Preparar arquivo para upload
            with open(file_path, 'rb') as file:
                files = {
                    'file': (file_name, file, 'application/octet-stream')
                }
                
                headers = {
                    # Não definir Content-Type manualmente - requests fará automaticamente para multipart/form-data
                    'User-Agent': 'WhatsApp-Bot/1.0'
                }
                
                logger.info(f"📤 Enviando para: {upload_url[:50]}...")
                
                response = requests.post(
                    upload_url,
                    files=files,
                    headers=headers,
                    timeout=60
                )
            
            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"✅ Upload bem-sucedido para Movidesk: {file_name}")
                return True
            else:
                logger.error(f"❌ Erro no upload Movidesk: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro no upload para Movidesk: {e}")
            return False

# Instância global do serviço ChatGPT
chatgpt_service = ChatGPTService() 