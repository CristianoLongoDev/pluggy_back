#!/usr/bin/env python3
"""
Script para corrigir account_id no banco
"""

import mysql.connector

# Configurações do banco
DB_CONFIG = {
    'host': '168.75.106.98',
    'port': 6446,
    'database': 'atendimento',
    'user': 'atendimento',
    'password': '8/vLQv98vCmw%Ox1'
}

def main():
    try:
        print("🔧 Corrigindo account_id...")
        
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor(dictionary=True)
        
        # Dados para correção
        email = "cristiano@pluggerbi.com"
        old_account_id = "3d0477ad-537b-4364-94bd-cd46acec2136"
        new_account_id = "3782c0b6-0f1e-4450-bc80-a8aafa1508db"
        
        # 1. Verificar estado atual
        cursor.execute("SELECT id, name, account_id FROM contacts WHERE email = %s", (email,))
        contact = cursor.fetchone()
        
        if not contact:
            print(f"❌ Contato não encontrado com email: {email}")
            return
            
        print(f"📋 Estado atual:")
        print(f"   - ID: {contact['id']}")
        print(f"   - Nome: {contact['name']}")
        print(f"   - Account ID atual: {contact['account_id']}")
        print(f"   - Account ID novo: {new_account_id}")
        print()
        
        # 2. Atualizar account_id
        print("🔄 Atualizando account_id...")
        cursor.execute(
            "UPDATE contacts SET account_id = %s WHERE email = %s",
            (new_account_id, email)
        )
        
        rows_affected = cursor.rowcount
        connection.commit()
        
        print(f"✅ Linhas afetadas: {rows_affected}")
        
        # 3. Verificar a atualização
        cursor.execute("SELECT id, name, account_id FROM contacts WHERE email = %s", (email,))
        updated_contact = cursor.fetchone()
        
        print(f"📋 Estado após atualização:")
        print(f"   - ID: {updated_contact['id']}")
        print(f"   - Nome: {updated_contact['name']}")
        print(f"   - Account ID: {updated_contact['account_id']}")
        print()
        
        # 4. Verificar conversas agora acessíveis
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM conversation c 
            LEFT JOIN contacts ct ON c.contact_id = ct.id 
            WHERE ct.account_id = %s
        """, (new_account_id,))
        
        conversations_count = cursor.fetchone()
        print(f"💬 Conversas agora acessíveis: {conversations_count['count']}")
        
        cursor.close()
        connection.close()
        
        print("\n🎉 Correção concluída! Agora o WebSocket deve encontrar as conversas.")
        
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    main()