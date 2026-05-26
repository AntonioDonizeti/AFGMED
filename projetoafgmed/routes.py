from projetoafgmed import app, database, bcrypt
from projetoafgmed.models import Usuario, Medico, Produto ,Carrinho, ItemCarrinho
from projetoafgmed.forms import FormProduto, FormCriarConta, FormLogin, FormMedico
from flask import render_template, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask import request
import os
from werkzeug.utils import secure_filename


# ----------------- HOME -----------------
@app.route("/")
def homepage():
    produtos_destaque = Produto.query.limit(4).all()
    carrinho = None
    if current_user.is_authenticated:
        carrinho = Carrinho.query.filter_by(id_usuario=current_user.id, status='ativo').first()
    return render_template("homepage.html", produtos=produtos_destaque, carrinho=carrinho)

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
            return redirect(url_for("homepage"))
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

# ----------------- ADICIONAR PRODUTO AO CARRINHO -----------------
@app.route("/adicionar-carrinho/<int:id_produto>", methods=["POST"])
@login_required
def adicionar_carrinho(id_produto):
    produto = Produto.query.get_or_404(id_produto)

    # Pega o carrinho ativo do usuário ou cria
    carrinho = Carrinho.query.filter_by(id_usuario=current_user.id, status='ativo').first()
    if not carrinho:
        carrinho = Carrinho(id_usuario=current_user.id)
        database.session.add(carrinho)
        database.session.commit()

    # Verifica se o produto já está no carrinho
    item = ItemCarrinho.query.filter_by(id_carrinho=carrinho.id, id_produto=produto.id).first()
    if item:
        item.quantidade += 1
    else:
        item = ItemCarrinho(
            id_carrinho=carrinho.id,
            id_produto=produto.id,
            quantidade=1,
            preco_unitario=produto.preco
        )
        database.session.add(item)

    database.session.commit()
    flash(f"{produto.nome} adicionado ao carrinho!", "success")
    return redirect(request.referrer)

# ----------------- VISUALIZAR CARRINHO -----------------
@app.route("/carrinho")
@login_required
def ver_carrinho():
    carrinho = Carrinho.query.filter_by(id_usuario=current_user.id, status='ativo').first()
    itens = carrinho.itens if carrinho else []
    total = sum([item.quantidade * item.preco_unitario for item in itens])
    return render_template("carrinho.html", itens=itens, total=total)

# ----------------- REMOVER ITEM -----------------
@app.route("/remover-carrinho/<int:id_item>", methods=["POST"])
@login_required
def remover_item_carrinho(id_item):
    item = ItemCarrinho.query.get_or_404(id_item)
    database.session.delete(item)
    database.session.commit()
    flash("Item removido do carrinho!", "info")
    return redirect(url_for("ver_carrinho"))

# ----------------- FINALIZAR COMPRA -----------------
@app.route("/finalizar-carrinho", methods=["POST"])
@login_required
def finalizar_carrinho():
    carrinho = Carrinho.query.filter_by(id_usuario=current_user.id, status='ativo').first()
    if not carrinho or not carrinho.itens:
        flash("Carrinho vazio!", "warning")
        return redirect(url_for("ver_carrinho"))

    carrinho.status = "finalizado"
    database.session.commit()
    flash("Compra finalizada com sucesso!", "success")
    return redirect(url_for("homepage"))