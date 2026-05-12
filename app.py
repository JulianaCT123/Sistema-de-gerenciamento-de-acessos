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
    """Função auxiliar para conectar e executar comandos no banco [cite: 38]"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    resultado = cursor.fetchall()
    conn.close()
    return resultado


@app.route('/api/status_sala', methods=['GET'])
def status_sala():
    # Busca apenas quem está com o status 'esta_na_sala = 1'
    presentes = executar_query("SELECT nome, funcao FROM colaboradores WHERE esta_na_sala = 1")
    return jsonify([{"nome": p[0], "funcao": p[1]} for p in presentes])

# --- ROTAS DE AUTENTICAÇÃO [cite: 44, 45] ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        dados = request.json
        usuario = dados.get('usuario')
        senha = dados.get('senha')
        
        # Autenticação simples conforme o requisito 
        if usuario == 'admin' and senha == '1234':
            session['logado'] = True
            return jsonify({"status": "sucesso"}), 200
        return jsonify({"status": "erro", "mensagem": "Credenciais inválidas"}), 401
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logado', None)
    return redirect(url_for('login'))

# --- ROTAS DE NAVEGAÇÃO ---

@app.route('/')
def index():
    if not session.get('logado'):
        return redirect(url_for('login'))
    return redirect(url_for('admin_page'))

@app.route('/admin')
def admin_page():
    if not session.get('logado'):
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/monitoramento')
def monitoramento_page():
    # Página para a empresa de segurança (pode ser pública ou restrita) [cite: 61]
    return render_template('monitoramento.html')

@app.route('/logs_view')
def logs_page():
    if not session.get('logado'):
        return redirect(url_for('login'))
    return render_template('logs.html')

# --- API DE COLABORADORES (CRUD COMPLETO) [cite: 46, 47, 48, 49] ---

@app.route('/colaboradores', methods=['GET'])
def listar_colaboradores():
    usuarios = executar_query("SELECT id, nome, tag_rfid, funcao, permissao_acesso, esta_na_sala FROM colaboradores")
    lista = []
    for u in usuarios:
        lista.append({
            "id": u[0], "nome": u[1], "tag_rfid": u[2], 
            "funcao": u[3], "permissao": bool(u[4]), "na_sala": bool(u[5])
        })
    return jsonify(lista)

@app.route('/colaboradores', methods=['POST'])
def cadastrar_colaborador():
    dados = request.json
    try:
        executar_query(
            "INSERT INTO colaboradores (nome, tag_rfid, funcao, permissao_acesso) VALUES (?, ?, ?, ?)",
            (dados['nome'], dados['tag_rfid'], dados['funcao'], dados.get('permissao', 0))
        )
        return jsonify({"mensagem": "Cadastrado com sucesso!"}), 201
    except Exception as e:
        return jsonify({"erro": str(e)}), 400

@app.route('/colaboradores/<int:id>', methods=['PUT'])
def editar_colaborador(id):
    dados = request.json
    executar_query(
        "UPDATE colaboradores SET nome=?, tag_rfid=?, funcao=?, permissao_acesso=? WHERE id=?",
        (dados['nome'], dados['tag_rfid'], dados['funcao'], dados['permissao'], id)
    )
    return jsonify({"mensagem": "Atualizado!"})

@app.route('/colaboradores/<int:id>', methods=['DELETE'])
def excluir_colaborador(id):
    """Implementação da exclusão de colaborador """
    try:
        executar_query("DELETE FROM colaboradores WHERE id = ?", (id,))
        return jsonify({"mensagem": "Removido com sucesso!"}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# --- API DE LOGS E EVENTOS [cite: 52, 63, 64, 65] ---

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

if __name__ == '__main__':
    # '0.0.0.0' permite acesso externo (Raspberry Pi na mesma rede) [cite: 39]
    app.run(host='0.0.0.0', port=5000, debug=True)