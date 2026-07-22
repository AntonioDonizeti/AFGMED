from flask_login import UserMixin
from datetime import datetime
from projetoafgmed import database, login_manager


@login_manager.user_loader
def load_usuario(id_usuario):
    return Usuario.query.get(int(id_usuario))


class Usuario(database.Model, UserMixin):
    id = database.Column(database.Integer, primary_key=True)
    nome = database.Column(database.String, nullable=False)
    sobrenome = database.Column(database.String, nullable=False)
    email = database.Column(database.String, nullable=False, unique=True)
    senha = database.Column(database.String, nullable=False)
    foto = database.Column(database.String(200), nullable=True, default="usuario_padrao.jpg")

    is_admin = database.Column(database.Boolean, default=False)
    is_medico = database.Column(database.Boolean, default=False, nullable=False)
    id_medico = database.Column(database.Integer, database.ForeignKey("medico.id"), nullable=True)

    perfil = database.relationship("PerfilUsuario", backref="usuario", uselist=False)
    carrinho = database.relationship("Carrinho", backref="usuario", uselist=False)
    consultas = database.relationship("Consulta", backref="usuario", lazy=True)
    pedidos = database.relationship("Pedido", backref="usuario", lazy=True)

    medico = database.relationship(
        "Medico",
        backref=database.backref("usuario_acesso", uselist=False),
        foreign_keys=[id_medico]
    )


class PerfilUsuario(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    id_usuario = database.Column(database.Integer, database.ForeignKey("usuario.id"), nullable=False)

    telefone = database.Column(database.String(20), nullable=True)
    cpf = database.Column(database.String(20), nullable=True, unique=True)
    data_nascimento = database.Column(database.Date, nullable=True)

    endereco = database.Column(database.String(200))
    cidade = database.Column(database.String(100))
    estado = database.Column(database.String(50))
    cep = database.Column(database.String(20))


class Medico(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    nome = database.Column(database.String, nullable=False)
    sobrenome = database.Column(database.String, nullable=False, default="AFGMED")
    especialidade = database.Column(database.String, nullable=False)
    email = database.Column(database.String)
    telefone = database.Column(database.String)
    foto = database.Column(database.String, default="default.jpg")
    data_criacao = database.Column(database.DateTime, nullable=False, default=datetime.utcnow)


class Consulta(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    medico_id = database.Column(database.Integer, database.ForeignKey("medico.id"), nullable=False)
    usuario_id = database.Column(database.Integer, database.ForeignKey("usuario.id"), nullable=False)
    horario = database.Column(database.String(20), nullable=False)
    data = database.Column(database.Date, default=datetime.today)

    # Status possíveis: agendada, cancelada, concluida
    status = database.Column(database.String(20), nullable=False, default="agendada")

    medico = database.relationship("Medico", backref=database.backref("consultas", lazy=True))

    def __repr__(self):
        return f"<Consulta {self.usuario.nome} - {self.horario} - {self.status}>"

    def __repr__(self):
        return f"<Consulta {self.usuario.nome} - {self.horario}>"


class Produto(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    nome = database.Column(database.String, nullable=False)
    descricao = database.Column(database.String)
    preco = database.Column(database.Float, nullable=False)
    estoque = database.Column(database.Integer, default=0)
    foto = database.Column(database.String, default="default.jpg")
    ativo = database.Column(database.Boolean, default=True, nullable=False)
    destaque_home = database.Column(database.Boolean, default=False, nullable=False)
    data_criacao = database.Column(database.DateTime, nullable=False, default=datetime.utcnow)


class Carrinho(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    id_usuario = database.Column(database.Integer, database.ForeignKey("usuario.id"), nullable=False)
    data_criacao = database.Column(database.DateTime, default=datetime.utcnow)

    status = database.Column(database.String, default="ativo")
    ativo = database.Column(database.Boolean, default=True, nullable=False)

    status_pagamento = database.Column(database.String(30), default="pendente")
    mercado_pago_preference_id = database.Column(database.String(120), nullable=True)
    mercado_pago_payment_id = database.Column(database.String(120), nullable=True)
    mercado_pago_init_point = database.Column(database.String(500), nullable=True)

    itens = database.relationship("ItemCarrinho", backref="carrinho", lazy=True)
    entrega = database.relationship("Entrega", backref="carrinho", uselist=False)
    pedido = database.relationship("Pedido", backref="carrinho", uselist=False)


class ItemCarrinho(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    id_carrinho = database.Column(database.Integer, database.ForeignKey("carrinho.id"), nullable=False)
    id_produto = database.Column(database.Integer, database.ForeignKey("produto.id"), nullable=False)
    quantidade = database.Column(database.Integer, default=1)
    preco_unitario = database.Column(database.Float, nullable=False)

    produto = database.relationship("Produto")


class Entrega(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    id_carrinho = database.Column(database.Integer, database.ForeignKey("carrinho.id"), nullable=False)
    endereco = database.Column(database.String(200), nullable=False)
    cidade = database.Column(database.String(50), nullable=False)
    estado = database.Column(database.String(50), nullable=False)
    cep = database.Column(database.String(20), nullable=False)
    data_criacao = database.Column(database.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Entrega {self.endereco} - {self.cidade}>"


class Pedido(database.Model):
    id = database.Column(database.Integer, primary_key=True)

    id_usuario = database.Column(database.Integer, database.ForeignKey("usuario.id"), nullable=False)
    id_carrinho = database.Column(database.Integer, database.ForeignKey("carrinho.id"), nullable=False, unique=True)

    status = database.Column(database.String(30), default="aguardando_pagamento", nullable=False)
    status_pagamento = database.Column(database.String(30), default="pending", nullable=False)

    total_produtos = database.Column(database.Float, default=0, nullable=False)
    total_entrega = database.Column(database.Float, default=0, nullable=False)
    total = database.Column(database.Float, default=0, nullable=False)

    endereco = database.Column(database.String(200), nullable=False)
    cidade = database.Column(database.String(100), nullable=False)
    estado = database.Column(database.String(50), nullable=False)
    cep = database.Column(database.String(20), nullable=False)

    mercado_pago_preference_id = database.Column(database.String(120), nullable=True)
    mercado_pago_payment_id = database.Column(database.String(120), nullable=True)
    mercado_pago_init_point = database.Column(database.String(500), nullable=True)

    data_criacao = database.Column(database.DateTime, default=datetime.utcnow)
    data_atualizacao = database.Column(database.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    itens = database.relationship(
        "ItemPedido",
        backref="pedido",
        lazy=True,
        cascade="all, delete-orphan"
    )


class ItemPedido(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    id_pedido = database.Column(database.Integer, database.ForeignKey("pedido.id"), nullable=False)
    id_produto = database.Column(database.Integer, database.ForeignKey("produto.id"), nullable=True)

    nome_produto = database.Column(database.String, nullable=False)
    descricao_produto = database.Column(database.String)
    foto_produto = database.Column(database.String)

    quantidade = database.Column(database.Integer, nullable=False)
    preco_unitario = database.Column(database.Float, nullable=False)
    subtotal = database.Column(database.Float, nullable=False)

    produto = database.relationship("Produto")