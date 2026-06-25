from flask import render_template
from flask_login import login_required, current_user

from projetoafgmed import app
from projetoafgmed.models import Pedido
from projetoafgmed.rotas.utils import status_visual_pedido


@app.route("/minhas-compras")
@login_required
def meus_pedidos():
    pedidos = Pedido.query.filter_by(
        id_usuario=current_user.id
    ).order_by(
        Pedido.data_criacao.desc()
    ).all()

    pedidos_formatados = []

    for pedido in pedidos:
        pedidos_formatados.append({
            "pedido": pedido,
            "status": status_visual_pedido(pedido)
        })

    return render_template(
        "meus_pedidos.html",
        pedidos=pedidos_formatados
    )