import sqlite3

def init_db():
    conn = sqlite3.connect('seguranca.db')
    cursor = conn.cursor()

    # Criando a tabela de colaboradores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS colaboradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tag_rfid TEXT UNIQUE NOT NULL,
            funcao TEXT,
            permissao_acesso BOOLEAN DEFAULT 0,
            esta_na_sala BOOLEAN DEFAULT 0
        )
    ''')

    # Criando a tabela de logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_acesso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            colaborador_id INTEGER, -- Guardamos o ID numérico
            nome_colaborador TEXT,   -- Guardamos o Nome para facilitar a leitura
            tag_rfid TEXT,
            timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
            tipo_evento TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()
    print("Banco de dados e tabelas criados com sucesso!")

if __name__ == "__main__":
    init_db()