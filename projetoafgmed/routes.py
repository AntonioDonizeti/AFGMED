from projetoafgmed import app, database, bcrypt
from projetoafgmed.models import Usuario, Medico, Produto, Carrinho, ItemCarrinho, Consulta, Entrega, PerfilUsuario, Pedido, ItemPedido
from projetoafgmed.forms import FormProduto, FormCriarConta, FormLogin, FormMedico
from flask import render_template, redirect, url_for, flash, current_app, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import func
import mercadopago
import os




# ----------------- CONFIGURAÇÕES -----------------
SENHA_PADRAO_MEDICO = "123456"


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


def montar_resposta_carrinho(carrinho):
    itens = carrinho.itens if carrinho else []

    return {
        "sucesso": True,
        "carrinho_id": carrinho.id if carrinho else None,
        "quantidade": sum(item.quantidade for item in itens),
        "total": sum(item.quantidade * item.preco_unitario for item in itens),
        "itens": [
            {
                "id": item.id,
                "produto": item.produto.nome,
                "quantidade": item.quantidade,
                "preco_unitario": float(item.preco_unitario),
                "subtotal": float(item.quantidade * item.preco_unitario),
                "estoque": item.produto.estoque
            }
            for item in itens
        ]
    }


# ----------------- FUNÇÕES DE PEDIDO -----------------
def calcular_total_carrinho(carrinho):
    if not carrinho:
        return 0

    return sum(item.quantidade * item.preco_unitario for item in carrinho.itens)


def criar_ou_atualizar_pedido(carrinho, endereco, cidade, estado, cep):
    total_produtos = calcular_total_carrinho(carrinho)
    total_entrega = 0
    total = total_produtos + total_entrega

    pedido = Pedido.query.filter_by(id_carrinho=carrinho.id).first()

    if not pedido:
        pedido = Pedido(
            id_usuario=carrinho.id_usuario,
            id_carrinho=carrinho.id,
            status="aguardando_pagamento",
            status_pagamento="pending",
            endereco=endereco,
            cidade=cidade,
            estado=estado,
            cep=cep,
            total_produtos=total_produtos,
            total_entrega=total_entrega,
            total=total
        )

        database.session.add(pedido)
        database.session.flush()
    else:
        pedido.endereco = endereco
        pedido.cidade = cidade
        pedido.estado = estado
        pedido.cep = cep
        pedido.total_produtos = total_produtos
        pedido.total_entrega = total_entrega
        pedido.total = total

    ItemPedido.query.filter_by(id_pedido=pedido.id).delete()
    database.session.flush()

    for item in carrinho.itens:
        item_pedido = ItemPedido(
            id_pedido=pedido.id,
            id_produto=item.produto.id,
            nome_produto=item.produto.nome,
            descricao_produto=item.produto.descricao,
            foto_produto=item.produto.foto,
            quantidade=item.quantidade,
            preco_unitario=item.preco_unitario,
            subtotal=item.quantidade * item.preco_unitario
        )

        database.session.add(item_pedido)

    return pedido


def status_visual_pedido(pedido):
    status_pagamento = (pedido.status_pagamento or "").lower()

    if pedido.status == "pago" or status_pagamento == "approved":
        return {
            "classe": "bg-success",
            "icone": "bi-check-circle",
            "texto": "Pagamento aprovado",
            "descricao": "Pedido confirmado e em preparação."
        }

    if pedido.status == "aguardando_pagamento" or status_pagamento in ["pending", "pendente", "in_process"]:
        return {
            "classe": "bg-warning text-dark",
            "icone": "bi-clock-history",
            "texto": "Aguardando pagamento",
            "descricao": "O pagamento ainda está pendente de confirmação."
        }

    if pedido.status in ["falha", "cancelado"] or status_pagamento in ["rejected", "cancelled"]:
        return {
            "classe": "bg-danger",
            "icone": "bi-x-circle",
            "texto": "Pagamento não aprovado",
            "descricao": "O pagamento não foi concluído."
        }

    return {
        "classe": "bg-secondary",
        "icone": "bi-info-circle",
        "texto": "Status em análise",
        "descricao": "Estamos verificando o status do pedido."
    }


def obter_pedido_por_referencia(external_reference):
    if not external_reference:
        return None

    external_reference = str(external_reference)

    if external_reference.startswith("pedido:"):
        try:
            pedido_id = int(external_reference.replace("pedido:", ""))
            return Pedido.query.get(pedido_id)
        except ValueError:
            return None

    try:
        carrinho_id = int(external_reference)
        return Pedido.query.filter_by(id_carrinho=carrinho_id).first()
    except ValueError:
        return None


# ----------------- FUNÇÕES DE MÉDICO -----------------
def sincronizar_usuario_medico(medico):
    email_medico = (medico.email or "").strip().lower()

    if not email_medico:
        return None, "Informe um e-mail para o médico."

    usuario_com_email = Usuario.query.filter_by(email=email_medico).first()
    usuario_vinculado = Usuario.query.filter_by(id_medico=medico.id).first()

    if usuario_com_email and usuario_com_email.id_medico and usuario_com_email.id_medico != medico.id:
        return None, "Este e-mail já está vinculado a outro médico."

    if usuario_vinculado and usuario_vinculado.email != email_medico:
        email_em_uso = Usuario.query.filter_by(email=email_medico).first()

        if email_em_uso and email_em_uso.id != usuario_vinculado.id:
            return None, "Este e-mail já está sendo usado por outro usuário."

        usuario = usuario_vinculado
        usuario.email = email_medico

    elif usuario_com_email:
        usuario = usuario_com_email

    else:
        senha_hash = bcrypt.generate_password_hash(SENHA_PADRAO_MEDICO).decode("utf-8")

        usuario = Usuario(
            nome=medico.nome,
            sobrenome=medico.sobrenome,
            email=email_medico,
            senha=senha_hash,
            is_medico=True,
            id_medico=medico.id
        )

        database.session.add(usuario)

    usuario.nome = medico.nome
    usuario.sobrenome = medico.sobrenome
    usuario.is_medico = True
    usuario.id_medico = medico.id

    return usuario, None


def medico_logado():
    if not getattr(current_user, "is_medico", False):
        return None

    if not current_user.id_medico:
        return None

    return Medico.query.get(current_user.id_medico)


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


# ----------------- PERFIL -----------------
@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    usuario = current_user
    perfil_usuario = usuario.perfil or PerfilUsuario(usuario=usuario)

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
            email_novo = email_novo.strip().lower()

            email_em_uso = Usuario.query.filter(
                Usuario.email == email_novo,
                Usuario.id != current_user.id
            ).first()

            if email_em_uso:
                flash("Este e-mail já está em uso.", "danger")
                return redirect(url_for("perfil"))

            usuario.email = email_novo

        perfil_usuario.endereco = request.form.get("endereco")
        perfil_usuario.cidade = request.form.get("cidade")
        perfil_usuario.estado = request.form.get("estado")
        perfil_usuario.cep = request.form.get("cep")

        database.session.add(usuario)
        database.session.add(perfil_usuario)
        database.session.commit()

        flash("Perfil atualizado com sucesso!", "success")
        return redirect(url_for("perfil"))

    return render_template("perfil.html", usuario=usuario, perfil=perfil_usuario)


# ----------------- MÉDICOS -----------------
@app.route("/medicos")
@login_required
def medicos():
    if getattr(current_user, "is_medico", False) and not getattr(current_user, "is_admin", False):
        medico = medico_logado()

        if not medico:
            flash("Seu usuário médico ainda não está vinculado a um cadastro médico.", "warning")
            return render_template("consultas_medico.html", medico=None, consultas=[])

        consultas_medico = Consulta.query.filter_by(
            medico_id=medico.id
        ).order_by(
            Consulta.data.asc(),
            Consulta.horario.asc()
        ).all()

        return render_template(
            "consultas_medico.html",
            medico=medico,
            consultas=consultas_medico
        )

    return render_template("medicos.html", medicos=Medico.query.all())


@app.route("/cadastro-medico", methods=["GET", "POST"])
@login_required
def cadastro_medico():
    if not getattr(current_user, "is_admin", False):
        flash("Apenas administradores podem acessar esta página.", "warning")
        return redirect(url_for("homepage"))

    form = FormMedico()

    if form.validate_on_submit():
        email_medico = form.email.data.strip().lower()

        medico_existente = Medico.query.filter(
            func.lower(Medico.email) == email_medico
        ).first()

        if medico_existente:
            flash("Já existe um médico cadastrado com este e-mail.", "danger")
            return redirect(url_for("cadastro_medico"))

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
            sobrenome=form.sobrenome.data,
            especialidade=form.especialidade.data,
            email=email_medico,
            telefone=form.telefone.data,
            foto=nome_arquivo
        )

        database.session.add(medico)
        database.session.flush()

        usuario_medico, erro_usuario = sincronizar_usuario_medico(medico)

        if erro_usuario:
            database.session.rollback()
            flash(erro_usuario, "danger")
            return redirect(url_for("cadastro_medico"))

        database.session.commit()

        flash(
            "Médico cadastrado com sucesso! Usuário médico criado/vinculado com senha padrão 123456.",
            "success"
        )

        return redirect(url_for("medicos"))

    return render_template("cadastro_medico.html", form=form, medico=None)


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
        form.sobrenome.data = medico.sobrenome
        form.especialidade.data = medico.especialidade
        form.email.data = medico.email
        form.telefone.data = medico.telefone

    if form.validate_on_submit():
        email_medico = form.email.data.strip().lower()

        medico_com_email = Medico.query.filter(
            func.lower(Medico.email) == email_medico,
            Medico.id != medico.id
        ).first()

        if medico_com_email:
            flash("Já existe outro médico cadastrado com este e-mail.", "danger")
            return redirect(url_for("editar_medico", id_medico=medico.id))

        medico.nome = form.nome.data
        medico.sobrenome = form.sobrenome.data
        medico.especialidade = form.especialidade.data
        medico.email = email_medico
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

        usuario_medico, erro_usuario = sincronizar_usuario_medico(medico)

        if erro_usuario:
            database.session.rollback()
            flash(erro_usuario, "danger")
            return redirect(url_for("editar_medico", id_medico=medico.id))

        database.session.commit()

        flash("Médico atualizado com sucesso! Usuário médico sincronizado.", "success")
        return redirect(url_for("medicos"))

    return render_template("cadastro_medico.html", form=form, medico=medico)


@app.route("/remover-medico/<int:id_medico>", methods=["POST"])
@login_required
def remover_medico(id_medico):
    if not getattr(current_user, "is_admin", False):
        flash("Apenas administradores podem acessar.", "warning")
        return redirect(url_for("homepage"))

    medico = Medico.query.get_or_404(id_medico)

    usuario_medico = Usuario.query.filter_by(id_medico=medico.id).first()

    Consulta.query.filter_by(medico_id=id_medico).delete()

    if usuario_medico:
        usuario_medico.is_medico = False
        usuario_medico.id_medico = None

    database.session.delete(medico)
    database.session.commit()

    flash("Médico removido com sucesso! O usuário vinculado deixou de ser médico.", "success")
    return redirect(url_for("medicos"))


# ----------------- CONSULTAS -----------------
@app.route("/consultas/<int:medico_id>", methods=["GET", "POST"])
@login_required
def consultas(medico_id):
    if getattr(current_user, "is_medico", False) and not getattr(current_user, "is_admin", False):
        flash("Usuários médicos não podem marcar consultas como pacientes.", "warning")
        return redirect(url_for("medicos"))

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

    if data_obj < datetime.today().date():
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
    consultas_usuario = Consulta.query.filter_by(usuario_id=current_user.id) \
        .order_by(Consulta.data.asc(), Consulta.horario.asc()) \
        .all()

    return render_template("meus_agendamentos.html", consultas=consultas_usuario)


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


# ----------------- CARRINHO -----------------
@app.route("/adicionar-carrinho/<int:id_produto>", methods=["POST"])
@login_required
def adicionar_carrinho(id_produto):
    if getattr(current_user, "is_medico", False) and not getattr(current_user, "is_admin", False):
        flash("Usuários médicos não podem comprar produtos como pacientes.", "warning")
        return redirect(url_for("homepage"))

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
    carrinho = item.carrinho
    id_carrinho = carrinho.id

    if carrinho.id_usuario != current_user.id:
        return jsonify({
            "sucesso": False,
            "mensagem": "Você não pode alterar este item."
        }), 403

    if carrinho.status != "ativo":
        return jsonify({
            "sucesso": False,
            "mensagem": "Este carrinho já está em pagamento e não pode ser alterado."
        }), 400

    produto = Produto.query.get_or_404(item.id_produto)

    if acao == "aumentar":
        if produto.estoque > 0:
            item.quantidade += 1
            produto.estoque -= 1
        else:
            return jsonify({
                "sucesso": False,
                "mensagem": "Produto sem estoque."
            }), 400

    elif acao == "diminuir":
        if item.quantidade > 1:
            item.quantidade -= 1
            produto.estoque += 1
        else:
            produto.estoque += item.quantidade
            database.session.delete(item)

    else:
        return jsonify({
            "sucesso": False,
            "mensagem": "Ação inválida."
        }), 400

    database.session.commit()

    carrinho_atualizado = Carrinho.query.get(id_carrinho)
    database.session.expire(carrinho_atualizado, ["itens"])

    return jsonify(montar_resposta_carrinho(carrinho_atualizado))


@app.route("/remover-item/<int:id_item>", methods=["POST"])
@login_required
def remover_item(id_item):
    item = ItemCarrinho.query.get_or_404(id_item)
    carrinho = item.carrinho
    id_carrinho = carrinho.id

    if carrinho.id_usuario != current_user.id:
        return jsonify({
            "sucesso": False,
            "mensagem": "Você não pode remover este item."
        }), 403

    if carrinho.status != "ativo":
        return jsonify({
            "sucesso": False,
            "mensagem": "Este carrinho já está em pagamento e não pode ser alterado."
        }), 400

    produto = Produto.query.get(item.id_produto)

    if produto:
        produto.estoque += item.quantidade

    database.session.delete(item)
    database.session.commit()

    carrinho_atualizado = Carrinho.query.get(id_carrinho)
    database.session.expire(carrinho_atualizado, ["itens"])

    return jsonify(montar_resposta_carrinho(carrinho_atualizado))


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
def criar_preferencia_mercado_pago(pedido):
    access_token = current_app.config.get("MERCADO_PAGO_ACCESS_TOKEN")
    app_base_url = current_app.config.get("APP_BASE_URL")

    if not access_token:
        return None, "Access Token do Mercado Pago não configurado."

    if not app_base_url:
        return None, "APP_BASE_URL não configurada no .env."

    if not pedido.itens:
        return None, "Pedido sem itens."

    sdk = mercadopago.SDK(access_token)

    itens_mp = []

    for item in pedido.itens:
        itens_mp.append({
            "title": item.nome_produto,
            "description": item.descricao_produto or "Produto AFGMED",
            "quantity": int(item.quantidade),
            "currency_id": "BRL",
            "unit_price": float(item.preco_unitario)
        })

    preference_data = {
        "items": itens_mp,

        "external_reference": f"pedido:{pedido.id}",

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
    print("REFERÊNCIA:", pagamento.get("external_reference"))

    external_reference = pagamento.get("external_reference")
    status_pagamento = pagamento.get("status", "pending")

    pedido = obter_pedido_por_referencia(external_reference)
    carrinho = pedido.carrinho if pedido else None

    if not pedido:
        return pagamento

    pedido.mercado_pago_payment_id = str(pagamento_id)
    pedido.status_pagamento = status_pagamento

    if carrinho:
        carrinho.mercado_pago_payment_id = str(pagamento_id)
        carrinho.status_pagamento = status_pagamento

    if status_pagamento == "approved":
        pedido.status = "pago"

        if carrinho:
            carrinho.status = "finalizado"
            carrinho.ativo = False

    elif status_pagamento in ["rejected", "cancelled"]:
        pedido.status = "falha"

        if carrinho:
            carrinho.status = "ativo"
            carrinho.status_pagamento = status_pagamento
            carrinho.mercado_pago_preference_id = None
            carrinho.mercado_pago_payment_id = None
            carrinho.mercado_pago_init_point = None

    elif status_pagamento in ["pending", "in_process"]:
        pedido.status = "aguardando_pagamento"

        if carrinho:
            carrinho.status = "aguardando_pagamento"

    database.session.commit()

    return pagamento


# ----------------- ENTREGA -----------------
@app.route("/entrega/<int:id_carrinho>", methods=["GET", "POST"])
@login_required
def entrega(id_carrinho):
    carrinho = Carrinho.query.get_or_404(id_carrinho)
    usuario = current_user
    perfil_usuario = usuario.perfil or PerfilUsuario(usuario=usuario)

    if carrinho.id_usuario != current_user.id:
        return redirect(url_for("homepage"))

    if carrinho.status not in ["ativo", "aguardando_pagamento"]:
        return redirect(url_for("homepage"))

    if request.method == "POST":
        endereco = request.form.get("endereco") or perfil_usuario.endereco
        cidade = request.form.get("cidade") or perfil_usuario.cidade
        estado = request.form.get("estado") or perfil_usuario.estado
        cep = request.form.get("cep") or perfil_usuario.cep

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

        perfil_usuario.endereco = endereco
        perfil_usuario.cidade = cidade
        perfil_usuario.estado = estado
        perfil_usuario.cep = cep

        database.session.add(perfil_usuario)

        pedido = criar_ou_atualizar_pedido(
            carrinho=carrinho,
            endereco=endereco,
            cidade=cidade,
            estado=estado,
            cep=cep
        )

        database.session.commit()

        if (
            pedido.status == "aguardando_pagamento"
            and pedido.status_pagamento in ["pending", "pendente", "in_process"]
            and pedido.mercado_pago_preference_id
            and pedido.mercado_pago_init_point
        ):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "sucesso": True,
                    "redirect_url": pedido.mercado_pago_init_point
                })

            return redirect(pedido.mercado_pago_init_point)

        carrinho.status = "aguardando_pagamento"
        carrinho.status_pagamento = "pending"

        pedido.status = "aguardando_pagamento"
        pedido.status_pagamento = "pending"

        database.session.commit()

        preference, erro_mp = criar_preferencia_mercado_pago(pedido)

        if not preference:
            carrinho.status = "ativo"
            carrinho.status_pagamento = "pendente"

            pedido.status = "falha"
            pedido.status_pagamento = "rejected"

            database.session.commit()

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "sucesso": False,
                    "mensagem": f"Erro Mercado Pago: {erro_mp}"
                })

            flash(f"Erro Mercado Pago: {erro_mp}", "danger")
            return redirect(url_for("entrega", id_carrinho=carrinho.id))

        link_pagamento = preference.get("init_point") or preference.get("sandbox_init_point")

        if not link_pagamento:
            carrinho.status = "ativo"
            carrinho.status_pagamento = "pendente"

            pedido.status = "falha"
            pedido.status_pagamento = "rejected"

            database.session.commit()

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "sucesso": False,
                    "mensagem": "Mercado Pago não retornou link de pagamento."
                })

            flash("Mercado Pago não retornou link de pagamento.", "danger")
            return redirect(url_for("entrega", id_carrinho=carrinho.id))

        pedido.mercado_pago_preference_id = preference.get("id")
        pedido.mercado_pago_init_point = link_pagamento

        carrinho.mercado_pago_preference_id = preference.get("id")
        carrinho.mercado_pago_init_point = link_pagamento

        database.session.commit()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "sucesso": True,
                "redirect_url": link_pagamento
            })

        return redirect(link_pagamento)

    return render_template(
        "entrega.html",
        carrinho=carrinho,
        perfil=perfil_usuario,
        google_maps_api_key=current_app.config.get("GOOGLE_MAPS_API_KEY")
    )


# ----------------- RETORNO DO PAGAMENTO -----------------
@app.route("/pagamento/sucesso")
def pagamento_sucesso():
    payment_id = request.args.get("payment_id") or request.args.get("collection_id")
    external_reference = request.args.get("external_reference")

    pedido = None

    if payment_id:
        pagamento = atualizar_carrinho_por_pagamento(payment_id)

        if pagamento and pagamento.get("external_reference"):
            external_reference = pagamento.get("external_reference")

    if external_reference:
        pedido = obter_pedido_por_referencia(external_reference)

    if pedido and pedido.status == "pago":
        return render_template("pagamento_sucesso.html", pedido=pedido, carrinho=pedido.carrinho)

    return render_template("pagamento_pendente.html", pedido=pedido, carrinho=pedido.carrinho if pedido else None)


@app.route("/pagamento/falha")
def pagamento_falha():
    external_reference = request.args.get("external_reference")

    pedido = obter_pedido_por_referencia(external_reference)
    carrinho = pedido.carrinho if pedido else None

    if pedido:
        pedido.status_pagamento = "rejected"
        pedido.status = "falha"

    if carrinho:
        carrinho.status_pagamento = "falha"
        carrinho.status = "ativo"
        carrinho.mercado_pago_preference_id = None
        carrinho.mercado_pago_payment_id = None
        carrinho.mercado_pago_init_point = None

    database.session.commit()

    return render_template("pagamento_falha.html", pedido=pedido, carrinho=carrinho)


@app.route("/pagamento/pendente")
def pagamento_pendente():
    payment_id = request.args.get("payment_id") or request.args.get("collection_id")
    external_reference = request.args.get("external_reference")

    pedido = None

    if payment_id:
        pagamento = atualizar_carrinho_por_pagamento(payment_id)

        if pagamento and pagamento.get("external_reference"):
            external_reference = pagamento.get("external_reference")

    if external_reference:
        pedido = obter_pedido_por_referencia(external_reference)

    if pedido and pedido.status == "pago":
        return render_template("pagamento_sucesso.html", pedido=pedido, carrinho=pedido.carrinho)

    return render_template("pagamento_pendente.html", pedido=pedido, carrinho=pedido.carrinho if pedido else None)


@app.route("/status-pagamento/<int:id_carrinho>")
@login_required
def status_pagamento(id_carrinho):
    carrinho = Carrinho.query.get_or_404(id_carrinho)

    if carrinho.id_usuario != current_user.id and not current_user.is_admin:
        return jsonify({
            "sucesso": False,
            "mensagem": "Você não pode acessar este pedido."
        }), 403

    pedido = Pedido.query.filter_by(id_carrinho=carrinho.id).first()

    if pedido:
        status = status_visual_pedido(pedido)

        return jsonify({
            "sucesso": True,
            "status": carrinho.status,
            "status_pedido": pedido.status,
            "status_pagamento": pedido.status_pagamento,
            "classe": status["classe"],
            "icone": status["icone"],
            "texto": status["texto"],
            "descricao": status["descricao"]
        })

    return jsonify({
        "sucesso": True,
        "status": carrinho.status,
        "status_pedido": None,
        "status_pagamento": carrinho.status_pagamento,
        "classe": "bg-secondary",
        "icone": "bi-info-circle",
        "texto": "Status em análise",
        "descricao": "Estamos verificando o status do pedido."
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


# ----------------- MINHAS COMPRAS -----------------
@app.route("/minhas-compras")
@login_required
def meus_pedidos():
    pedidos = Pedido.query.filter_by(
        id_usuario=current_user.id
    ).order_by(
        Pedido.data_criacao.desc()
    ).all()

    pedidos_formatados = []

    for pedido in pedidos:
        pedidos_formatados.append({
            "pedido": pedido,
            "status": status_visual_pedido(pedido)
        })

    return render_template(
        "meus_pedidos.html",
        pedidos=pedidos_formatados
    )