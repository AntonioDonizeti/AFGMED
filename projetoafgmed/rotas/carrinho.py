from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from projetoafgmed import app, database
from projetoafgmed.models import Produto, Carrinho, ItemCarrinho
from projetoafgmed.rotas.utils import montar_resposta_carrinho


@app.route("/adicionar-carrinho/<int:id_produto>", methods=["POST"])
@login_required
def adicionar_carrinho(id_produto):
    if getattr(current_user, "is_medico", False) and not getattr(current_user, "is_admin", False):
        flash("Usuários médicos não podem comprar produtos como pacientes.", "warning")
        return redirect(url_for("homepage"))

    produto = Produto.query.get_or_404(id_produto)

    if not produto.ativo:
        flash("Produto indisponível.", "warning")
        return redirect(request.referrer or url_for("produtos"))

    if produto.estoque <= 0:
        flash("Produto sem estoque.", "warning")
        return redirect(request.referrer or url_for("produtos"))

    carrinho = Carrinho.query.filter_by(
        id_usuario=current_user.id,
        status="ativo"
    ).first()

    if not carrinho:
        carrinho = Carrinho(id_usuario=current_user.id)
        database.session.add(carrinho)
        database.session.commit()

    item = ItemCarrinho.query.filter_by(
        id_carrinho=carrinho.id,
        id_produto=produto.id
    ).first()

    if item:
        item.quantidade += 1
    else:
        item = ItemCarrinho(
            id_carrinho=carrinho.id,
            id_produto=produto.id,
            quantidade=1,
            preco_unitario=produto.preco
        )
        database.session.add(item)

    produto.estoque -= 1

    database.session.commit()

    flash(f"{produto.nome} adicionado ao carrinho!", "success")
    return redirect(request.referrer or url_for("produtos"))


@app.route("/atualizar-item/<int:id_item>", methods=["POST"])
@login_required
def atualizar_item(id_item):
    acao = request.form.get("acao")
    item = ItemCarrinho.query.get_or_404(id_item)
    carrinho = item.carrinho
    id_carrinho = carrinho.id

    if carrinho.id_usuario != current_user.id:
        return jsonify({
            "sucesso": False,
            "mensagem": "Você não pode alterar este item."
        }), 403

    if carrinho.status != "ativo":
        return jsonify({
            "sucesso": False,
            "mensagem": "Este carrinho já está em pagamento e não pode ser alterado."
        }), 400

    produto = Produto.query.get_or_404(item.id_produto)

    if acao == "aumentar":
        if produto.estoque > 0:
            item.quantidade += 1
            produto.estoque -= 1
        else:
            return jsonify({
                "sucesso": False,
                "mensagem": "Produto sem estoque."
            }), 400

    elif acao == "diminuir":
        if item.quantidade > 1:
            item.quantidade -= 1
            produto.estoque += 1
        else:
            produto.estoque += item.quantidade
            database.session.delete(item)

    else:
        return jsonify({
            "sucesso": False,
            "mensagem": "Ação inválida."
        }), 400

    database.session.commit()

    carrinho_atualizado = Carrinho.query.get(id_carrinho)
    database.session.expire(carrinho_atualizado, ["itens"])

    return jsonify(montar_resposta_carrinho(carrinho_atualizado))


@app.route("/remover-item/<int:id_item>", methods=["POST"])
@login_required
def remover_item(id_item):
    item = ItemCarrinho.query.get_or_404(id_item)
    carrinho = item.carrinho
    id_carrinho = carrinho.id

    if carrinho.id_usuario != current_user.id:
        return jsonify({
            "sucesso": False,
            "mensagem": "Você não pode remover este item."
        }), 403

    if carrinho.status != "ativo":
        return jsonify({
            "sucesso": False,
            "mensagem": "Este carrinho já está em pagamento e não pode ser alterado."
        }), 400

    produto = Produto.query.get(item.id_produto)

    if produto:
        produto.estoque += item.quantidade

    database.session.delete(item)
    database.session.commit()

    carrinho_atualizado = Carrinho.query.get(id_carrinho)
    database.session.expire(carrinho_atualizado, ["itens"])

    return jsonify(montar_resposta_carrinho(carrinho_atualizado))


@app.route("/ver-carrinho")
@login_required
def ver_carrinho():
    carrinho = Carrinho.query.filter_by(
        id_usuario=current_user.id,
        status="ativo"
    ).first()

    itens = carrinho.itens if carrinho else []
    total = sum(item.quantidade * item.preco_unitario for item in itens)

    return render_template(
        "_carrinho_lateral.html",
        itens_carrinho=itens,
        total_carrinho=total,
        carrinho=carrinho
    )


@app.route("/finalizar-carrinho", methods=["POST"])
@login_required
def finalizar_carrinho():
    carrinho = Carrinho.query.filter_by(
        id_usuario=current_user.id,
        status="ativo"
    ).first()

    if not carrinho or not carrinho.itens:
        flash("Carrinho vazio!", "warning")
        return redirect(url_for("ver_carrinho"))

    return redirect(url_for("entrega", id_carrinho=carrinho.id))