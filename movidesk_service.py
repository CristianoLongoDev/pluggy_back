import requests
import json
import logging
import re
from config import MOVIDESK_TOKEN, MOVIDESK_PERSONS_ENDPOINT
from database import db_manager

logger = logging.getLogger(__name__)

class MovideskService:
    def __init__(self):
        self.token = MOVIDESK_TOKEN
        self.persons_endpoint = MOVIDESK_PERSONS_ENDPOINT
        
    def _get_domain_from_email(self, email):
        """Extrai o domínio do email"""
        if '@' not in email:
            return None
        return email.split('@')[1].lower()
    
    def _get_company_id_by_domain(self, domain):
        """Busca company_id na tabela company_relationship pelo domínio"""
        if not domain:
            return None
            
        try:
            query = "SELECT company_id FROM company_relationship WHERE domain = %s"
            result = db_manager.execute_query(query, (domain,))
            
            if result and len(result) > 0:
                return result[0]['company_id']
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar company_id para domínio {domain}: {e}")
            return None
    
    def search_person_by_email(self, email):
        """Busca uma pessoa na Movidesk pelo email"""
        if not self.token:
            logger.error("Token da Movidesk não configurado")
            return None
            
        try:
            # Montar a URL com filtro
            filter_param = f"Emails/any(e: e/email eq '{email}')"
            params = {
                'token': self.token,
                '$filter': filter_param
            }
            
            logger.info(f"Buscando pessoa na Movidesk para email: {email}")
            response = requests.get(self.persons_endpoint, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    person = data[0]  # Pegar o primeiro resultado
                    logger.info(f"Pessoa encontrada na Movidesk: ID {person.get('id')}")
                    return person
                else:
                    logger.info(f"Pessoa não encontrada na Movidesk para email: {email}")
                    return None
            else:
                logger.error(f"Erro na busca da Movidesk: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao buscar pessoa na Movidesk: {e}")
            return None
    
    def create_person(self, contact_name, contact_email):
        """Cria uma nova pessoa na Movidesk"""
        if not self.token:
            logger.error("Token da Movidesk não configurado")
            return None
            
        try:
            # Extrair domínio e buscar company_id
            domain = self._get_domain_from_email(contact_email)
            company_id = self._get_company_id_by_domain(domain) if domain else None
            
            # Se não encontrou company_id específico, usar o padrão
            if not company_id:
                company_id = "1044491776"  # Company ID padrão
                logger.info(f"Company_id não encontrado para domínio {domain}, usando padrão: {company_id}")
            
            # Montar JSON base
            person_data = {
                "isActive": True,
                "personType": 1,
                "profileType": 2,
                "accessProfile": "Clientes",
                "businessName": contact_name,
                "userName": contact_email,
                "emails": [
                    {
                        "emailType": "Profissional",
                        "email": contact_email,
                        "isDefault": True
                    }
                ]
            }
            
            # Sempre adicionar relationships (agora sempre temos company_id)
            person_data["relationships"] = [
                {
                    "id": company_id,
                    "forceChildrenToHaveSomeAgreement": False,
                    "allowAllServices": True,
                    "isGetMethod": True
                }
            ]
            logger.info(f"Adicionando relationship com company_id: {company_id}")
            
            # Fazer POST para criar pessoa
            params = {'token': self.token}
            headers = {'Content-Type': 'application/json'}
            
            logger.info(f"Criando pessoa na Movidesk: {contact_name} ({contact_email})")
            response = requests.post(
                self.persons_endpoint, 
                params=params, 
                headers=headers,
                data=json.dumps(person_data),
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                person_id = data.get('id')
                logger.info(f"Pessoa criada na Movidesk com sucesso: ID {person_id}")
                return person_id
            else:
                logger.error(f"Erro ao criar pessoa na Movidesk: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao criar pessoa na Movidesk: {e}")
            return None
    
    def get_or_create_person(self, contact_name, contact_email):
        """Busca pessoa na Movidesk, se não encontrar, cria uma nova"""
        try:
            # Primeiro, buscar se já existe
            person = self.search_person_by_email(contact_email)
            
            if person:
                # Pessoa encontrada, retornar o ID
                person_id = person.get('id')
                logger.info(f"Pessoa já existente na Movidesk: {person_id}")
                return person_id
            else:
                # Pessoa não encontrada, criar nova
                person_id = self.create_person(contact_name, contact_email)
                if person_id:
                    logger.info(f"Nova pessoa criada na Movidesk: {person_id}")
                    return person_id
                else:
                    logger.error(f"Falha ao criar pessoa na Movidesk para {contact_email}")
                    return None
                    
        except Exception as e:
            logger.error(f"Erro no processo get_or_create_person: {e}")
            return None

# Instância global do serviço
movidesk_service = MovideskService() 