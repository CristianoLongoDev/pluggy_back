import requests
import json
import logging
from datetime import datetime
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
            if system_prompt:
                return system_prompt
            else:
                # Prompt padrão se não estiver configurado
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
        """Monta o contexto da conversa com as últimas mensagens"""
        try:
            # Buscar últimas 10 mensagens do contato hoje
            messages = db_manager.get_conversation_context(contact_id, limit=10)
            
            conversation = []
            
            # Adicionar prompt do sistema
            system_prompt = self.get_system_prompt()
            conversation.append(system_prompt)
            
            # Adicionar mensagens do contexto
            for msg in messages:
                role = "user" if msg['event_type'] == 'message_received' else "assistant"
                conversation.append({
                    "role": role,
                    "content": msg['message']
                })
            
            logger.info(f"Contexto montado para {contact_id}: {len(conversation)} mensagens")
            return conversation
            
        except Exception as e:
            logger.error(f"Erro ao montar contexto para {contact_id}: {e}")
            # Retorna apenas o system prompt em caso de erro
            return [self.get_system_prompt()]
    
    def generate_response(self, contact_id, user_message):
        """Gera resposta usando ChatGPT"""
        try:
            # Montar contexto da conversa
            conversation = self.build_conversation_context(contact_id)
            
            # Adicionar mensagem atual do usuário
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
    
    def process_message(self, contact_id, message_text):
        """Processa uma mensagem e retorna resposta do ChatGPT"""
        logger.info(f"Processando mensagem de {contact_id}: {message_text[:50]}...")
        
        # Gerar resposta
        result = self.generate_response(contact_id, message_text)
        
        if result["success"]:
            # Salvar resposta no banco como message_sended
            try:
                db_manager.save_webhook_event(
                    event_type="message_sended",
                    event_data={
                        "type": "text", 
                        "from": "chatgpt",
                        "to": contact_id,
                        "text": result["response"],
                        "tokens_used": result["tokens_used"],
                        "timestamp": datetime.now().isoformat(),
                        "chatgpt_raw": result["raw_data"]
                    }
                )
                
                logger.info(f"Resposta ChatGPT salva no banco para {contact_id}")
                return result["response"]
                
            except Exception as e:
                logger.error(f"Erro ao salvar resposta ChatGPT no banco: {e}")
                return result["response"]  # Retorna mesmo que não salve
        
        else:
            logger.error(f"Falha ao gerar resposta ChatGPT: {result.get('error', 'Erro desconhecido')}")
            return "Desculpe, não consegui processar sua mensagem no momento. Tente novamente."

# Instância global do serviço ChatGPT
chatgpt_service = ChatGPTService() 