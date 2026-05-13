from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
from datetime import datetime
from database import init_db

init_db()  # Inicializa o banco de dados

app = Flask(__name__)
DB_NAME = 'seguranca.db'
CORS(app)

def executar_query(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    # Aumentar o timeout ajuda a evitar o erro de 'locked'
    conn.execute("PRAGMA busy_timeout = 3000") 
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.fetchall()
    except Exception as e:
        print(f"Erro no banco: {e}")
        conn.rollback() # Cancela se der erro
        raise e
    finally:
        conn.close() # GARANTE que a porta do escritório será fechada

@app.route('/')
def index():
    # Isso vai procurar o arquivo index.html dentro da pasta /templates
    return render_template('index.html')

# 1. Endpoint para a Raspberry Pi validar o acesso
@app.route('/verificar_tag', methods=['POST'])
def verificar_tag():
    dados = request.json
    tag_lida = dados.get('tag_rfid')

    if not tag_lida:
        return jsonify({"status": "erro", "mensagem": "Tag não enviada"}), 400

    # 1. Busca o colaborador associado à tag
    # Buscamos o ID e Nome para registrar no log, e o status de permissão/presença
    colaborador = executar_query(
        "SELECT id, nome, permissao_acesso, esta_na_sala FROM colaboradores WHERE tag_rfid = ?", 
        (tag_lida,)
    )

    # 2. Caso a tag não esteja cadastrada no banco
    if not colaborador:
        executar_query(
            "INSERT INTO logs_acesso (tag_rfid, tipo_evento, nome_colaborador) VALUES (?, ?, ?)", 
            (tag_lida, "Tag Não Reconhecida", "DESCONHECIDO")
        )
        return jsonify({
            "status": "negado", 
            "mensagem": "Tag não cadastrada no sistema"
        }), 403

    # Extraímos os dados da tupla retornada pelo banco
    user_id, nome, permissao, na_sala = colaborador[0]

    # 3. Caso o colaborador exista, mas não tenha permissão para esta sala
    if not permissao:
        executar_query(
            "INSERT INTO logs_acesso (colaborador_id, nome_colaborador, tag_rfid, tipo_evento) VALUES (?, ?, ?, ?)", 
            (user_id, nome, tag_lida, "Tentativa Negada")
        )
        return jsonify({
            "status": "negado", 
            "nome": nome, 
            "mensagem": "Acesso restrito (NDA)"
        }), 401

    # 4. Lógica de Entrada/Saída (Inversão de status)
    # Se na_sala for 1 (True), novo_status será 0. Se for 0, será 1.
    novo_status = 0 if na_sala else 1
    tipo_evento = "Saída" if na_sala else "Entrada"

    # Atualiza o status de presença na tabela de colaboradores
    executar_query(
        "UPDATE colaboradores SET esta_na_sala = ? WHERE id = ?", 
        (novo_status, user_id)
    )
    
    # Registra o log oficial com ID e Nome (Chave Estrangeira)
    executar_query(
        """INSERT INTO logs_acesso (colaborador_id, nome_colaborador, tag_rfid, tipo_evento) 
           VALUES (?, ?, ?, ?)""", 
        (user_id, nome, tag_lida, tipo_evento)
    )

    return jsonify({
        "status": "autorizado",
        "nome": nome,
        "evento": tipo_evento,
        "mensagem": f"{tipo_evento} registrada com sucesso"
    }), 200

# 2. Endpoint para o Dashboard listar os logs
@app.route('/logs', methods=['GET'])
def listar_logs():
    logs = executar_query("SELECT id, colaborador_id, nome_colaborador, timestamp, tipo_evento FROM logs_acesso ORDER BY timestamp DESC LIMIT 50")
    
    lista_logs = []
    for l in logs:
        lista_logs.append({
            "id": l[0],
            "colaborador_id": l[1],
            "nome": l[2],
            "data_hora": l[3],
            "evento": l[4]
        })
    return jsonify(lista_logs)

# CADASTRO DE COLABORADORES
@app.route('/colaboradores', methods=['POST'])
def cadastrar_colaborador():
    dados = request.json
    print(f"Dados recebidos: {dados}")
    
    # Pegando os dados do JSON enviado pelo Front-end
    nome = dados.get('nome')
    tag_rfid = dados.get('tag_rfid')
    funcao = dados.get('funcao')
    permissao = dados.get('permissao_acesso', 0) # Padrão é 0 (sem acesso)

    try:
        executar_query(
            """INSERT INTO colaboradores (nome, tag_rfid, funcao, permissao_acesso) 
               VALUES (?, ?, ?, ?)""",
            (nome, tag_rfid, funcao, permissao)
        )
        return jsonify({"mensagem": "Colaborador cadastrado com sucesso!"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"erro": "Tag RFID já cadastrada."}), 400

# EDIÇÃO DE COLABORADORES
@app.route('/colaboradores/<int:id>', methods=['PUT'])
def editar_colaborador(id):
    dados = request.json
    
    # Coletando apenas os dados necessários para a gestão
    nome = dados.get('nome')
    tag_rfid = dados.get('tag_rfid')
    funcao = dados.get('funcao')
    permissao = dados.get('permissao_acesso')

    try:
        # Atualizamos os dados cadastrais e o nível de acesso
        # Note que a tag_rfid pode ser trocada aqui caso o colaborador mude de crachá
        executar_query(
            """UPDATE colaboradores 
               SET nome = ?, tag_rfid = ?, funcao = ?, permissao_acesso = ?
               WHERE id = ?""",
            (nome, tag_rfid, funcao, permissao, id)
        )

        return jsonify({"mensagem": "Colaborador atualizado com sucesso!"}), 200

    except sqlite3.IntegrityError:
        # Erro caso a nova tag_rfid já esteja cadastrada para outra pessoa
        return jsonify({"erro": "Esta Tag RFID já está em uso por outro colaborador."}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# LISTA OS COLABORADORES
@app.route('/colaboradores', methods=['GET'])
def listar_colaboradores():
    # Busca todos os dados da tabela colaboradores
    usuarios = executar_query("SELECT id, nome, tag_rfid, funcao, permissao_acesso, esta_na_sala FROM colaboradores")
    
    # Precisamos transformar a lista de tuplas do SQLite em uma lista de dicionários (JSON)
    lista_usuarios = []
    for u in usuarios:
        lista_usuarios.append({
            "id": u[0],
            "nome": u[1],
            "tag_rfid": u[2],
            "funcao": u[3],
            "permissao_acesso": bool(u[4]), # Converte 0/1 para True/False
            "esta_na_sala": bool(u[5])
        })
    
    return jsonify(lista_usuarios), 200

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

# ---------- ENDPOINTS DE LOGIN DE USUÁRIO PARA O SISTEMA DE GERENCIAMENTO ----------
@app.route('/login', methods=['POST'])
def login():
    dados = request.json
    usuario = dados.get('username')
    senha = dados.get('password')

    # Busca o usuário no banco
    user = executar_query("SELECT id FROM usuarios_sistema WHERE username = ? AND password = ?", (usuario, senha))

    if user:
        return jsonify({"status": "sucesso", "mensagem": "Login realizado"}), 200
    else:
        return jsonify({"status": "erro", "mensagem": "Usuário ou senha incorretos"}), 401

# ---------- ENDPOINS DE MONITORAMENTO EM TEMPO REAL ----------
@app.route('/monitoramento_dados', methods=['GET'])
def monitoramento_dados():
    # 1. Colaboradores atualmente na sala
    na_sala = executar_query("SELECT nome, funcao FROM colaboradores WHERE esta_na_sala = 1")
    
    # 2. Últimos eventos (Geral)
    ultimos_eventos = executar_query("""
        SELECT nome_colaborador, tag_rfid, timestamp, tipo_evento 
        FROM logs_acesso 
        ORDER BY timestamp DESC LIMIT 10
    """)
    
    # 3. Alertas (Não autorizados e Tags desconhecidas)
    alertas = executar_query("""
        SELECT tag_rfid, timestamp, tipo_evento 
        FROM logs_acesso 
        WHERE tipo_evento IN ('Tentativa Negada', 'Tag Não Reconhecida')
        ORDER BY timestamp DESC LIMIT 5
    """)

    return jsonify({
        "na_sala": na_sala,
        "eventos": ultimos_eventos,
        "alertas": alertas
    })

if __name__ == '__main__':
    # '0.0.0.0' permite que a Raspberry Pi encontre o seu PC na rede local
    app.run(host='0.0.0.0', port=5000, debug=True)