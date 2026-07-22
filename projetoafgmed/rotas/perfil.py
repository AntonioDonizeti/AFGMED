from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
from uuid import uuid4
import os

from projetoafgmed import app, database
from projetoafgmed.models import Usuario, PerfilUsuario


EXTENSOES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp"}


@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    usuario = current_user
    perfil_usuario = usuario.perfil or PerfilUsuario(usuario=usuario)

    if request.method == "POST":

        # FOTO DE PERFIL
        if "foto" in request.files and request.files["foto"].filename:
            arquivo = request.files["foto"]
            nome_original = secure_filename(arquivo.filename)
            extensao = os.path.splitext(nome_original)[1].lower()

            if extensao not in EXTENSOES_PERMITIDAS:
                flash("Formato de imagem inválido. Use JPG, PNG ou WEBP.", "danger")
                return redirect(url_for("perfil"))

            nome_foto = f"{uuid4().hex}{extensao}"

            pasta_fotos = os.path.join(app.root_path, "static", "fotos_perfil")
            os.makedirs(pasta_fotos, exist_ok=True)

            caminho = os.path.join(pasta_fotos, nome_foto)
            arquivo.save(caminho)

            usuario.foto = nome_foto

        # DADOS DO USUÁRIO
        usuario.nome = request.form.get("nome") or usuario.nome
        usuario.sobrenome = request.form.get("sobrenome") or usuario.sobrenome

        email_novo = request.form.get("email")

        if email_novo:
            email_novo = email_novo.strip().lower()

            email_em_uso = Usuario.query.filter(
                Usuario.email == email_novo,
                Usuario.id != current_user.id
            ).first()

            if email_em_uso:
                flash("Este e-mail já está em uso.", "danger")
                return redirect(url_for("perfil"))

            usuario.email = email_novo

        # DADOS COMPLEMENTARES
        perfil_usuario.telefone = request.form.get("telefone")
        perfil_usuario.cpf = request.form.get("cpf")

        data_nascimento = request.form.get("data_nascimento")

        if data_nascimento:
            try:
                perfil_usuario.data_nascimento = datetime.strptime(
                    data_nascimento,
                    "%Y-%m-%d"
                ).date()
            except ValueError:
                flash("Data de nascimento inválida.", "danger")
                return redirect(url_for("perfil"))
        else:
            perfil_usuario.data_nascimento = None

        # ENDEREÇO
        perfil_usuario.endereco = request.form.get("endereco")
        perfil_usuario.cidade = request.form.get("cidade")
        perfil_usuario.estado = request.form.get("estado")
        perfil_usuario.cep = request.form.get("cep")

        database.session.add(usuario)
        database.session.add(perfil_usuario)
        database.session.commit()

        flash("Perfil atualizado com sucesso!", "success")
        return redirect(url_for("perfil"))

    return render_template(
        "perfil.html",
        usuario=usuario,
        perfil=perfil_usuario
    )