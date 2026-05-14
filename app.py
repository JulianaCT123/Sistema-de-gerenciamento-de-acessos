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

# @app.route('/')
# def index():
#     # Isso vai procurar o arquivo index.html dentro da pasta /templates
#     return render_template('index.html')

@app.route('/')
def pagina_login():
    return render_template('login.html')

@app.route('/gerenciamento')
def pagina_admin():
    return render_template('index.html')

@app.route('/monitor')
def pagina_monitoramento():
    return render_template('monitor.html')


@app.route('/obter_cache', methods=['GET'])
def obter_cache():
    # Busca apenas quem tem permissão de acesso à sala
    colaboradores = executar_query("SELECT tag_rfid, nome FROM colaboradores WHERE permissao_acesso = 1")
    
    # Transforma a lista de tuplas em um dicionário para o JSON
    cache = {}
    if colaboradores:
        for tag, nome in colaboradores:
            cache[tag] = nome
            
    return jsonify(cache), 200

@app.route('/verificar_tag', methods=['POST'])
def verificar_tag():
    data = request.get_json()
    tag_lida = data.get('tag')
    
    # Busca o colaborador no banco
    colaborador = executar_query("SELECT id, nome, permissao_acesso, esta_na_sala FROM colaboradores WHERE tag_rfid = ?", (tag_lida,))
    
    if colaborador:
        colab_id, nome, tem_permissao, na_sala = colaborador[0]
        
        if tem_permissao:
            # Lógica de Entrada e Saída
            novo_status = 0 if na_sala else 1
            tipo_evento = "SAIDA" if na_sala else "ENTRADA"
            
            # Atualiza e salva o log
            executar_query("UPDATE colaboradores SET esta_na_sala = ? WHERE id = ?", (novo_status, colab_id))
            executar_query("INSERT INTO logs_acesso (colaborador_id, nome_colaborador, tag_rfid, tipo_evento) VALUES (?, ?, ?, ?)", (colab_id, nome, tag_lida, tipo_evento))
            
            return jsonify({"status": "sucesso", "nome": nome, "evento": tipo_evento}), 200
        else:
            # Sem permissão
            executar_query("INSERT INTO logs_acesso (tag_rfid, tipo_evento) VALUES (?, ?)", (tag_lida, "TENTATIVA_NEGADA"))
            return jsonify({"status": "negado", "mensagem": "Sem permissão"}), 403
    else:
        # Tag desconhecida (Invasão)
        executar_query("INSERT INTO logs_acesso (tag_rfid, tipo_evento) VALUES (?, ?)", (tag_lida, "TAG_DESCONHECIDA"))
        return jsonify({"status": "invasao", "mensagem": "Tag não reconhecida"}), 404

@app.route('/sincronizar_logs', methods=['POST'])
def sincronizar_logs():
    try:
        logs_offline = request.get_json()
        print(f"--- INICIANDO SINCRONIZAÇÃO DE {len(logs_offline)} LOGS ---")
        
        if not logs_offline:
            return jsonify({"status": "vazio"}), 200

        for log in logs_offline:
            tag = log.get('tag')
            tipo_evento = log.get('status')
            timestamp = log.get('horario')
            
            print(f"Sincronizando: Tag {tag} | Evento {tipo_evento} | Hora {timestamp}")

            # Busca o estado atual
            colaborador = executar_query("SELECT id, nome, esta_na_sala FROM colaboradores WHERE tag_rfid = ?", (tag,))

            if colaborador:
                colab_id, nome, na_sala = colaborador[0]
                
                if tipo_evento == "ENTRADA_OFFLINE":
                    novo_status = 0 if na_sala else 1
                    evento_real = "SAIDA_OFFLINE" if na_sala else "ENTRADA_OFFLINE"
                    
                    executar_comando("UPDATE colaboradores SET esta_na_sala = ? WHERE id = ?", (novo_status, colab_id))
                    executar_comando(
                        "INSERT INTO logs_acesso (colaborador_id, nome_colaborador, tag_rfid, tipo_evento, timestamp) VALUES (?, ?, ?, ?, ?)", 
                        (colab_id, nome, tag, evento_real, timestamp)
                    )
                else:
                    executar_comando(
                        "INSERT INTO logs_acesso (colaborador_id, nome_colaborador, tag_rfid, tipo_evento, timestamp) VALUES (?, ?, ?, ?, ?)", 
                        (colab_id, nome, tag, tipo_evento, timestamp)
                    )
            else:
                executar_comando(
                    "INSERT INTO logs_acesso (tag_rfid, tipo_evento, timestamp) VALUES (?, ?, ?)", 
                    (tag, tipo_evento, timestamp)
                )

        print("--- SINCRONIZAÇÃO CONCLUÍDA COM SUCESSO ---")
        return jsonify({"status": "sucesso"}), 200

    except Exception as e:
        # ISSO AQUI VAI SALVAR A NOSSA VIDA:
        print(f"ERRO CRÍTICO NA SINCRONIZAÇÃO: {e}")
        return jsonify({"status": "erro", "detalhe": str(e)}), 500

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