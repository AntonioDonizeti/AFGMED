from projetoafgmed import app, database

with app.app_context():
    database.create_all()
    print("Banco de dados criado com sucesso!")