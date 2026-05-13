const API_URL = "http://127.0.0.1:5000";

async function fazerLogin(event) {
    event.preventDefault(); 
    
    const user = document.getElementById('username').value;
    const pass = document.getElementById('password').value;

    try {
        const res = await fetch(`${API_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user, password: pass })
        });

        const data = await res.json();

        if (res.ok) {
            localStorage.setItem('usuario_logado', 'true');
            window.location.href = "index.html"; 
        } else {
            alert(data.mensagem || "Usuário ou senha incorretos");
        }
    } catch (error) {
        alert("Erro ao conectar com o servidor.");
    }
}

// ESTA LINHA É A CHAVE: Ela liga o seu formulário à função do JS
document.getElementById('login-form').addEventListener('submit', fazerLogin);