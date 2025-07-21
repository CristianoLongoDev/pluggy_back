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
        
    def get_system_prompt(self):
        """Busca o prompt do sistema na configuração do banco"""
        try:
            system_prompt = db_manager.get_config('system_prompt')
            if system_prompt and isinstance(system_prompt, dict) and system_prompt.get('content'):
                return system_prompt
            else:
                # Prompt padrão se não estiver configurado ou inválido
                logger.warning(f"System prompt inválido no banco: {system_prompt}, usando padrão")
                return {
                    "role": "system",
                    "content": "Você é um assistente virtual amigável e prestativo. Responda de forma clara e objetiva em português brasileiro. Mantenha as respostas concisas (máximo 200 caracteres)."
                }
        except Exception as e:
            logger.error(f"Erro ao buscar system prompt: {e}")
            # Retorna prompt padrão em caso de erro
            return {
                "role": "system",
                "content": "Você é um assistente virtual amigável. Responda de forma objetiva em português."
            }
    
    def build_conversation_context(self, contact_id):
        """Monta o contexto da conversa com as últimas mensagens da conversa ativa. Se o contato for novo, inclui o first_contact_prompt no system_prompt."""
        try:
            # Buscar conversa ativa
            conversation = db_manager.get_active_conversation(contact_id)
            conversation_msgs = []
            if conversation:
                conversation_id = conversation['id']
                conversation_msgs = db_manager.get_conversation_messages(conversation_id, limit=10)

            conversation_list = []
            # Adicionar prompt do sistema
            system_prompt = self.get_system_prompt()

            # Verificar se é o primeiro contato (usuário completamente novo)
            # Considera primeiro contato se o usuário NUNCA recebeu uma resposta do agente
            is_first_contact = False
            try:
                # Verificar se existe alguma mensagem do agente para este contato em QUALQUER conversa
                has_agent_response = db_manager.has_agent_response_for_contact(contact_id)
                is_first_contact = not has_agent_response
                
                logger.info(f"Primeiro contato para {contact_id}: {is_first_contact}")
            except Exception as e:
                logger.warning(f"Erro ao verificar se é primeiro contato: {e}")
                # Em caso de erro, considera como primeiro contato para garantir boa experiência
                is_first_contact = True

            if is_first_contact:
                try:
                    first_prompt = db_manager.get_config('first_contact_prompt')
                    if first_prompt and isinstance(first_prompt, dict) and first_prompt.get('content'):
                        logger.info(f"Adicionando prompt de primeiro contato para {contact_id}")
                        system_prompt['content'] += '\n' + str(first_prompt['content'])
                    else:
                        logger.warning(f"Prompt de primeiro contato não encontrado ou inválido: {first_prompt}")
                except Exception as e:
                    logger.error(f"Erro ao buscar/aplicar first_contact_prompt: {e}")

            # Verificar se system_prompt tem content válido
            if not system_prompt.get('content'):
                logger.error("System prompt sem content válido!")
                system_prompt['content'] = "Você é um assistente útil."
            
            conversation_list.append(system_prompt)
            # Adicionar mensagens do contexto
            logger.info(f"Mensagens encontradas na conversa: {len(conversation_msgs)}")
            for i, msg in enumerate(conversation_msgs):
                logger.info(f"Mensagem {i+1}: sender={msg.get('sender')}, message_text='{msg.get('message_text')[:50] if msg.get('message_text') else None}...'")
                if msg['sender'] == 'user':
                    role = 'user'
                elif msg['sender'] == 'agent':
                    role = 'assistant'
                else:
                    continue
                
                # Verificar se message_text não é None ou vazio
                message_text = msg.get('message_text')
                if not message_text:
                    logger.warning(f"Mensagem com texto vazio/None ignorada: {msg.get('id', 'N/A')}")
                    continue
                    
                conversation_list.append({
                    "role": role,
                    "content": message_text
                })
            
            logger.info(f"Contexto montado para {contact_id}: {len(conversation_list)} mensagens")
            
            # Log detalhado das mensagens que serão enviadas ao ChatGPT
            logger.info("=== MENSAGENS PARA CHATGPT ===")
            for i, msg in enumerate(conversation_list):
                content_preview = msg.get('content', '')[:100] if msg.get('content') else 'NULL/EMPTY'
                logger.info(f"Msg {i+1}: role={msg.get('role')}, content='{content_preview}...'")
            logger.info("=== FIM MENSAGENS ===")
            
            return conversation_list
        except Exception as e:
            logger.error(f"Erro ao montar contexto para {contact_id}: {e}")
            # Retorna apenas o system prompt em caso de erro
            return [self.get_system_prompt()]
    
    def generate_response(self, contact_id, user_message=None):
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
            
            # Configurar payload
            payload = {
                "model": self.model,
                "messages": conversation,
                "max_tokens": self.max_tokens,
                "temperature": 0.7,
                "top_p": 1,
                "frequency_penalty": 0,
                "presence_penalty": 0
            }
            
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
                
                # Extrair resposta
                chatgpt_response = result['choices'][0]['message']['content'].strip()
                
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