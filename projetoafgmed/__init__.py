from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = '8bf514e8a329e946306502fa33f3a939'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///afgmed.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['GOOGLE_MAPS_API_KEY'] = os.environ.get('GOOGLE_MAPS_API_KEY', 'AIzaSyC_o4Sx5hv1JCiAWZuKF6qZvJ7RDwqs_do')

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

database = SQLAlchemy(app)
bcrypt = Bcrypt(app)  
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Importa rotas depois para evitar loop
from projetoafgmed import routes