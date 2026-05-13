const API_URL = "http://192.168.0.7:5000";

async function atualizarPainel() {
    try {
        const res = await fetch(`${API_URL}/monitoramento_dados`);
        const dados = await res.json();

        // 1. Atualizar Colaboradores na Sala
        const listaPresenca = document.getElementById('lista-presenca');
        listaPresenca.innerHTML = dados.na_sala.length ? '' : '<li>Ninguém na sala no momento.</li>';
        dados.na_sala.forEach(c => {
            listaPresenca.innerHTML += `<li><strong>${c[0]}</strong> (${c[1]})</li>`;
        });

        // 2. Atualizar Tabela de Eventos (Entradas e Saídas)
        const tabelaCorpo = document.querySelector('#tabela-atividades tbody');
        tabelaCorpo.innerHTML = '';
        dados.eventos.forEach(e => {
            const nome = e[0] || "Tag: " + e[1];
            const classeEvento = e[3].includes('ENTRADA') ? 'texto-entrada' : 'texto-saida';
            tabelaCorpo.innerHTML += `
                <tr>
                    <td>${nome}</td>
                    <td>${new Date(e[2]).toLocaleTimeString()}</td>
                    <td class="${classeEvento}">${e[3]}</td>
                </tr>`;
        });

        // 3. Atualizar Alertas (Invasão / Não Autorizado)
        // No monitor.js, dentro da função atualizarPainel():

        const listaAlertas = document.getElementById('lista-alertas');
        listaAlertas.innerHTML = ''; // Limpa antes de preencher

        if (dados.alertas && dados.alertas.length > 0) {
            dados.alertas.forEach(a => {
                // a[0] = tag_rfid, a[1] = timestamp, a[2] = tipo_evento
                const div = document.createElement('div');
                div.className = 'alerta-item';
                
                // Formatação simples para o alerta
                div.innerHTML = `
                    <p style="color: red; margin: 5px 0;">
                        <strong>🚨 ${a[2]}</strong><br>
                        Tag: ${a[0]} | Hora: ${new Date(a[1]).toLocaleTimeString()}
                    </p>
                    <hr>
                `;
                listaAlertas.appendChild(div);
            });
        } else {
            listaAlertas.innerHTML = '<p>✅ Nenhum incidente crítico recente.</p>';
        }

    } catch (err) {
        console.error("Erro ao buscar dados:", err);
    }
}

// Atualiza a cada 3 segundos
setInterval(atualizarPainel, 3000);
atualizarPainel(); // Primeira execução