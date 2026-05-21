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

class Produto(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    nome = database.Column(database.String, nullable=False)
    descricao = database.Column(database.String)
    preco = database.Column(database.Float, nullable=False)
    estoque = database.Column(database.Integer, default=0)
    foto = database.Column(database.String, default="default.jpg")


