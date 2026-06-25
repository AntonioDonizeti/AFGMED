from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
import os

# Carrega as variáveis do arquivo .env
load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-dev-afgmed')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///afgmed.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


app.config['GOOGLE_MAPS_API_KEY'] = os.environ.get('GOOGLE_MAPS_API_KEY', '')
app.config['MERCADO_PAGO_ACCESS_TOKEN'] = os.environ.get('MERCADO_PAGO_ACCESS_TOKEN', '')
app.config["APP_BASE_URL"] = os.environ.get("APP_BASE_URL", "")

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

database = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Importa rotas depois para evitar loop
from projetoafgmed.rotas import registrar_rotas
registrar_rotas()