from flask_login import UserMixin
from datetime import datetime
from projetoafgmed import database, login_manager
from wtforms import StringField, SubmitField, FloatField, IntegerField
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired
from flask_wtf import FlaskForm

@login_manager.user_loader
def load_usuario(id_usuario):
    return Usuario.query.get(int(id_usuario))

class Usuario(database.Model, UserMixin):
    id = database.Column(database.Integer, primary_key=True)
    nome = database.Column(database.String, nullable=False)
    sobrenome = database.Column(database.String, nullable=False)
    email = database.Column(database.String, nullable=False, unique=True)
    senha = database.Column(database.String, nullable=False)
    is_admin = database.Column(database.Boolean, default=False)

class Medico(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    nome = database.Column(database.String, nullable=False)
    especialidade = database.Column(database.String, nullable=False)
    email = database.Column(database.String)
    telefone = database.Column(database.String)
    foto = database.Column(database.String, default="default.jpg")
    data_criacao = database.Column(database.DateTime, nullable=False, default=datetime.utcnow)

class Consulta(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    medico_id = database.Column(
        database.Integer,
        database.ForeignKey('medico.id'),  # usa o nome correto da tabela de médicos
        nullable=False
    )
    paciente_nome = database.Column(database.String(100), nullable=False)
    horario = database.Column(database.String(20), nullable=False)
    data = database.Column(database.Date, default=datetime.today)

    # Relacionamento opcional para facilitar consultas
    medico = database.relationship('Medico', backref=database.backref('consultas', lazy=True))

    def __repr__(self):
        return f'<Consulta {self.paciente_nome} - {self.horario}>'


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
    id_usuario = database.Column(database.Integer, database.ForeignKey('usuario.id'), nullable=False)
    data_criacao = database.Column(database.DateTime, default=datetime.utcnow)
    status = database.Column(database.String, default='ativo')  # ativo ou finalizado
    ativo = database.Column(database.Boolean, default=True, nullable=False)  # NOVO CAMPO

    usuario = database.relationship('Usuario', backref=database.backref('carrinho', uselist=False))
    itens = database.relationship('ItemCarrinho', backref='carrinho', lazy=True)

class ItemCarrinho(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    id_carrinho = database.Column(database.Integer, database.ForeignKey('carrinho.id'), nullable=False)
    id_produto = database.Column(database.Integer, database.ForeignKey('produto.id'), nullable=False)
    quantidade = database.Column(database.Integer, default=1)
    preco_unitario = database.Column(database.Float, nullable=False)

    produto = database.relationship('Produto')

class Entrega(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    id_carrinho = database.Column(database.Integer, database.ForeignKey('carrinho.id'), nullable=False)
    endereco = database.Column(database.String(200), nullable=False)
    cidade = database.Column(database.String(50), nullable=False)
    estado = database.Column(database.String(50), nullable=False)
    cep = database.Column(database.String(20), nullable=False)
    telefone = database.Column(database.String(20), nullable=False)
    data_criacao = database.Column(database.DateTime, default=datetime.utcnow)

    carrinho = database.relationship('Carrinho', backref=database.backref('entrega', uselist=False))

    def __repr__(self):
        return f'<Entrega {self.endereco} - {self.cidade}>'