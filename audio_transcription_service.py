#!/usr/bin/env python3
"""
Serviço de transcrição de áudio usando OpenAI Whisper
Baixa arquivos de áudio do WhatsApp, converte para MP3 e transcreve
"""

import os
import logging
import requests
import tempfile
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioTranscriptionService:
    def __init__(self):
        # Usar a mesma API key do ChatGPT
        self.api_key = "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"
        self.api_url = "https://api.openai.com/v1/audio/transcriptions"
        self.model = "whisper-1"
        
    def download_audio_file(self, audio_url, access_token=None, timeout=30):
        """
        Baixa arquivo de áudio da URL fornecida (com autenticação WhatsApp)
        """
        try:
            logger.info(f"🎵 Baixando arquivo de áudio: {audio_url[:50]}...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # Adicionar token de autorização se fornecido (necessário para URLs do WhatsApp)
            if access_token:
                headers['Authorization'] = f'Bearer {access_token}'
                logger.info("🔐 Usando autenticação WhatsApp para download")
            
            logger.info(f"🌐 Fazendo requisição para: {audio_url}")
            response = requests.get(audio_url, headers=headers, timeout=timeout, stream=True)
            logger.info(f"📡 Status da resposta: {response.status_code}")
            logger.info(f"📋 Content-Type: {response.headers.get('content-type', 'unknown')}")
            response.raise_for_status()
            
            # Criar arquivo temporário
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp')
            logger.info(f"📁 Arquivo temporário criado: {temp_file.name}")
            
            # Baixar em chunks
            total_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
                    total_size += len(chunk)
            
            temp_file.close()
            
            logger.info(f"✅ Áudio baixado com sucesso: {temp_file.name} ({total_size} bytes)")
            
            # Verificar se o arquivo foi criado corretamente
            if os.path.exists(temp_file.name) and os.path.getsize(temp_file.name) > 0:
                logger.info(f"✅ Verificação do arquivo: OK ({os.path.getsize(temp_file.name)} bytes)")
                return temp_file.name
            else:
                logger.error(f"❌ Arquivo baixado está vazio ou não foi criado")
                return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao baixar áudio: {e}")
            return None
    
    def convert_to_mp3(self, input_file, output_file=None):
        """
        Converte arquivo de áudio para MP3 usando ffmpeg
        """
        try:
            if not output_file:
                output_file = input_file.replace('.tmp', '.mp3')
            
            logger.info(f"🔄 Convertendo áudio para MP3...")
            
            # Usar caminho completo do ffmpeg
            ffmpeg_path = '/usr/bin/ffmpeg'
            logger.info(f"🔧 Tentando conversão com ffmpeg: {ffmpeg_path}")
            
            # Comando ffmpeg para conversão
            cmd = [
                ffmpeg_path, '-i', input_file,
                '-acodec', 'libmp3lame',  # Usar libmp3lame para melhor compatibilidade
                '-ar', '16000',  # 16kHz sample rate (recomendado para Whisper)
                '-ac', '1',      # Mono
                '-f', 'mp3',     # Forçar formato MP3
                '-y',            # Sobrescrever arquivo se existir
                output_file
            ]
            
            logger.info(f"🔧 Executando comando: {' '.join(cmd)}")
            logger.info(f"📁 Arquivo entrada: {input_file} (existe: {os.path.exists(input_file)}, tamanho: {os.path.getsize(input_file) if os.path.exists(input_file) else 'N/A'} bytes)")
            
            # Executar conversão com timeout
            try:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=60  # 1 minuto timeout
                )
                
                logger.info(f"🔍 FFmpeg return code: {result.returncode}")
                if result.stdout:
                    logger.info(f"🔍 FFmpeg stdout: {result.stdout}")
                if result.stderr:
                    logger.info(f"🔍 FFmpeg stderr: {result.stderr}")
                
                if result.returncode == 0:
                    logger.info(f"✅ Conversão concluída: {output_file}")
                    logger.info(f"📁 Arquivo saída: {output_file} (existe: {os.path.exists(output_file)}, tamanho: {os.path.getsize(output_file) if os.path.exists(output_file) else 'N/A'} bytes)")
                    
                    # Remover arquivo original
                    try:
                        os.unlink(input_file)
                        logger.info(f"🗑️ Arquivo original removido: {input_file}")
                    except Exception as cleanup_error:
                        logger.warning(f"⚠️ Erro ao remover arquivo original: {cleanup_error}")
                        
                    return output_file
                else:
                    logger.error(f"❌ Erro na conversão ffmpeg (code {result.returncode}): {result.stderr}")
                    # Retornar arquivo original se conversão falhar
                    return input_file
                    
            except subprocess.TimeoutExpired:
                logger.error("❌ Timeout na conversão ffmpeg (60s). Usando arquivo original...")
                return input_file
            except Exception as e:
                logger.error(f"❌ Erro inesperado na conversão: {e}. Usando arquivo original...")
                return input_file
                
        except subprocess.TimeoutExpired:
            logger.error("⏰ Timeout na conversão de áudio")
            return input_file
        except Exception as e:
            logger.error(f"❌ Erro na conversão: {e}")
            return input_file
    
    def transcribe_audio(self, audio_file_path):
        """
        Transcreve arquivo de áudio usando OpenAI Whisper
        """
        try:
            logger.info(f"🎤 Transcrevendo áudio: {audio_file_path}")
            
            # Verificar se o arquivo existe
            if not os.path.exists(audio_file_path):
                logger.error(f"❌ Arquivo de áudio não encontrado: {audio_file_path}")
                return None
            
            # Verificar tamanho do arquivo (limite OpenAI: 25MB)
            file_size = os.path.getsize(audio_file_path)
            if file_size > 25 * 1024 * 1024:  # 25MB
                logger.error(f"❌ Arquivo muito grande ({file_size/1024/1024:.1f}MB). Limite: 25MB")
                return None
            
            logger.info(f"📊 Tamanho do arquivo: {file_size/1024:.1f}KB")
            
            # Verificar se o arquivo tem extensão MP3 (esperado após conversão)
            if not audio_file_path.endswith('.mp3'):
                logger.warning(f"⚠️ Arquivo não é MP3: {audio_file_path} - pode haver problemas com a API")
            
            # Configurar headers para requisição
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }
            
            # Preparar dados para multipart/form-data
            files = {
                'file': open(audio_file_path, 'rb'),
                'model': (None, self.model),
                'language': (None, 'pt')  # Forçar português
            }
            
            logger.info(f"🚀 Enviando arquivo para OpenAI Whisper API...")
            logger.info(f"🔧 URL: {self.api_url}")
            logger.info(f"🔧 Modelo: {self.model}")
            logger.info(f"🔧 Arquivo: {audio_file_path} ({file_size} bytes)")
            
            # Fazer requisição para OpenAI Whisper
            response = requests.post(
                self.api_url,
                headers=headers,
                files=files,
                timeout=60
            )
            
            # Fechar arquivo
            files['file'].close()
            
            logger.info(f"📡 Resposta da API: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Resposta recebida: {result}")
                transcription = result.get('text', '').strip()
                
                if transcription:
                    logger.info(f"✅ Transcrição concluída: {transcription[:100]}...")
                    return transcription
                else:
                    logger.warning("⚠️ Transcrição vazia")
                    return None
            else:
                logger.error(f"❌ Erro na API Whisper: {response.status_code}")
                logger.error(f"❌ Resposta: {response.text}")
                return None
                    
        except Exception as e:
            logger.error(f"❌ Erro na transcrição: {e}")
            return None
        finally:
            # Limpar arquivo temporário
            try:
                if os.path.exists(audio_file_path):
                    os.unlink(audio_file_path)
                    logger.debug(f"🧹 Arquivo temporário removido: {audio_file_path}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Erro ao limpar arquivo: {cleanup_error}")
    
    def process_audio_message(self, audio_url, access_token=None):
        """
        Processa mensagem de áudio completa: download -> conversão -> transcrição
        """
        try:
            logger.info(f"🎙️ Iniciando processamento de áudio: {audio_url[:50]}...")
            
            # 1. Baixar arquivo de áudio (com autenticação se fornecida)
            temp_audio_file = self.download_audio_file(audio_url, access_token)
            if not temp_audio_file:
                return None
            
            # 2. Converter para MP3 (se necessário)
            mp3_file = self.convert_to_mp3(temp_audio_file)
            if not mp3_file:
                return None
            
            # 3. Transcrever áudio
            transcription = self.transcribe_audio(mp3_file)
            
            if transcription:
                logger.info(f"🎉 Processamento de áudio concluído com sucesso")
                return {
                    "success": True,
                    "transcription": transcription,
                    "message": "Áudio transcrito com sucesso"
                }
            else:
                logger.error("❌ Falha na transcrição")
                return {
                    "success": False,
                    "error": "Falha na transcrição do áudio",
                    "transcription": None
                }
                
        except Exception as e:
            logger.error(f"❌ Erro no processamento de áudio: {e}")
            return {
                "success": False,
                "error": str(e),
                "transcription": None
            }

# Instância global do serviço
audio_transcription_service = AudioTranscriptionService() 