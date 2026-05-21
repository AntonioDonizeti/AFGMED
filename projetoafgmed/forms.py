from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, EmailField, FloatField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo
from flask_wtf.file import FileField, FileAllowed

class FormCriarConta(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired()])
    sobrenome = StringField("Sobrenome", validators=[DataRequired()])
    email = EmailField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField("Senha", validators=[DataRequired()])
    confirmacao_senha = PasswordField("Confirme a Senha", validators=[DataRequired(), EqualTo("senha")])
    botao_confirmacao = SubmitField("Cadastrar")

class FormLogin(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField("Senha", validators=[DataRequired()])
    botao_confirmacao = SubmitField("Entrar")


class FormMedico(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired()])
    especialidade = StringField("Especialidade", validators=[DataRequired()])
    email = StringField("Email")
    telefone = StringField("Telefone")
    foto = FileField(
        "Foto",
        validators=[FileAllowed(['jpg','jpeg','png'], "Apenas imagens são permitidas!")]
    )
    botao_confirmacao = SubmitField("Cadastrar")


class FormProduto(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired()])
    descricao = StringField("Descrição")
    preco = FloatField("Preço", validators=[DataRequired()])
    estoque = IntegerField("Estoque", default=0, validators=[DataRequired()])
    foto = FileField("Foto", validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Apenas imagens são permitidas!')])
    botao_confirmacao = SubmitField("Cadastrar")