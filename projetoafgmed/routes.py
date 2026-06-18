from projetoafgmed import app, database, bcrypt
from projetoafgmed.models import Usuario, Medico, Produto, Carrinho, ItemCarrinho, Consulta, Entrega, PerfilUsuario
from projetoafgmed.forms import FormProduto, FormCriarConta, FormLogin, FormMedico
from flask import render_template, redirect, url_for, flash, current_app, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os


# --- Context processor para carrinho global ---
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
    produtos_destaque = Produto.query.filter_by(ativo=True, destaque_home=True).limit(4).all()
    return render_template("homepage.html", produtos=produtos_destaque)

# ----------------- USUÁRIOS -----------------
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

@app.route("/login", methods=["GET","POST"])
def login():
    form = FormLogin()
    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(email=form.email.data).first()
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


# Perfil do usuário
@app.route("/perfil", methods=["GET","POST"])
@login_required
def perfil():
    usuario = current_user
    perfil = usuario.perfil or PerfilUsuario(usuario=usuario)

    if request.method == "POST":
        # Foto
        if "foto" in request.files and request.files["foto"].filename:
            arquivo = request.files["foto"]
            nome_foto = secure_filename(arquivo.filename)
            caminho = os.path.join(app.root_path, "static/fotos_perfil", nome_foto)
            arquivo.save(caminho)
            usuario.foto = nome_foto

        # Endereço
        perfil.endereco = request.form.get("endereco")
        perfil.cidade = request.form.get("cidade")
        perfil.estado = request.form.get("estado")
        perfil.cep = request.form.get("cep")

        # Pagamento
        perfil.numero_cartao = request.form.get("numero_cartao")
        perfil.nome_cartao = request.form.get("nome_cartao")
        perfil.validade_cartao = request.form.get("validade_cartao")
        perfil.cvv = request.form.get("cvv")

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

@app.route("/cadastro-medico", methods=["GET","POST"])
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

# ----------------- CONSULTAS -----------------
# ----------------- CONSULTAS -----------------
@app.route('/consultas/<int:medico_id>', methods=['GET', 'POST'])
@login_required
def consultas(medico_id):
    medico = Medico.query.get_or_404(medico_id)
    horarios = ['09:00', '10:00', '11:00', '14:00', '15:00', '16:00']

    if request.method == 'POST':
        horario = request.form.get('horario')
        data_consulta = request.form.get('data_consulta')

        if not horario or not data_consulta:
            flash("Escolha data e horário para continuar.", "warning")
            return redirect(url_for('consultas', medico_id=medico.id))

        data_obj = datetime.strptime(data_consulta, '%Y-%m-%d').date()

        # Verifica se já existe consulta nesse horário e data
        existente = Consulta.query.filter_by(
            medico_id=medico.id,
            horario=horario,
            data=data_obj
        ).first()

        if existente:
            flash("Horário já reservado para essa data!", "danger")
            return redirect(url_for('consultas', medico_id=medico.id))

        # Cria a nova consulta vinculada ao usuário logado
        nova_consulta = Consulta(
            medico_id=medico.id,
            usuario_id=current_user.id,
            horario=horario,
            data=data_obj
        )
        database.session.add(nova_consulta)
        database.session.commit()
        flash("Consulta agendada com sucesso!", "success")
        return redirect(url_for('meus_agendamentos'))

    consultas_marcadas = Consulta.query.filter_by(medico_id=medico.id).all()
    return render_template('consultas.html', medico=medico, horarios=horarios, consultas=consultas_marcadas)

# ----------------- HORARIOS DISPONIVEIS -----------------
@app.route('/horarios_disponiveis/<int:medico_id>/<data>')
@login_required
def horarios_disponiveis(medico_id, data):
    try:
        data_obj = datetime.strptime(data, '%Y-%m-%d').date()
    except ValueError:
        return jsonify([])

    consultas = Consulta.query.filter_by(medico_id=medico_id, data=data_obj).all()
    horarios_ocupados = [c.horario for c in consultas]
    return jsonify(horarios_ocupados)

# ----------------- MEUS AGENDAMENTOS -----------------
@app.route('/meus_agendamentos')
@login_required
def meus_agendamentos():
    # Busca apenas consultas do usuário logado
    consultas = Consulta.query.filter_by(usuario_id=current_user.id)\
        .order_by(Consulta.data.asc(), Consulta.horario.asc())\
        .all()
    return render_template('meus_agendamentos.html', consultas=consultas)

# ----------------- CANCELAR AGENDAMENTOS -----------------
@app.route('/cancelar_consulta/<int:consulta_id>', methods=['POST'])
@login_required
def cancelar_consulta(consulta_id):
    consulta = Consulta.query.get_or_404(consulta_id)
    if consulta.usuario_id != current_user.id:
        flash('Você não pode cancelar esta consulta.', 'danger')
        return redirect(url_for('meus_agendamentos'))

    database.session.delete(consulta)
    database.session.commit()
    flash('Consulta cancelada com sucesso!', 'success')
    return redirect(url_for('meus_agendamentos'))

# ----------------- EDITAR MÉDICO -----------------
@app.route("/editar-medico/<int:id_medico>", methods=["GET", "POST"])
@login_required
def editar_medico(id_medico):
    if not getattr(current_user, "is_admin", False):
        flash("Apenas administradores podem acessar esta página.", "warning")
        return redirect(url_for("homepage"))

    medico = Medico.query.get_or_404(id_medico)
    form = FormMedico()

    # Preencher formulário com dados existentes
    if request.method == "GET":
        form.nome.data = medico.nome
        form.especialidade.data = medico.especialidade
        form.email.data = medico.email
        form.telefone.data = medico.telefone

    # Atualizar dados ao enviar
    if form.validate_on_submit():
        medico.nome = form.nome.data
        medico.especialidade = form.especialidade.data
        medico.email = form.email.data
        medico.telefone = form.telefone.data

        # Atualizar foto
        if form.foto.data:
            arquivo = form.foto.data
            nome_foto = secure_filename(arquivo.filename)
            caminho = os.path.join(current_app.root_path, 'static/fotos_medicos', nome_foto)
            os.makedirs(os.path.dirname(caminho), exist_ok=True)
            arquivo.save(caminho)
            medico.foto = nome_foto

        database.session.commit()
        flash("Médico atualizado com sucesso!", "success")
        return redirect(url_for("medicos"))

    return render_template("cadastro_medico.html", form=form, medico=medico)

# ----------------- REMOVER MÉDICO -----------------
@app.route("/remover-medico/<int:id_medico>", methods=["POST"])
@login_required
def remover_medico(id_medico):
    if not getattr(current_user, "is_admin", False):
        flash("Apenas administradores podem acessar.", "warning")
        return redirect(url_for("homepage"))

    medico = Medico.query.get_or_404(id_medico)

    # ✅ APAGA AS CONSULTAS PRIMEIRO
    Consulta.query.filter_by(medico_id=id_medico).delete()

    # ✅ AGORA APAGA O MÉDICO
    database.session.delete(medico)
    database.session.commit()

    flash("Médico removido com sucesso!", "success")
    return redirect(url_for("medicos"))


# ----------------- PRODUTOS -----------------
@app.route("/produtos")
@login_required
def produtos():
    return render_template("produtos.html", produtos=Produto.query.all())

@app.route("/cadastro-produto", methods=["GET","POST"])
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
            foto=nome_foto,
            ativo=form.ativo.data,
            destaque_home=form.destaque_home.data
        )
        database.session.add(produto)
        database.session.commit()
        flash("Produto cadastrado com sucesso!", "success")
        return redirect(url_for("produtos"))

    return render_template("cadastro_produto.html", form=form)

@app.route("/editar-produto/<int:id_produto>", methods=["GET","POST"])
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
            caminho = os.path.join(current_app.root_path, 'static/fotos_produtos', nome_foto)
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

    carrinho = Carrinho.query.filter_by(id_usuario=current_user.id, status='ativo').first()
    if not carrinho:
        carrinho = Carrinho(id_usuario=current_user.id)
        database.session.add(carrinho)
        database.session.commit()

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

    if acao == "aumentar" and produto.estoque > 0:
        item.quantidade += 1
        produto.estoque -= 1
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
    produto.estoque += item.quantidade
    database.session.delete(item)
    database.session.commit()
    flash("Item removido do carrinho!", "info")
    return redirect(url_for("ver_carrinho"))

@app.route("/ver-carrinho")
@login_required
def ver_carrinho():
    carrinho = Carrinho.query.filter_by(id_usuario=current_user.id, status='ativo').first()
    itens = carrinho.itens if carrinho else []
    total = sum(item.quantidade * item.preco_unitario for item in itens)
    return render_template("_carrinho_lateral.html", itens_carrinho=itens, total_carrinho=total)

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
# ----------------- ALTERNAR DESTAQUE -----------------
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

# ----------------- DESATIVAR PRODUTO -----------------
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

# ----------------- ATIVAR PRODUTO -----------------
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

# ----------------- ENTREGA -----------------

@app.route("/entrega/<int:id_carrinho>", methods=["GET", "POST"])
@login_required
def entrega(id_carrinho):
    carrinho = Carrinho.query.get_or_404(id_carrinho)
    usuario = current_user
    perfil = usuario.perfil or PerfilUsuario(usuario=usuario)

    # Segurança: impede acessar carrinho de outro usuário
    if carrinho.id_usuario != current_user.id:
        return redirect(url_for("homepage"))

    # Segurança: impede finalizar carrinho já finalizado
    if carrinho.status != "ativo":
        return redirect(url_for("homepage"))

    if request.method == "POST":
        endereco = request.form.get("endereco") or perfil.endereco
        cidade = request.form.get("cidade") or perfil.cidade
        estado = request.form.get("estado") or perfil.estado
        cep = request.form.get("cep") or perfil.cep

        nova_entrega = Entrega(
            id_carrinho=carrinho.id,
            endereco=endereco,
            cidade=cidade,
            estado=estado,
            cep=cep
        )

        database.session.add(perfil)
        database.session.add(nova_entrega)

        carrinho.status = "finalizado"

        database.session.commit()

        # Resposta para o popup estilizado do entrega.html
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "sucesso": True,
                "mensagem": "Compra realizada com sucesso!",
                "redirect_url": url_for("homepage")
            })

        return redirect(url_for("homepage"))

    return render_template(
        "entrega.html",
        carrinho=carrinho,
        perfil=perfil,
        google_maps_api_key=current_app.config.get("GOOGLE_MAPS_API_KEY")
    )