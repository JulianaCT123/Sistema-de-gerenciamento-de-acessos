from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import sqlite3
from datetime import datetime
from database import init_db
import os

# Inicializa o banco de dados se necessário
init_db()

app = Flask(__name__)

# CHAVE SECRETA: Necessária para usar sessões (Login) 
app.secret_key = 'chave_secreta_para_projeto_atitus'

DB_NAME = 'seguranca.db'

def executar_query(query, params=()):
    """Função auxiliar para conectar e executar comandos no banco"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    resultado = cursor.fetchall()
    conn.close()
    return resultado

@app.route('/')
def index():
    return "API Rodando!"

# 1. Endpoint para a Raspberry Pi validar o acesso
@app.route('/verificar_tag', methods=['POST'])
def verificar_tag():
    """Endpoint principal para a Raspberry Pi [cite: 12, 40]"""
    dados = request.json
    tag_lida = dados.get('tag_rfid')
    
    colaborador = executar_query(
        "SELECT id, nome, permissao_acesso, esta_na_sala FROM colaboradores WHERE tag_rfid = ?", 
        (tag_lida,)
    )

    if not colaborador:
        # Tentativa de invasão (Tag desconhecida) [cite: 20, 35]
        executar_query(
            "INSERT INTO logs_acesso (tag_rfid, tipo_evento, nome_colaborador) VALUES (?, ?, ?)", 
            (tag_lida, "Invasão - Tag Desconhecida", "DESCONHECIDO")
        )
        return jsonify({"status": "negado", "mensagem": "Alerta: Tag não reconhecida"}), 403

    user_id, nome, permissao, na_sala = colaborador[0]

    if not permissao:
        # Acesso negado para colaborador sem permissão [cite: 19, 26]
        executar_query(
            "INSERT INTO logs_acesso (colaborador_id, nome_colaborador, tag_rfid, tipo_evento) VALUES (?, ?, ?, ?)", 
            (user_id, nome, tag_lida, "Acesso Negado (NDA)")
        )
        return jsonify({"status": "negado", "nome": nome, "mensagem": "Sem permissão de acesso"}), 401

    # Lógica de Entrada/Saída [cite: 17, 22, 24]
    novo_status = 0 if na_sala else 1
    tipo_evento = "Saída" if na_sala else ("Entrada (Primeira)" if na_sala == 0 else "Entrada (Retorno)")

    executar_query("UPDATE colaboradores SET esta_na_sala = ? WHERE id = ?", (novo_status, user_id))
    executar_query(
        "INSERT INTO logs_acesso (colaborador_id, nome_colaborador, tag_rfid, tipo_evento) VALUES (?, ?, ?, ?)", 
        (user_id, nome, tag_lida, tipo_evento)
    )

    return jsonify({"status": "autorizado", "nome": nome, "evento": tipo_evento}), 200

@app.route('/logs', methods=['GET'])
def listar_logs():
    """Retorna logs para o Monitoramento e Dashboard [cite: 52, 61, 83]"""
    logs = executar_query("SELECT id, nome_colaborador, timestamp, tipo_evento, tag_rfid FROM logs_acesso ORDER BY timestamp DESC LIMIT 50")
    return jsonify([{
        "id": l[0], "nome": l[1], "data": l[2], "evento": l[3], "tag": l[4]
    } for l in logs])

@app.route('/colaboradores/<int:id>', methods=['DELETE'])
def deletar_colaborador(id):
    try:
        # 1. Verifica se o colaborador existe antes de tentar deletar
        colaborador = executar_query("SELECT nome FROM colaboradores WHERE id = ?", (id,))
        
        if not colaborador:
            return jsonify({"erro": "Colaborador não encontrado."}), 404

        # 2. Executa a exclusão
        executar_query("DELETE FROM colaboradores WHERE id = ?", (id,))
        
        return jsonify({"mensagem": f"Colaborador {colaborador[0][0]} removido com sucesso!"}), 200

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    # '0.0.0.0' permite acesso externo (Raspberry Pi na mesma rede) [cite: 39]
    app.run(host='0.0.0.0', port=5000, debug=True)