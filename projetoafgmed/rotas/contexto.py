from flask_login import current_user

from projetoafgmed import app
from projetoafgmed.models import Carrinho


@app.context_processor
def carrinho_global():
    if current_user.is_authenticated:
        carrinho = Carrinho.query.filter_by(
            id_usuario=current_user.id,
            status="ativo"
        ).first()

        itens = carrinho.itens if carrinho else []
        total = sum(item.quantidade * item.preco_unitario for item in itens)
        quantidade = sum(item.quantidade for item in itens)

        return {
            "carrinho": carrinho,
            "itens_carrinho": itens,
            "total_carrinho": total,
            "quantidade_carrinho": quantidade
        }

    return {
        "carrinho": None,
        "itens_carrinho": [],
        "total_carrinho": 0,
        "quantidade_carrinho": 0
    }