from flask import render_template

from projetoafgmed import app
from projetoafgmed.models import Produto


@app.route("/")
def homepage():
    produtos_destaque = Produto.query.filter_by(
        ativo=True,
        destaque_home=True
    ).limit(4).all()

    return render_template("homepage.html", produtos=produtos_destaque)