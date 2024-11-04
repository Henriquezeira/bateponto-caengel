from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'

# Função para converter string para datetime
@app.template_filter('to_datetime')
def to_datetime(date_string):
    try:
        return datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None

# Função para conectar ao banco de dados
def conecta_bd():
    return sqlite3.connect('database.db')

# Inicializa o banco de dados
def inicializa_bd():
    conn = conecta_bd()
    cursor = conn.cursor()

    # Criar tabela para registros de check-in/check-out
    cursor.execute('''CREATE TABLE IF NOT EXISTS registros (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT,
                        data TEXT,
                        checkin TEXT,
                        checkout TEXT,
                        total_horas TEXT)''')

    # Criar tabela para cadastrar pessoas
    cursor.execute('''CREATE TABLE IF NOT EXISTS pessoas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT UNIQUE)''')

    # Criar tabela para usuários
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT UNIQUE,
                        senha TEXT)''')

    conn.commit()
    conn.close()

# Função para adicionar um usuário (admin)
def adicionar_usuario(nome, senha):
    conn = conecta_bd()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (nome, senha) VALUES (?, ?)", (nome, senha))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

# Rota principal (exibir página inicial)
@app.route('/')
def index():
    conn = conecta_bd()
    cursor = conn.cursor()

    nome_selecionado = request.args.get('nome_selecionado', None)

    if nome_selecionado:
        cursor.execute("SELECT * FROM registros WHERE nome = ? AND data = ?", (nome_selecionado, datetime.now().strftime("%Y-%m-%d")))
        registros = cursor.fetchall()
    else:
        registros = []

    cursor.execute("SELECT * FROM pessoas")
    pessoas = cursor.fetchall()
    conn.close()

    return render_template('index.html', registros=registros, pessoas=pessoas, nome_selecionado=nome_selecionado)


# Rota para fazer check-in
@app.route('/checkin', methods=['POST'])
def checkin():
    nome = request.form['nome']
    data = datetime.now().strftime("%Y-%m-%d")
    hora = datetime.now().strftime("%H:%M:%S")

    conn = conecta_bd()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO registros (nome, data, checkin) VALUES (?, ?, ?)", (nome, data, hora))
    conn.commit()
    conn.close()

    return redirect(url_for('index', nome_selecionado=nome))


# Rota para fazer check-out
@app.route('/checkout/<int:id>', methods=['POST'])
def checkout(id):
    hora_saida = datetime.now().strftime("%H:%M:%S")
    conn = conecta_bd()
    cursor = conn.cursor()
    
    cursor.execute("SELECT checkin, data FROM registros WHERE id = ?", (id,))
    registro = cursor.fetchone()
    
    if registro:
        checkin_time = registro[0]
        data = registro[1]
        
        total_horas = calcular_horas(checkin_time, hora_saida)
        
        cursor.execute("UPDATE registros SET checkout = ?, total_horas = ? WHERE id = ?", (hora_saida, total_horas, id))
        conn.commit()
    
    conn.close()
    return redirect(url_for('index'))

def calcular_horas(checkin, checkout):
    checkin_dt = datetime.strptime(checkin, '%H:%M:%S')
    checkout_dt = datetime.strptime(checkout, '%H:%M:%S')
    
    delta = checkout_dt - checkin_dt
    return str(delta)

# Rota para adicionar uma nova pessoa
@app.route('/adicionar_pessoa', methods=['POST'])
def adicionar_pessoa():
    if 'usuario' not in session:
        return redirect(url_for('index'))

    nome = request.form['nome']
    conn = conecta_bd()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO pessoas (nome) VALUES (?)", (nome,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    return redirect(url_for('admin'))

# Rota para excluir uma pessoa
@app.route('/excluir_pessoa/<int:id>', methods=['POST'])
def excluir_pessoa(id):
    if 'usuario' not in session:
        return redirect(url_for('index'))
    
    conn = conecta_bd()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pessoas WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('admin'))

# Rota para login de admin
@app.route('/login', methods=['POST'])
def login():
    nome = request.form['nome']
    senha = request.form['senha']

    conn = conecta_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE nome = ? AND senha = ?", (nome, senha))
    usuario = cursor.fetchone()
    conn.close()

    if usuario:
        session['usuario'] = nome
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('index'))

# Função para obter registros da última semana
def obter_registros_semanal():
    conn = conecta_bd()
    cursor = conn.cursor()
    uma_semana_atras = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    cursor.execute("SELECT * FROM registros WHERE data >= ?", (uma_semana_atras,))
    registros = cursor.fetchall()
    conn.close()
    return registros

# Rota para a página do admin
@app.route('/admin')
def admin():
    conn = conecta_bd()
    cursor = conn.cursor()

    hoje = datetime.now()
    inicio_semana = hoje - timedelta(days=hoje.weekday())

    cursor.execute("SELECT * FROM pessoas")
    pessoas = cursor.fetchall()

    registros_semana = []
    for pessoa in pessoas:
        pessoa_id, nome = pessoa

        cursor.execute("""
            SELECT data, checkin, checkout FROM registros
            WHERE nome = ? AND data >= ? AND data <= ?
        """, (nome, inicio_semana.strftime("%Y-%m-%d"), hoje.strftime("%Y-%m-%d")))
        registros = cursor.fetchall()

        total_horas_semana = 0
        for registro in registros:
            check_in = datetime.strptime(registro[1], "%H:%M:%S")
            check_out = datetime.strptime(registro[2], "%H:%M:%S") if registro[2] else None
            if check_out:
                horas_trabalhadas = (check_out - check_in).total_seconds() / 3600
                total_horas_semana += horas_trabalhadas

        registros_semana.append({
            'nome': nome,
            'total_horas_semana': round(total_horas_semana, 2),
            'registros': registros
        })

    conn.close()

    return render_template('admin.html', registros_semana=registros_semana, pessoas=pessoas, usuario='Admin')

# Rota para logout
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    inicializa_bd()
    # adicionar_usuario('admin', 'senha123')  # Execute esta linha apenas uma vez para criar o usuário
    app.run(debug=True)
    port = int(os.environ.get('PORT', 5000))  # 5000 é o padrão local
    app.run(host='0.0.0.0', port=port)
