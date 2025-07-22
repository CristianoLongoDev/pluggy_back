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
    
    def generate_response(self, contact_id, user_message=None):
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
                
                # Adicionar ao cache para evitar futuras consultas ao banco
                self._email_cache.add(contact_id)
                logger.info(f"Email registrado - adicionando {contact_id} ao cache")
                
                # Em vez de resposta fixa, gerar nova resposta com contexto completo
                logger.info(f"Email registrado - gerando nova resposta com contexto para {contact_id}")
                
                # Fazer nova chamada ao ChatGPT sem function de email, mas com contexto completo
                new_result = self.generate_response(contact_id, None)
                
                if new_result and new_result.get("success"):
                    return {
                        "success": True,
                        "response": new_result.get("response"),
                        "raw_data": new_result.get("raw_data", result),
                        "tokens_used": result.get('usage', {}).get('total_tokens', 0) + new_result.get('tokens_used', 0),
                        "function_executed": True
                    }
                else:
                    # Fallback para resposta padrão se nova chamada falhar
                    logger.warning(f"Nova chamada ChatGPT falhou, usando resposta padrão")
                    return {
                        "success": True,
                        "response": f"Obrigado! Seu email {email} foi registrado com sucesso. Como posso ajudá-lo hoje?",
                        "raw_data": result,
                        "tokens_used": result.get('usage', {}).get('total_tokens', 0),
                        "function_executed": True
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
    
    def process_message(self, contact_id, message_text=None):
        """Processa uma mensagem e retorna resposta do ChatGPT"""
        logger.info(f"Processando mensagem de {contact_id}: {str(message_text)[:50] if message_text else 'None'}...")
        # Gerar resposta
        result = self.generate_response(contact_id, message_text)
        if result and result.get("success"):
            logger.info(f"Resposta ChatGPT gerada para {contact_id}")
            return result.get("response", "Desculpe, não consegui processar sua mensagem no momento. Tente novamente.")
        else:
            logger.error(f"Falha ao gerar resposta ChatGPT: {result.get('error', 'Erro desconhecido') if result else 'Erro desconhecido'}")
            return "Desculpe, não consegui processar sua mensagem no momento. Tente novamente."

# Instância global do serviço ChatGPT
chatgpt_service = ChatGPTService() 