const API_URL = "http://127.0.0.1:5000";

// Verifica se existe a marcação de login no navegador
if (localStorage.getItem('usuario_logado') !== 'true') {
    // Se não estiver logado, manda de volta para o login
    window.location.href = "login.html";
}

// 1. Carregar Colaboradores
async function carregarColaboradores() {
    const res = await fetch(`${API_URL}/colaboradores`);
    const dados = await res.json();
    const corpo = document.getElementById('tabela-corpo');
    corpo.innerHTML = '';

    dados.forEach(c => {
        corpo.innerHTML += `
            <tr>
                <td>${c.nome}</td>
                <td>${c.tag_rfid}</td>
                <td>${c.funcao}</td>
                <td>${c.permissao_acesso ? '✅ Sim' : '❌ Não'}</td>
                <td>${c.esta_na_sala ? '🔵 Na Sala' : '⚪ Fora'}</td>
                <td>
                    <button onclick="prepararEdicao(${c.id}, '${c.nome}', '${c.tag_rfid}', '${c.funcao}', ${c.permissao_acesso})">Editar</button>
                    <button onclick="deletarColaborador(${c.id})">Deletar</button>
                </td>
            </tr>
        `;
    });
}

// 2. Salvar (POST ou PUT)
document.getElementById('colaborador-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('colaborador-id').value;
    const corpo = {
        nome: document.getElementById('nome').value,
        tag_rfid: document.getElementById('tag_rfid').value,
        funcao: document.getElementById('funcao').value,
        permissao_acesso: document.getElementById('permissao_acesso').checked
    };

    const metodo = id ? 'PUT' : 'POST';
    const url = id ? `${API_URL}/colaboradores/${id}` : `${API_URL}/colaboradores`;

    await fetch(url, {
        method: metodo,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(corpo)
    });

    limparFormulario();
    carregarColaboradores();
});

// 3. Deletar
async function deletarColaborador(id) {
    if (confirm("Deseja realmente excluir este colaborador?")) {
        await fetch(`${API_URL}/colaboradores/${id}`, { method: 'DELETE' });
        carregarColaboradores();
    }
}

// Auxiliares
function prepararEdicao(id, nome, tag, funcao, permissao) {
    document.getElementById('colaborador-id').value = id;
    document.getElementById('nome').value = nome;
    document.getElementById('tag_rfid').value = tag;
    document.getElementById('funcao').value = funcao;
    document.getElementById('permissao_acesso').checked = permissao;
    document.getElementById('form-title').innerText = "Editar Colaborador";
    document.getElementById('btn-cancelar').style.display = 'inline';
}

function limparFormulario() {
    document.getElementById('colaborador-form').reset();
    document.getElementById('colaborador-id').value = '';
    document.getElementById('form-title').innerText = "Cadastrar Novo Colaborador";
    document.getElementById('btn-cancelar').style.display = 'none';
}

function logout() {
    localStorage.removeItem('usuario_logado'); // Apaga a permissão
    window.location.href = "login.html"; // Volta para o início
}

// Inicializar
carregarColaboradores();