#!/usr/bin/env python3

import sys
import os
import logging

# Adicionar diretório atual ao path para importar módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_movidesk_integration():
    """Testa a integração com Movidesk com dados de exemplo"""
    
    print("🔍 TESTE DE INTEGRAÇÃO COM MOVIDESK")
    print("=" * 50)
    
    try:
        # 1. Verificar configurações
        print("\n1. VERIFICANDO CONFIGURAÇÕES:")
        from config import MOVIDESK_TOKEN, MOVIDESK_PERSONS_ENDPOINT
        
        print(f"   Token configurado: {'✅ SIM' if MOVIDESK_TOKEN else '❌ NÃO'}")
        print(f"   URL endpoint: {MOVIDESK_PERSONS_ENDPOINT}")
        
        if not MOVIDESK_TOKEN:
            print("❌ ERRO: Token da Movidesk não configurado!")
            print("   Verifique se a variável MOVIDESK_TOKEN está definida.")
            return False
        
        # 2. Testar conexão com banco
        print("\n2. VERIFICANDO CONEXÃO COM BANCO:")
        from database import db_manager
        
        if db_manager.enabled:
            connection_status = db_manager.get_connection_status()
            print(f"   Status: {connection_status}")
            
            if connection_status == "connected":
                print("   ✅ Conexão com banco OK")
                
                # Verificar se tabela company_relationship existe
                try:
                    result = db_manager.execute_query("SHOW TABLES LIKE 'company_relationship'")
                    if result:
                        print("   ✅ Tabela company_relationship existe")
                        
                        # Verificar dados na tabela
                        companies = db_manager.execute_query("SELECT * FROM company_relationship LIMIT 5")
                        if companies:
                            print(f"   📊 Encontradas {len(companies)} empresas cadastradas:")
                            for comp in companies:
                                print(f"      - {comp['domain']} → company_id: {comp['company_id']}")
                        else:
                            print("   ⚠️ Tabela company_relationship está vazia")
                            print("   📝 Execute o SQL de exemplo para popular a tabela")
                    else:
                        print("   ❌ Tabela company_relationship não existe")
                        return False
                        
                except Exception as e:
                    print(f"   ❌ Erro ao verificar tabela: {e}")
                    return False
            else:
                print(f"   ❌ Problema na conexão: {connection_status}")
                return False
        else:
            print("   ❌ Banco de dados desabilitado")
            return False
        
        # 3. Testar importação do serviço
        print("\n3. TESTANDO IMPORTAÇÃO DO MOVIDESK SERVICE:")
        try:
            from movidesk_service import movidesk_service
            print("   ✅ Movidesk service importado com sucesso")
            print(f"   Token carregado: {'✅ SIM' if movidesk_service.token else '❌ NÃO'}")
        except Exception as e:
            print(f"   ❌ Erro ao importar movidesk_service: {e}")
            return False
        
        # 4. Testar busca na Movidesk com email de exemplo
        print("\n4. TESTANDO BUSCA NA MOVIDESK:")
        test_email = input("   Digite um email para testar (ou pressione Enter para usar cristiano@pluggerbi.com): ").strip()
        if not test_email:
            test_email = "cristiano@pluggerbi.com"
        
        print(f"   Testando busca por: {test_email}")
        
        try:
            # Testar busca
            person = movidesk_service.search_person_by_email(test_email)
            if person:
                print(f"   ✅ Pessoa encontrada: ID {person.get('id')}")
                print(f"      Nome: {person.get('businessName')}")
                return True
            else:
                print(f"   ℹ️ Pessoa não encontrada para {test_email}")
                
                # Testar criação
                print(f"   🔄 Testando criação de nova pessoa...")
                person_id = movidesk_service.create_person("Teste Bot", test_email)
                if person_id:
                    print(f"   ✅ Pessoa criada com sucesso: ID {person_id}")
                    return True
                else:
                    print(f"   ❌ Falha ao criar pessoa")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Erro ao testar Movidesk: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            return False
        
    except Exception as e:
        print(f"❌ ERRO GERAL: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def check_recent_contacts():
    """Verifica contatos recentes para ver se person_id foi gravado"""
    
    print("\n🔍 VERIFICANDO CONTATOS RECENTES")
    print("=" * 50)
    
    try:
        from database import db_manager
        
        # Buscar contatos com email mas sem person_id
        query = """
        SELECT id, name, email, person_id, created_at, updated_at 
        FROM contacts 
        WHERE email IS NOT NULL 
        ORDER BY updated_at DESC 
        LIMIT 10
        """
        
        contacts = db_manager.execute_query(query)
        if contacts:
            print(f"\n📋 Últimos {len(contacts)} contatos com email:")
            print("-" * 80)
            for contact in contacts:
                status = "✅ COM person_id" if contact['person_id'] else "❌ SEM person_id"
                print(f"ID: {contact['id']}")
                print(f"Nome: {contact['name'] or 'N/A'}")
                print(f"Email: {contact['email']}")
                print(f"Person ID: {contact['person_id'] or 'N/A'} - {status}")
                print(f"Atualizado: {contact['updated_at']}")
                print("-" * 80)
        else:
            print("   ℹ️ Nenhum contato com email encontrado")
            
    except Exception as e:
        print(f"❌ Erro ao verificar contatos: {e}")

if __name__ == "__main__":
    print("🚀 INICIANDO DEBUG DA INTEGRAÇÃO MOVIDESK")
    
    # Teste principal
    success = test_movidesk_integration()
    
    # Verificar contatos existentes
    check_recent_contacts()
    
    print(f"\n🏁 RESULTADO FINAL: {'✅ SUCESSO' if success else '❌ FALHA'}")
    
    if not success:
        print("\n💡 DICAS PARA RESOLVER:")
        print("1. Verifique se o token MOVIDESK_TOKEN está configurado no secret do Kubernetes")
        print("2. Execute o script populate_company_relationship.sql no banco")
        print("3. Verifique os logs do webhook-worker durante o teste")
        print("4. Teste com kubectl logs -f deployment/webhook-worker -n whatsapp-webhook") 