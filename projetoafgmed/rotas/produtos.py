from flask import render_template, redirect, url_for, flash, current_app, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os

from projetoafgmed import app, database
from projetoafgmed.models import Produto
from projetoafgmed.forms import FormProduto


@app.route("/produtos")
@login_required
def produtos():
    return render_template("produtos.html", produtos=Produto.query.all())


@app.route("/cadastro-produto", methods=["GET", "POST"])
@login_required
def cadastro_produto():
    if not getattr(current_user, "is_admin", False):
        flash("Apenas administradores podem acessar esta página.", "warning")
        return redirect(url_for("homepage"))

    form = FormProduto()

    if form.validate_on_submit():
        preco_str = str(form.preco.data).replace(",", ".")
        form.preco.data = float(preco_str)

        nome_foto = "default.jpg"

        pasta_uploads = os.path.join(
            current_app.root_path,
            "static/fotos_produtos"
        )

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
            foto=nome_foto,
            ativo=form.ativo.data,
            destaque_home=form.destaque_home.data
        )

        database.session.add(produto)
        database.session.commit()

        flash("Produto cadastrado com sucesso!", "success")
        return redirect(url_for("produtos"))

    return render_template("cadastro_produto.html", form=form)


@app.route("/editar-produto/<int:id_produto>", methods=["GET", "POST"])
@login_required
def editar_produto(id_produto):
    if not getattr(current_user, "is_admin", False):
        flash("Apenas administradores podem acessar esta página.", "warning")
        return redirect(url_for("homepage"))

    produto = Produto.query.get_or_404(id_produto)
    form = FormProduto()

    if request.method == "GET":
        form.nome.data = produto.nome
        form.descricao.data = produto.descricao
        form.preco.data = produto.preco
        form.estoque.data = produto.estoque
        form.ativo.data = produto.ativo
        form.destaque_home.data = produto.destaque_home

    if form.validate_on_submit():
        produto.nome = form.nome.data
        produto.descricao = form.descricao.data
        produto.preco = form.preco.data
        produto.estoque = form.estoque.data
        produto.ativo = form.ativo.data
        produto.destaque_home = form.destaque_home.data

        if form.foto.data:
            arquivo = form.foto.data
            nome_foto = secure_filename(arquivo.filename)

            caminho = os.path.join(
                current_app.root_path,
                "static/fotos_produtos",
                nome_foto
            )

            os.makedirs(os.path.dirname(caminho), exist_ok=True)
            arquivo.save(caminho)

            produto.foto = nome_foto

        database.session.commit()

        flash("Produto atualizado com sucesso!", "success")
        return redirect(url_for("produtos"))

    return render_template("cadastro_produto.html", form=form, produto=produto)


@app.route("/alternar-destaque-produto/<int:id_produto>", methods=["POST"])
@login_required
def alternar_destaque_produto(id_produto):
    if not getattr(current_user, "is_admin", False):
        flash("Apenas administradores podem acessar.", "warning")
        return redirect(url_for("produtos"))

    produto = Produto.query.get_or_404(id_produto)

    produto.destaque_home = not produto.destaque_home

    database.session.commit()

    flash("Produto adicionado ou removido dos Mais Vendidos.", "success")
    return redirect(url_for("produtos"))


@app.route("/desativar-produto/<int:id_produto>", methods=["POST"])
@login_required
def desativar_produto(id_produto):
    if not getattr(current_user, "is_admin", False):
        flash("Apenas administradores podem acessar.", "warning")
        return redirect(url_for("produtos"))

    produto = Produto.query.get_or_404(id_produto)

    produto.ativo = False

    database.session.commit()

    flash("Produto desativado.", "info")
    return redirect(url_for("produtos"))


@app.route("/ativar-produto/<int:id_produto>", methods=["POST"])
@login_required
def ativar_produto(id_produto):
    if not getattr(current_user, "is_admin", False):
        flash("Apenas administradores podem acessar.", "warning")
        return redirect(url_for("produtos"))

    produto = Produto.query.get_or_404(id_produto)

    produto.ativo = True

    database.session.commit()

    flash("Produto ativado.", "success")
    return redirect(url_for("produtos"))