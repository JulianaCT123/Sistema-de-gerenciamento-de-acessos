# ESTE ARQUIVO RODA NA RASP

import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import requests
import json
import time
import os

# Configurações
SERVER_URL = "http://10.1.25.41:5000/verificar_tag"
reader = SimpleMFRC522()
CACHE_URL = "http://10.1.25.41:5000/obter_cache"
ARQUIVO_CACHE = "cache_autorizados.json"
ARQUIVO_LOGS_OFFLINE = "logs_pendentes.json"

# Pinos (Exemplo)
LED_VERDE = 18
LED_VERMELHO = 38
BUZZER = 40

GPIO.setmode(GPIO.BOARD)
GPIO.setup([LED_VERDE, LED_VERMELHO, BUZZER], GPIO.OUT)

def atualizar_cache():
    print("Tentando baixar permissões do servidor...")
    try:
        res = requests.get(CACHE_URL, timeout=5)
        if res.status_code == 200:
            with open(ARQUIVO_CACHE, 'w') as f:
                json.dump(res.json(), f)
            print("Cache atualizado com sucesso!")
    except requests.exceptions.RequestException:
        print("Servidor offline. Usando último cache salvo localmente.")

def registrar_log_offline(tag, status):
    log = {
        "tag": tag,
        "status": status,
        "horario": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    logs = []
    # Lê os logs antigos se o arquivo existir
    if os.path.exists(ARQUIVO_LOGS_OFFLINE):
        with open(ARQUIVO_LOGS_OFFLINE, 'r') as f:
            try:
                logs = json.load(f)
            except:
                logs = []
                
    logs.append(log)
    
    # Salva o novo log no arquivo
    with open(ARQUIVO_LOGS_OFFLINE, 'w') as f:
        json.dump(logs, f)
    print("Log salvo offline para sincronização futura.")

SYNC_URL = "http://10.1.25.41:5000/sincronizar_logs" # Ajuste o IP!

def sincronizar_logs_pendentes():
    if not os.path.exists(ARQUIVO_LOGS_OFFLINE):
        return # Se o arquivo não existe, não há o que sincronizar

    try:
        with open(ARQUIVO_LOGS_OFFLINE, 'r') as f:
            logs = json.load(f)

        if len(logs) > 0:
            print(f"Tentando sincronizar {len(logs)} logs offline...")
            res = requests.post(SYNC_URL, json=logs, timeout=5)

            if res.status_code == 200:
                print("Sincronização concluída com sucesso!")
                # Deleta o arquivo local para não sincronizar duplicado
                os.remove(ARQUIVO_LOGS_OFFLINE)
    except Exception as e:
        # Se der erro (ainda está offline), não faz nada, tenta de novo na próxima
        pass

def feedback_sucesso():
    GPIO.output(LED_VERDE, True)
    # Beep curto do buzzer
    GPIO.output(BUZZER, True)
    time.sleep(0.2)
    GPIO.output(BUZZER, False)
    time.sleep(1.8)
    GPIO.output(LED_VERDE, False)

def feedback_erro():
    GPIO.output(LED_VERMELHO, True)
    # Beep longo ou repetido
    for _ in range(3):
        GPIO.output(BUZZER, True)
        time.sleep(0.1)
        GPIO.output(BUZZER, False)
        time.sleep(0.1)
    time.sleep(1)
    GPIO.output(LED_VERMELHO, False)

atualizar_cache()
try:
    print("Aguardando aproximação da tag...")
    while True:
        id_tag, texto = reader.read()
        tag_str = str(id_tag)
        print(f"Tag lida: {id_tag}")
        
        try:
            sincronizar_logs_pendentes()

            # Envia para o seu Flask
            res = requests.post(SERVER_URL, json={"tag": str(tag_str)}, timeout=5)
            dados = res.json()
            
            if res.status_code == 200:
                print(f"Acesso Liberado: {dados.get('nome')}")
                feedback_sucesso()
            else:
                print("Acesso Negado!")
                feedback_erro()
                
        except Exception as e:
            print("Erro de conexão. Verificando modo offline...")
            # Aqui entra a sua lógica de buscar no arquivo local futuramente [cite: 79]

            # Lê o arquivo de cache
            autorizados = {}
            if os.path.exists(ARQUIVO_CACHE):
                with open(ARQUIVO_CACHE, 'r') as f:
                    autorizados = json.load(f)
            
            # Verifica se a tag está no cache local
            if tag_str in autorizados:
                nome = autorizados[tag_str]
                print(f"OFFLINE: Acesso Liberado para {nome}")
                registrar_log_offline(tag_str, "ENTRADA_OFFLINE")
            else:
                print("OFFLINE: Acesso Negado / Tag Desconhecida")
                registrar_log_offline(tag_str, "TENTATIVA_OFFLINE")

finally:
    # GPIO.cleanup()
    print("Encerrando.")