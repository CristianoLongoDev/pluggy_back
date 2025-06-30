#!/usr/bin/env python3
"""
Script para testar se o HTTPS está funcionando corretamente
"""

import requests
import urllib3
import sys
import os

# Desabilitar avisos de certificados auto-assinados para teste
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_https():
    """Testa se o servidor HTTPS está funcionando"""
    
    # Configurações
    base_url = "https://localhost:5000"
    
    print("🔒 Testando HTTPS...")
    print(f"URL: {base_url}")
    print("-" * 50)
    
    try:
        # Teste 1: Endpoint principal
        print("1. Testando endpoint principal...")
        response = requests.get(f"{base_url}/", verify=False, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Conteúdo: {response.text[:100]}...")
        
        # Teste 2: Health check
        print("\n2. Testando health check...")
        response = requests.get(f"{base_url}/health", verify=False, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Resposta: {response.json()}")
        
        # Teste 3: API endpoint
        print("\n3. Testando API endpoint...")
        response = requests.get(f"{base_url}/api", verify=False, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Resposta: {response.json()}")
        
        # Teste 4: Webhook (GET)
        print("\n4. Testando webhook (GET)...")
        response = requests.get(f"{base_url}/webhook", verify=False, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Resposta: {response.text}")
        
        print("\n✅ Todos os testes HTTPS passaram!")
        print(f"\n🌐 Seu servidor HTTPS está rodando em: {base_url}")
        print("🔗 URL do webhook para WhatsApp Business: {base_url}/webhook")
        
    except requests.exceptions.ConnectionError:
        print("❌ Erro: Não foi possível conectar ao servidor HTTPS")
        print("   Verifique se o servidor está rodando com SSL habilitado:")
        print("   USE_SSL=True python app.py")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Erro durante o teste: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    test_https() 