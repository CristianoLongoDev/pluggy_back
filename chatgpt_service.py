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
        is_first_contact = False
        should_include_email_function = False
        
        try:
            # System prompt base
            system_prompt_config = db_manager.get_config('system_prompt')
            system_prompt = {
                "role": "system",
                "content": str(system_prompt_config.get('content', 'Você é um assistente útil.'))
            }
            
            # Verificar se é primeiro contato REAL (não apenas na conversa atual)
            try:
                conversation_msgs = db_manager.get_conversation_context(contact_id, limit)
                
                # Verificar se já existe alguma mensagem do agent/assistant na conversa atual
                has_agent_messages_current = any(msg.get('sender') == 'agent' for msg in conversation_msgs)
                
                # Verificar se o contato já existe no sistema (verdadeiro primeiro contato)
                contact = db_manager.get_contact(contact_id)
                contact_exists = contact is not None
                has_email = contact and contact.get('email') and contact.get('email').strip()

                # É primeiro contato REAL apenas se: contato não existe OU (contato existe mas nunca teve conversa com agent)
                is_first_contact = not contact_exists or (contact_exists and not has_email and not has_agent_messages_current)
                
                logger.info(f"Análise de primeiro contato para {contact_id}:")
                logger.info(f"  - Contato existe: {contact_exists}")
                logger.info(f"  - Tem email: {has_email}")
                logger.info(f"  - Mensagens do agent na conversa atual: {has_agent_messages_current}")
                logger.info(f"  - É primeiro contato: {is_first_contact}")
                
            except Exception as e:
                logger.warning(f"Erro ao verificar se é primeiro contato: {e}")
                # Em caso de erro, considera como primeiro contato para garantir boa experiência
                is_first_contact = True
                contact_exists = False
                has_email = False
            
            # Verificar se email foi registrado (usando dados já obtidos para otimização)
            should_include_email_function = False
            
            # Se já está no cache, não precisa consultar banco
            if contact_id in self._email_cache:
                logger.info(f"Contato {contact_id} tem email registrado (cache) - não incluindo function")
                should_include_email_function = False
            elif 'has_email' in locals() and has_email:
                # Usar informação já obtida na análise de primeiro contato
                logger.info(f"Contato {contact_id} tem email registrado (já verificado) - não incluindo function")
                # Adicionar ao cache para futuras otimizações
                self._email_cache.add(contact_id)
                should_include_email_function = False
            elif 'has_email' in locals() and not has_email:
                # Usar informação já obtida - não tem email
                logger.info(f"Contato {contact_id} não tem email registrado - incluindo function")
                should_include_email_function = True
            else:
                # Fallback - consultar banco apenas se não foi verificado anteriormente
                try:
                    contact = db_manager.get_contact(contact_id)
                    has_email_fallback = contact and contact.get('email') and contact.get('email').strip()
                    logger.info(f"Contato {contact_id} tem email registrado (fallback): {has_email_fallback}")
                    
                    if has_email_fallback:
                        # Adicionar ao cache para evitar futuras consultas
                        self._email_cache.add(contact_id)
                        logger.info(f"Email encontrado - adicionando {contact_id} ao cache")
                        should_include_email_function = False
                    else:
                        # Ainda não tem email - incluir function
                        should_include_email_function = True
                        logger.info(f"Email não encontrado - incluindo function para {contact_id}")
                    
                except Exception as e:
                    logger.warning(f"Erro ao verificar email do contato: {e}")
                    # Em caso de erro, incluir function para garantir captura
                    should_include_email_function = True

            if is_first_contact:
                try:
                    # Adicionar first_contact_prompt
                    first_prompt = db_manager.get_config('first_contact_prompt')
                    if first_prompt and isinstance(first_prompt, dict) and first_prompt.get('content'):
                        logger.info(f"Adicionando prompt de primeiro contato para {contact_id}")
                        system_prompt['content'] += '\n' + str(first_prompt['content'])
                    else:
                        logger.warning(f"Prompt de primeiro contato não encontrado ou inválido: {first_prompt}")
                        
                except Exception as e:
                    logger.error(f"Erro ao buscar/aplicar prompts de primeiro contato: {e}")
            
            # Adicionar prompt de email enquanto não tiver email registrado
            if should_include_email_function:
                try:
                    email_prompt = db_manager.get_config('get_email_prompt')
                    if email_prompt and isinstance(email_prompt, dict) and email_prompt.get('content'):
                        logger.info(f"Adicionando prompt de captura de email para {contact_id}")
                        system_prompt['content'] += '\n' + str(email_prompt['content'])
                    else:
                        logger.warning(f"Prompt de captura de email não encontrado ou inválido: {email_prompt}")
                except Exception as e:
                    logger.error(f"Erro ao buscar/aplicar prompt de email: {e}")

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
            return conversation_list, should_include_email_function
            
        except Exception as e:
            logger.error(f"Erro ao montar contexto para {contact_id}: {e}")
            # Retornar contexto mínimo em caso de erro
            return [{"role": "system", "content": "Você é um assistente útil."}], False
    
    def generate_response(self, contact_id, user_message=None, ignore_cache=False):
        """Gera resposta usando ChatGPT"""
        try:
            # Montar contexto da conversa
            conversation, should_include_email_function = self.build_conversation_context(contact_id)
            
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
            
            # Adicionar functions se for primeiro contato
            if should_include_email_function:
                try:
                    email_function = db_manager.get_config('registrar_email_cliente')
                    if email_function:
                        # Se retornou uma lista, pegar o primeiro item
                        if isinstance(email_function, list) and len(email_function) > 0:
                            email_function = email_function[0]
                        
                        # Verificar se agora é um dict válido
                        if isinstance(email_function, dict) and 'name' in email_function:
                            payload["functions"] = [email_function]
                            payload["function_call"] = "auto"
                            logger.info(f"Adicionando function registrar_email_cliente para {contact_id}")
                        else:
                            logger.warning(f"Function registrar_email_cliente em formato inválido: {email_function}")
                    else:
                        logger.warning(f"Function registrar_email_cliente não encontrada ou inválida: {email_function}")
                except Exception as e:
                    logger.error(f"Erro ao adicionar function registrar_email_cliente: {e}")
            
            # Sempre incluir a função criar_ticket_atendimento para permitir criação de tickets
            try:
                ticket_function = db_manager.get_config('criar_ticket_atendimento')
                if ticket_function:
                    # Se retornou uma lista, pegar o primeiro item
                    if isinstance(ticket_function, list) and len(ticket_function) > 0:
                        ticket_function = ticket_function[0]
                    
                    # Verificar se é um dict válido
                    if isinstance(ticket_function, dict) and 'name' in ticket_function:
                        # Se já temos functions (email), adicionar à lista existente
                        if "functions" in payload:
                            payload["functions"].append(ticket_function)
                        else:
                            payload["functions"] = [ticket_function]
                            payload["function_call"] = "auto"
                        logger.info(f"Adicionando function criar_ticket_atendimento para {contact_id}")
                    else:
                        logger.warning(f"Function criar_ticket_atendimento em formato inválido: {ticket_function}")
                else:
                    logger.warning(f"Function criar_ticket_atendimento não encontrada")
            except Exception as e:
                logger.error(f"Erro ao adicionar function criar_ticket_atendimento: {e}")
            
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
                
                # Verificar se há function_call na resposta
                message = result['choices'][0]['message']
                
                if 'function_call' in message:
                    logger.info(f"ChatGPT retornou function_call: {message['function_call']['name']}")
                    return self._process_function_call(contact_id, message, result)
                else:
                    # Resposta normal de texto
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
    
    def _process_function_call(self, contact_id, message, result):
        """Processa function_calls do ChatGPT"""
        try:
            function_name = message['function_call']['name']
            function_args = message['function_call']['arguments']
            
            logger.info(f"Processando function_call: {function_name} com args: {function_args}")
            
            if function_name == 'registrar_email_cliente':
                return self._process_registrar_email(contact_id, function_args, result)
            elif function_name == 'criar_ticket_atendimento':
                return self._process_criar_ticket(contact_id, function_args, result)
            else:
                logger.warning(f"Function não reconhecida: {function_name}")
                return {
                    "success": False,
                    "error": f"Function não reconhecida: {function_name}",
                    "raw_data": result
                }
                
        except Exception as e:
            logger.error(f"Erro ao processar function_call: {e}")
            return {
                "success": False,
                "error": str(e),
                "raw_data": result
            }
    
    def _process_registrar_email(self, contact_id, function_args, result):
        """Processa a function registrar_email_cliente"""
        try:
            import json
            
            # Parse dos argumentos da function
            args = json.loads(function_args)
            email = args.get('email')
            
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
                
                # Integração com Movidesk - buscar ou criar pessoa
                logger.info(f"🔗 INICIANDO integração Movidesk para {email}")
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
                        contact_name = contact.get('name') if contact else contact_id
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
                
                # Adicionar ao cache para evitar futuras consultas ao banco
                self._email_cache.add(contact_id)
                logger.info(f"Email registrado - adicionando {contact_id} ao cache")
                
                # Gerar nova resposta contexto após registrar email
                logger.info(f"Email registrado - gerando nova resposta com contexto para {contact_id}")
                new_result = self.generate_response(contact_id, None, ignore_cache=True)
                
                if new_result and new_result.get("success"):
                    logger.info(f"Nova resposta gerada após registrar email: {new_result.get('response', '')[:100]}...")
                    return {
                        "success": True,
                        "response": new_result.get('response', ''),
                        "raw_data": new_result,
                        "tokens_used": new_result.get('tokens_used', 0),
                        "function_executed": False  # CORREÇÃO: Esta é uma resposta normal, não uma function
                    }
                else:
                    # Fallback para resposta padrão se nova chamada falhar
                    logger.warning(f"Nova chamada ChatGPT falhou, usando resposta padrão")
                    return {
                        "success": True,
                        "response": f"Obrigado! Seu email {email} foi registrado com sucesso. Como posso ajudá-lo hoje?",
                        "raw_data": result,
                        "tokens_used": result.get('usage', {}).get('total_tokens', 0),
                        "function_executed": False  # CORREÇÃO: Resposta padrão também não é function
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