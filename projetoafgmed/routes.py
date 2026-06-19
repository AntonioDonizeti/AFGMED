from projetoafgmed import app, database, bcrypt
from projetoafgmed.models import Usuario, Medico, Produto, Carrinho, ItemCarrinho, Consulta, Entrega, PerfilUsuario
from projetoafgmed.forms import FormProduto, FormCriarConta, FormLogin, FormMedico
from flask import render_template, redirect, url_for, flash, current_app, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import mercadopago
import os


# ----------------- CARRINHO GLOBAL -----------------
@app.context_processor
def carrinho_global():
    if current_user.is_authenticated:
        carrinho = Carrinho.query.filter_by(
            id_usuario=current_user.id,
            status="ativo"
        ).first()

        itens = carrinho.itens if carrinho else []
        total = sum(item.quantidade * item.preco_unitario for item in itens)
        quantidade = sum(item.quantidade for item in itens)

        return {
            "carrinho": carrinho,
            "itens_carrinho": itens,
            "total_carrinho": total,
            "quantidade_carrinho": quantidade
        }

    return {
        "carrinho": None,
        "itens_carrinho": [],
        "total_carrinho": 0,
        "quantidade_carrinho": 0
    }


# ----------------- HOME -----------------
@app.route("/")
def homepage():
    produtos_destaque = Produto.query.filter_by(
        ativo=True,
        destaque_home=True
    ).limit(4).all()

    return render_template("homepage.html", produtos=produtos_destaque)


# ----------------- USUÁRIOS -----------------
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
            return redirect(url_for("homepage"))

        flash("Email ou senha incorretos.", "danger")

    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("homepage"))


# ----------------- PERFIL -----------------
@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    usuario = current_user
    perfil = usuario.perfil or PerfilUsuario(usuario=usuario)

    if request.method == "POST":
        if "foto" in request.files and request.files["foto"].filename:
            arquivo = request.files["foto"]
            nome_foto = secure_filename(arquivo.filename)

            pasta_fotos = os.path.join(app.root_path, "static/fotos_perfil")
            os.makedirs(pasta_fotos, exist_ok=True)

            caminho = os.path.join(pasta_fotos, nome_foto)
            arquivo.save(caminho)

            usuario.foto = nome_foto

        usuario.nome = request.form.get("nome") or usuario.nome
        usuario.sobrenome = request.form.get("sobrenome") or usuario.sobrenome

        email_novo = request.form.get("email")
        if email_novo:
            usuario.email = email_novo.strip().lower()

        perfil.endereco = request.form.get("endereco")
        perfil.cidade = request.form.get("cidade")
        perfil.estado = request.form.get("estado")
        perfil.cep = request.form.get("cep")

        database.session.add(usuario)
        database.session.add(perfil)
        database.session.commit()

        flash("Perfil atualizado com sucesso!", "success")
        return redirect(url_for("perfil"))

    return render_template("perfil.html", usuario=usuario, perfil=perfil)


# ----------------- MÉDICOS -----------------
@app.route("/medicos")
@login_required
def medicos():
    return render_template("medicos.html", medicos=Medico.query.all())


@app.route("/cadastro-medico", methods=["GET", "POST"])
@login_required
def cadastro_medico():
    if not getattr(current_user, "is_admin", False):
        flash("Apenas administradores podem acessar esta página.", "warning")
        return redirect(url_for("homepage"))

    form = FormMedico()

    if form.validate_on_submit():
        nome_arquivo = "default.jpg"

        if form.foto.data:
            arquivo = form.foto.data
            nome_arquivo = secure_filename(arquivo.filename)

            caminho = os.path.join(
                current_app.root_path,
                "static/fotos_medicos",
                nome_arquivo
            )

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


# ----------------- CONSULTAS -----------------
@app.route("/consultas/<int:medico_id>", methods=["GET", "POST"])
@login_required
def consultas(medico_id):
    medico = Medico.query.get_or_404(medico_id)
    horarios = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]

    if request.method == "POST":
        horario = request.form.get("horario")
        data_consulta = request.form.get("data_consulta")

        if not horario or not data_consulta:
            flash("Escolha data e horário para continuar.", "warning")
            return redirect(url_for("consultas", medico_id=medico.id))

        if horario not in horarios:
            flash("Horário inválido.", "danger")
            return redirect(url_for("consultas", medico_id=medico.id))

        try:
            data_obj = datetime.strptime(data_consulta, "%Y-%m-%d").date()
        except ValueError:
            flash("Data inválida.", "danger")
            return redirect(url_for("consultas", medico_id=medico.id))

        if data_obj < datetime.today().date():
            flash("Não é possível marcar consulta em data passada.", "warning")
            return redirect(url_for("consultas", medico_id=medico.id))

        existente = Consulta.query.filter_by(
            medico_id=medico.id,
            horario=horario,
            data=data_obj
        ).first()

        if existente:
            flash("Horário já reservado para essa data!", "danger")
            return redirect(url_for("consultas", medico_id=medico.id))

        nova_consulta = Consulta(
            medico_id=medico.id,
            usuario_id=current_user.id,
            horario=horario,
            data=data_obj
        )

        database.session.add(nova_consulta)
        database.session.commit()

        flash("Consulta agendada com sucesso!", "success")
        return redirect(url_for("meus_agendamentos"))

    consultas_marcadas = Consulta.query.filter_by(medico_id=medico.id).all()

    return render_template(
        "consultas.html",
        medico=medico,
        horarios=horarios,
        consultas=consultas_marcadas
    )


@app.route("/horarios_disponiveis/<int:medico_id>/<data>")
@login_required
def horarios_disponiveis(medico_id, data):
    try:
        data_obj = datetime.strptime(data, "%Y-%m-%d").date()
    except ValueError:
        return jsonify([])

    consultas = Consulta.query.filter_by(
        medico_id=medico_id,
        data=data_obj
    ).all()

    horarios_ocupados = [c.horario for c in consultas]

    return jsonify(horarios_ocupados)


@app.route("/meus_agendamentos")
@login_required
def meus_agendamentos():
    consultas = Consulta.query.filter_by(usuario_id=current_user.id) \
        .order_by(Consulta.data.asc(), Consulta.horario.asc()) \
        .all()

    return render_template("meus_agendamentos.html", consultas=consultas)


@app.route("/cancelar_consulta/<int:consulta_id>", methods=["POST"])
@login_required
def cancelar_consulta(consulta_id):
    consulta = Consulta.query.get_or_404(consulta_id)

    if consulta.usuario_id != current_user.id:
        flash("Você não pode cancelar esta consulta.", "danger")
        return redirect(url_for("meus_agendamentos"))

    database.session.delete(consulta)
    database.session.commit()

    flash("Consulta cancelada com sucesso!", "success")
    return redirect(url_for("meus_agendamentos"))


# ----------------- EDITAR MÉDICO -----------------
@app.route("/editar-medico/<int:id_medico>", methods=["GET", "POST"])
@login_required
def editar_medico(id_medico):
    if not getattr(current_user, "is_admin", False):
        flash("Apenas administradores podem acessar esta página.", "warning")
        return redirect(url_for("homepage"))

    medico = Medico.query.get_or_404(id_medico)
    form = FormMedico()

    if request.method == "GET":
        form.nome.data = medico.nome
        form.especialidade.data = medico.especialidade
        form.email.data = medico.email
        form.telefone.data = medico.telefone

    if form.validate_on_submit():
        medico.nome = form.nome.data
        medico.especialidade = form.especialidade.data
        medico.email = form.email.data
        medico.telefone = form.telefone.data

        if form.foto.data:
            arquivo = form.foto.data
            nome_foto = secure_filename(arquivo.filename)

            caminho = os.path.join(
                current_app.root_path,
                "static/fotos_medicos",
                nome_foto
            )

            os.makedirs(os.path.dirname(caminho), exist_ok=True)
            arquivo.save(caminho)

            medico.foto = nome_foto

        database.session.commit()

        flash("Médico atualizado com sucesso!", "success")
        return redirect(url_for("medicos"))

    return render_template("cadastro_medico.html", form=form, medico=medico)


@app.route("/remover-medico/<int:id_medico>", methods=["POST"])
@login_required
def remover_medico(id_medico):
    if not getattr(current_user, "is_admin", False):
        flash("Apenas administradores podem acessar.", "warning")
        return redirect(url_for("homepage"))

    medico = Medico.query.get_or_404(id_medico)

    Consulta.query.filter_by(medico_id=id_medico).delete()

    database.session.delete(medico)
    database.session.commit()

    flash("Médico removido com sucesso!", "success")
    return redirect(url_for("medicos"))


# ----------------- PRODUTOS -----------------
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

            arquivo.save(caminho)
            produto.foto = nome_foto

        database.session.commit()

        flash("Produto atualizado com sucesso!", "success")
        return redirect(url_for("produtos"))

    return render_template("cadastro_produto.html", form=form, produto=produto)


# ----------------- CARRINHO -----------------
@app.route("/adicionar-carrinho/<int:id_produto>", methods=["POST"])
@login_required
def adicionar_carrinho(id_produto):
    produto = Produto.query.get_or_404(id_produto)

    if not produto.ativo:
        flash("Produto indisponível.", "warning")
        return redirect(request.referrer or url_for("produtos"))

    if produto.estoque <= 0:
        flash("Produto sem estoque.", "warning")
        return redirect(request.referrer or url_for("produtos"))

    carrinho = Carrinho.query.filter_by(
        id_usuario=current_user.id,
        status="ativo"
    ).first()

    if not carrinho:
        carrinho = Carrinho(id_usuario=current_user.id)
        database.session.add(carrinho)
        database.session.commit()

    item = ItemCarrinho.query.filter_by(
        id_carrinho=carrinho.id,
        id_produto=produto.id
    ).first()

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

    produto.estoque -= 1

    database.session.commit()

    flash(f"{produto.nome} adicionado ao carrinho!", "success")
    return redirect(request.referrer or url_for("produtos"))


@app.route("/atualizar-item/<int:id_item>", methods=["POST"])
@login_required
def atualizar_item(id_item):
    acao = request.form.get("acao")
    item = ItemCarrinho.query.get_or_404(id_item)

    if item.carrinho.id_usuario != current_user.id:
        flash("Você não pode alterar este item.", "danger")
        return redirect(request.referrer or url_for("homepage"))

    produto = Produto.query.get_or_404(item.id_produto)

    if acao == "aumentar":
        if produto.estoque > 0:
            item.quantidade += 1
            produto.estoque -= 1
        else:
            flash("Produto sem estoque.", "warning")

    elif acao == "diminuir":
        if item.quantidade > 1:
            item.quantidade -= 1
            produto.estoque += 1
        else:
            produto.estoque += item.quantidade
            database.session.delete(item)

    database.session.commit()

    return redirect(request.referrer or url_for("homepage") + "#carrinho-aberto")


@app.route("/remover-item/<int:id_item>", methods=["POST"])
@login_required
def remover_item(id_item):
    item = ItemCarrinho.query.get_or_404(id_item)

    if item.carrinho.id_usuario != current_user.id:
        flash("Você não pode remover este item.", "danger")
        return redirect(request.referrer or url_for("homepage"))

    produto = Produto.query.get(item.id_produto)

    if produto:
        produto.estoque += item.quantidade

    database.session.delete(item)
    database.session.commit()

    flash("Item removido do carrinho!", "info")
    return redirect(url_for("ver_carrinho"))


@app.route("/ver-carrinho")
@login_required
def ver_carrinho():
    carrinho = Carrinho.query.filter_by(
        id_usuario=current_user.id,
        status="ativo"
    ).first()

    itens = carrinho.itens if carrinho else []
    total = sum(item.quantidade * item.preco_unitario for item in itens)

    return render_template(
        "_carrinho_lateral.html",
        itens_carrinho=itens,
        total_carrinho=total,
        carrinho=carrinho
    )


@app.route("/finalizar-carrinho", methods=["POST"])
@login_required
def finalizar_carrinho():
    carrinho = Carrinho.query.filter_by(
        id_usuario=current_user.id,
        status="ativo"
    ).first()

    if not carrinho or not carrinho.itens:
        flash("Carrinho vazio!", "warning")
        return redirect(url_for("ver_carrinho"))

    return redirect(url_for("entrega", id_carrinho=carrinho.id))


# ----------------- MERCADO PAGO -----------------
def criar_preferencia_mercado_pago(carrinho):
    access_token = current_app.config.get("MERCADO_PAGO_ACCESS_TOKEN")
    app_base_url = current_app.config.get("APP_BASE_URL")

    if not access_token:
        return None, "Access Token do Mercado Pago não configurado."

    if not app_base_url:
        return None, "APP_BASE_URL não configurada no .env."

    sdk = mercadopago.SDK(access_token)

    itens_mp = []

    for item in carrinho.itens:
        itens_mp.append({
            "title": item.produto.nome,
            "description": item.produto.descricao or "Produto AFGMED",
            "quantity": int(item.quantidade),
            "currency_id": "BRL",
            "unit_price": float(item.preco_unitario)
        })

    preference_data = {
        "items": itens_mp,

        "external_reference": str(carrinho.id),

        "back_urls": {
            "success": f"{app_base_url}/pagamento/sucesso",
            "failure": f"{app_base_url}/pagamento/falha",
            "pending": f"{app_base_url}/pagamento/pendente"
        },

        "auto_return": "approved",

        "notification_url": f"{app_base_url}/webhook/mercado-pago"
    }

    try:
        preference_response = sdk.preference().create(preference_data)

        print("RESPOSTA MERCADO PAGO:")
        print(preference_response)

        status_code = preference_response.get("status")

        if status_code not in [200, 201]:
            erro = preference_response.get("response", {})
            return None, str(erro)

        preference = preference_response.get("response", {})

        return preference, None

    except Exception as erro:
        print("ERRO MERCADO PAGO:")
        print(erro)
        return None, str(erro)


def atualizar_carrinho_por_pagamento(pagamento_id):
    access_token = current_app.config.get("MERCADO_PAGO_ACCESS_TOKEN")

    if not access_token:
        print("Access Token do Mercado Pago não configurado.")
        return None

    sdk = mercadopago.SDK(access_token)

    try:
        pagamento_response = sdk.payment().get(str(pagamento_id))
        pagamento = pagamento_response.get("response", {})
    except Exception as erro:
        print("ERRO AO BUSCAR PAGAMENTO NO MERCADO PAGO:")
        print(erro)
        return None

    print("PAGAMENTO RECEBIDO DO MERCADO PAGO:")
    print("ID:", pagamento.get("id"))
    print("STATUS:", pagamento.get("status"))
    print("CARRINHO:", pagamento.get("external_reference"))

    carrinho_id = pagamento.get("external_reference")

    if not carrinho_id:
        return pagamento

    try:
        carrinho_id = int(carrinho_id)
    except ValueError:
        return pagamento

    carrinho = Carrinho.query.get(carrinho_id)

    if not carrinho:
        return pagamento

    status_pagamento = pagamento.get("status", "pendente")

    carrinho.mercado_pago_payment_id = str(pagamento_id)
    carrinho.status_pagamento = status_pagamento

    if status_pagamento == "approved":
        carrinho.status = "finalizado"

    elif status_pagamento in ["rejected", "cancelled"]:
        carrinho.status = "ativo"

    database.session.commit()

    return pagamento


# ----------------- ENTREGA -----------------
@app.route("/entrega/<int:id_carrinho>", methods=["GET", "POST"])
@login_required
def entrega(id_carrinho):
    carrinho = Carrinho.query.get_or_404(id_carrinho)
    usuario = current_user
    perfil = usuario.perfil or PerfilUsuario(usuario=usuario)

    if carrinho.id_usuario != current_user.id:
        return redirect(url_for("homepage"))

    if carrinho.status != "ativo":
        return redirect(url_for("homepage"))

    if request.method == "POST":
        endereco = request.form.get("endereco") or perfil.endereco
        cidade = request.form.get("cidade") or perfil.cidade
        estado = request.form.get("estado") or perfil.estado
        cep = request.form.get("cep") or perfil.cep

        if not endereco or not cidade or not estado or not cep:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "sucesso": False,
                    "mensagem": "Preencha todos os dados de entrega."
                })

            flash("Preencha todos os dados de entrega.", "warning")
            return redirect(url_for("entrega", id_carrinho=carrinho.id))

        if carrinho.entrega:
            carrinho.entrega.endereco = endereco
            carrinho.entrega.cidade = cidade
            carrinho.entrega.estado = estado
            carrinho.entrega.cep = cep
        else:
            nova_entrega = Entrega(
                id_carrinho=carrinho.id,
                endereco=endereco,
                cidade=cidade,
                estado=estado,
                cep=cep
            )
            database.session.add(nova_entrega)

        database.session.add(perfil)

        carrinho.status = "aguardando_pagamento"
        carrinho.status_pagamento = "pendente"

        database.session.commit()

        preference, erro_mp = criar_preferencia_mercado_pago(carrinho)

        if not preference:
            carrinho.status = "ativo"
            carrinho.status_pagamento = "pendente"
            database.session.commit()

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "sucesso": False,
                    "mensagem": f"Erro Mercado Pago: {erro_mp}"
                })

            flash(f"Erro Mercado Pago: {erro_mp}", "danger")
            return redirect(url_for("entrega", id_carrinho=carrinho.id))

        carrinho.mercado_pago_preference_id = preference.get("id")
        database.session.commit()

        link_pagamento = preference.get("init_point") or preference.get("sandbox_init_point")

        if not link_pagamento:
            carrinho.status = "ativo"
            carrinho.status_pagamento = "pendente"
            database.session.commit()

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "sucesso": False,
                    "mensagem": "Mercado Pago não retornou link de pagamento."
                })

            flash("Mercado Pago não retornou link de pagamento.", "danger")
            return redirect(url_for("entrega", id_carrinho=carrinho.id))

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "sucesso": True,
                "redirect_url": link_pagamento
            })

        return redirect(link_pagamento)

    return render_template(
        "entrega.html",
        carrinho=carrinho,
        perfil=perfil,
        google_maps_api_key=current_app.config.get("GOOGLE_MAPS_API_KEY")
    )


# ----------------- RETORNO DO PAGAMENTO -----------------
@app.route("/pagamento/sucesso")
def pagamento_sucesso():
    payment_id = request.args.get("payment_id") or request.args.get("collection_id")
    carrinho_id = request.args.get("external_reference")

    carrinho = None

    if payment_id:
        pagamento = atualizar_carrinho_por_pagamento(payment_id)

        if pagamento and pagamento.get("external_reference"):
            carrinho_id = pagamento.get("external_reference")

    if carrinho_id:
        try:
            carrinho = Carrinho.query.get(int(carrinho_id))
        except ValueError:
            carrinho = None

    if carrinho and carrinho.status == "finalizado":
        return render_template("pagamento_sucesso.html", carrinho=carrinho)

    return render_template("pagamento_pendente.html", carrinho=carrinho)


@app.route("/pagamento/falha")
def pagamento_falha():
    carrinho_id = request.args.get("external_reference")

    carrinho = None

    if carrinho_id:
        try:
            carrinho = Carrinho.query.get(int(carrinho_id))
        except ValueError:
            carrinho = None

    if carrinho:
        carrinho.status_pagamento = "falha"
        carrinho.status = "ativo"
        database.session.commit()

    return render_template("pagamento_falha.html", carrinho=carrinho)


@app.route("/pagamento/pendente")
def pagamento_pendente():
    payment_id = request.args.get("payment_id") or request.args.get("collection_id")
    carrinho_id = request.args.get("external_reference")

    carrinho = None

    if payment_id:
        pagamento = atualizar_carrinho_por_pagamento(payment_id)

        if pagamento and pagamento.get("external_reference"):
            carrinho_id = pagamento.get("external_reference")

    if carrinho_id:
        try:
            carrinho = Carrinho.query.get(int(carrinho_id))
        except ValueError:
            carrinho = None

    if carrinho and carrinho.status == "finalizado":
        return render_template("pagamento_sucesso.html", carrinho=carrinho)

    return render_template("pagamento_pendente.html", carrinho=carrinho)


@app.route("/status-pagamento/<int:id_carrinho>")
def status_pagamento(id_carrinho):
    carrinho = Carrinho.query.get_or_404(id_carrinho)

    return jsonify({
        "status": carrinho.status,
        "status_pagamento": carrinho.status_pagamento
    })


# ----------------- WEBHOOK MERCADO PAGO -----------------
@app.route("/webhook/mercado-pago", methods=["POST"])
def webhook_mercado_pago():
    dados = request.get_json(silent=True) or {}

    tipo = (
        dados.get("type")
        or request.args.get("type")
        or request.args.get("topic")
    )

    pagamento_id = None

    if dados.get("data"):
        pagamento_id = dados["data"].get("id")

    if not pagamento_id:
        pagamento_id = request.args.get("data.id")

    if not pagamento_id:
        pagamento_id = request.args.get("id")

    print("WEBHOOK RECEBIDO:")
    print("Tipo:", tipo)
    print("Pagamento ID:", pagamento_id)

    if tipo == "merchant_order":
        return "", 200

    if tipo not in ["payment", "payments"]:
        return "", 200

    if not pagamento_id:
        return "", 200

    atualizar_carrinho_por_pagamento(pagamento_id)

    return "", 200


# ----------------- PRODUTO DESTAQUE / STATUS -----------------
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