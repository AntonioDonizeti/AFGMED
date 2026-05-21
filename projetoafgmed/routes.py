from projetoafgmed import app, database, bcrypt
from projetoafgmed.models import Usuario, Medico, Produto
from projetoafgmed.forms import FormProduto, FormCriarConta, FormLogin, FormMedico
from flask import render_template, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
import os
from werkzeug.utils import secure_filename


# ----------------- HOME -----------------
@app.route("/")
def homepage():
    # Puxa 4 produtos mais recentes ou mais vendidos
    produtos_destaque = Produto.query.limit(4).all()
    return render_template("homepage.html", produtos=produtos_destaque)

# ----------------- CADASTRO USUÁRIO -----------------
@app.route("/criar-conta", methods=["GET","POST"])
def criar_conta():
    form = FormCriarConta()
    if form.validate_on_submit():
        senha_hash = bcrypt.generate_password_hash(form.senha.data).decode('utf-8')
        usuario = Usuario(
            nome=form.nome.data,
            sobrenome=form.sobrenome.data,
            email=form.email.data,
            senha=senha_hash
        )
        database.session.add(usuario)
        database.session.commit()
        flash("Conta criada com sucesso!", "success")
        return redirect(url_for("login"))
    return render_template("cadastro.html", form=form)

# ----------------- LOGIN -----------------
@app.route("/login", methods=["GET","POST"])
def login():
    form = FormLogin()
    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(email=form.email.data).first()
        if usuario and bcrypt.check_password_hash(usuario.senha, form.senha.data):
            login_user(usuario)
            return redirect(url_for("medicos"))
        else:
            flash("Email ou senha incorretos.", "danger")
    return render_template("login.html", form=form)

# ----------------- LOGOUT -----------------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("homepage"))

# ----------------- MÉDICOS -----------------
@app.route("/medicos")
@login_required
def medicos():
    medicos_lista = Medico.query.all()
    return render_template("medicos.html", medicos=medicos_lista)

@app.route("/cadastro-medico", methods=["GET", "POST"])
@login_required
def cadastro_medico():
    if not current_user.is_admin:
        flash("Apenas administradores podem acessar esta página.", "warning")
        return redirect(url_for("homepage"))

    form = FormMedico()
    if form.validate_on_submit():
        nome_arquivo = "default.jpg"
        if form.foto.data:
            arquivo = form.foto.data
            nome_arquivo = secure_filename(arquivo.filename)
            caminho = os.path.join(current_app.root_path, "static/fotos_medicos", nome_arquivo)
            os.makedirs(os.path.dirname(caminho), exist_ok=True)
            arquivo.save(caminho)

        medico = Medico(
            nome=form.nome.data,
            especialidade=form.especialidade.data,
            email=form.email.data,
            telefone=form.telefone.data,
            foto=nome_arquivo
        )
        database.session.add(medico)
        database.session.commit()
        flash("Médico cadastrado com sucesso!", "success")
        return redirect(url_for("medicos"))

    return render_template("cadastro_medico.html", form=form)

# ----------------- PRODUTOS -----------------
@app.route("/produtos")
@login_required
def produtos():
    produtos_lista = Produto.query.all()
    return render_template("produtos.html", produtos=produtos_lista)

@app.route("/cadastro-produto", methods=["GET","POST"])
@login_required
def cadastro_produto():
    if not current_user.is_admin:
        flash("Apenas administradores podem acessar esta página.", "warning")
        return redirect(url_for("homepage"))

    form = FormProduto()
    if form.validate_on_submit():
        # Converte vírgula para ponto no preço
        preco_str = str(form.preco.data).replace(",", ".")
        form.preco.data = float(preco_str)

        nome_foto = "default.jpg"
        pasta_uploads = os.path.join(current_app.root_path, 'static/fotos_produtos')
        os.makedirs(pasta_uploads, exist_ok=True)

        if form.foto.data:
            arquivo = form.foto.data
            nome_foto = secure_filename(arquivo.filename)
            caminho = os.path.join(pasta_uploads, nome_foto)
            arquivo.save(caminho)

        produto = Produto(
            nome=form.nome.data,
            descricao=form.descricao.data,
            preco=form.preco.data,
            estoque=form.estoque.data,
            foto=nome_foto
        )
        database.session.add(produto)
        database.session.commit()
        flash("Produto cadastrado com sucesso!", "success")
        return redirect(url_for("produtos"))

    return render_template("cadastro_produto.html", form=form)