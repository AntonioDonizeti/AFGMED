# tornar_admin.py
from projetoafgmed import app, database
from projetoafgmed.models import Usuario

email_usuario = input("Digite o email do usuário que será admin: ")

with app.app_context():
    usuario = Usuario.query.filter_by(email=email_usuario).first()
    if usuario:
        usuario.is_admin = True
        database.session.commit()
        print(f"Usuário {usuario.nome} agora é admin!")
    else:
        print("Usuário não encontrado.")