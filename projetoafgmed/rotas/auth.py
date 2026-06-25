from flask import render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required

from projetoafgmed import app, database, bcrypt
from projetoafgmed.models import Usuario
from projetoafgmed.forms import FormCriarConta, FormLogin


@app.route("/criar-conta", methods=["GET", "POST"])
def criar_conta():
    form = FormCriarConta()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        email_existente = Usuario.query.filter_by(email=email).first()

        if email_existente:
            return render_template(
                "cadastro.html",
                form=form,
                email_duplicado=True,
                email_informado=email
            )

        senha_hash = bcrypt.generate_password_hash(form.senha.data).decode("utf-8")

        usuario = Usuario(
            nome=form.nome.data,
            sobrenome=form.sobrenome.data,
            email=email,
            senha=senha_hash
        )

        database.session.add(usuario)
        database.session.commit()

        return redirect(url_for("login"))

    return render_template(
        "cadastro.html",
        form=form,
        email_duplicado=False
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    form = FormLogin()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and bcrypt.check_password_hash(usuario.senha, form.senha.data):
            login_user(usuario)

            if getattr(usuario, "is_medico", False) and not getattr(usuario, "is_admin", False):
                return redirect(url_for("medicos"))

            return redirect(url_for("homepage"))

        flash("Email ou senha incorretos.", "danger")

    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("homepage"))