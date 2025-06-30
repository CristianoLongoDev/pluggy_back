#!/usr/bin/env python3
"""
Script para testar a conexão com o banco MySQL
"""

import sys
import os
from database import db_manager

def test_database_connection():
    """Testa a conexão com o banco MySQL"""
    
    print("🗄️  Testando conexão com o banco MySQL...")
    print("=" * 50)
    
    # Teste 1: Conectar ao banco
    print("1. Testando conexão...")
    if db_manager.connect():
        print("   ✅ Conexão estabelecida com sucesso!")
    else:
        print("   ❌ Falha na conexão com o banco")
        return False
    
    # Teste 2: Criar tabela
    print("\n2. Testando criação da tabela...")
    if db_manager.create_table_if_not_exists():
        print("   ✅ Tabela logs verificada/criada com sucesso!")
    else:
        print("   ❌ Falha ao criar tabela")
        return False
    
    # Teste 3: Inserir dados de teste
    print("\n3. Testando inserção de dados...")
    test_data = {
        'test': True,
        'message': 'Teste de conexão com o banco',
        'timestamp': '2024-01-01T00:00:00Z'
    }
    
    if db_manager.save_webhook_event('test_connection', test_data):
        print("   ✅ Dados inseridos com sucesso!")
    else:
        print("   ❌ Falha ao inserir dados")
        return False
    
    # Teste 4: Verificar status
    print("\n4. Verificando status da conexão...")
    status = db_manager.get_connection_status()
    print(f"   Status: {status}")
    
    # Fechar conexão
    db_manager.disconnect()
    print("\n✅ Todos os testes passaram!")
    print("🗄️  Banco MySQL configurado e funcionando corretamente")
    
    return True

if __name__ == "__main__":
    success = test_database_connection()
    sys.exit(0 if success else 1) 