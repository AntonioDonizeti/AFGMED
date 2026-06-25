from flask import render_template, redirect, url_for, flash, current_app, request, jsonify
from flask_login import login_required, current_user

from projetoafgmed import app, database
from projetoafgmed.models import Carrinho, Entrega, PerfilUsuario, Pedido
from projetoafgmed.rotas.utils import (
    criar_ou_atualizar_pedido,
    criar_preferencia_mercado_pago,
    atualizar_carrinho_por_pagamento,
    obter_pedido_por_referencia,
    status_visual_pedido
)


@app.route("/entrega/<int:id_carrinho>", methods=["GET", "POST"])
@login_required
def entrega(id_carrinho):
    carrinho = Carrinho.query.get_or_404(id_carrinho)
    usuario = current_user
    perfil_usuario = usuario.perfil or PerfilUsuario(usuario=usuario)

    if carrinho.id_usuario != current_user.id:
        return redirect(url_for("homepage"))

    if carrinho.status not in ["ativo", "aguardando_pagamento"]:
        return redirect(url_for("homepage"))

    if request.method == "POST":
        endereco = request.form.get("endereco") or perfil_usuario.endereco
        cidade = request.form.get("cidade") or perfil_usuario.cidade
        estado = request.form.get("estado") or perfil_usuario.estado
        cep = request.form.get("cep") or perfil_usuario.cep

        if not endereco or not cidade or not estado or not cep:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "sucesso": False,
                    "mensagem": "Preencha todos os dados de entrega."
                })

            flash("Preencha todos os dados de entrega.", "warning")
            return redirect(url_for("entrega", id_carrinho=carrinho.id))

        if carrinho.entrega:
            carrinho.entrega.endereco = endereco
            carrinho.entrega.cidade = cidade
            carrinho.entrega.estado = estado
            carrinho.entrega.cep = cep
        else:
            nova_entrega = Entrega(
                id_carrinho=carrinho.id,
                endereco=endereco,
                cidade=cidade,
                estado=estado,
                cep=cep
            )
            database.session.add(nova_entrega)

        perfil_usuario.endereco = endereco
        perfil_usuario.cidade = cidade
        perfil_usuario.estado = estado
        perfil_usuario.cep = cep

        database.session.add(perfil_usuario)

        pedido = criar_ou_atualizar_pedido(
            carrinho=carrinho,
            endereco=endereco,
            cidade=cidade,
            estado=estado,
            cep=cep
        )

        database.session.commit()

        if (
            pedido.status == "aguardando_pagamento"
            and pedido.status_pagamento in ["pending", "pendente", "in_process"]
            and pedido.mercado_pago_preference_id
            and pedido.mercado_pago_init_point
        ):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "sucesso": True,
                    "redirect_url": pedido.mercado_pago_init_point
                })

            return redirect(pedido.mercado_pago_init_point)

        carrinho.status = "aguardando_pagamento"
        carrinho.status_pagamento = "pending"

        pedido.status = "aguardando_pagamento"
        pedido.status_pagamento = "pending"

        database.session.commit()

        preference, erro_mp = criar_preferencia_mercado_pago(pedido)

        if not preference:
            carrinho.status = "ativo"
            carrinho.status_pagamento = "pendente"

            pedido.status = "falha"
            pedido.status_pagamento = "rejected"

            database.session.commit()

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "sucesso": False,
                    "mensagem": f"Erro Mercado Pago: {erro_mp}"
                })

            flash(f"Erro Mercado Pago: {erro_mp}", "danger")
            return redirect(url_for("entrega", id_carrinho=carrinho.id))

        link_pagamento = preference.get("init_point") or preference.get("sandbox_init_point")

        if not link_pagamento:
            carrinho.status = "ativo"
            carrinho.status_pagamento = "pendente"

            pedido.status = "falha"
            pedido.status_pagamento = "rejected"

            database.session.commit()

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "sucesso": False,
                    "mensagem": "Mercado Pago não retornou link de pagamento."
                })

            flash("Mercado Pago não retornou link de pagamento.", "danger")
            return redirect(url_for("entrega", id_carrinho=carrinho.id))

        pedido.mercado_pago_preference_id = preference.get("id")
        pedido.mercado_pago_init_point = link_pagamento

        carrinho.mercado_pago_preference_id = preference.get("id")
        carrinho.mercado_pago_init_point = link_pagamento

        database.session.commit()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "sucesso": True,
                "redirect_url": link_pagamento
            })

        return redirect(link_pagamento)

    return render_template(
        "entrega.html",
        carrinho=carrinho,
        perfil=perfil_usuario,
        google_maps_api_key=current_app.config.get("GOOGLE_MAPS_API_KEY")
    )


@app.route("/pagamento/sucesso")
def pagamento_sucesso():
    payment_id = request.args.get("payment_id") or request.args.get("collection_id")
    external_reference = request.args.get("external_reference")

    pedido = None

    if payment_id:
        pagamento = atualizar_carrinho_por_pagamento(payment_id)

        if pagamento and pagamento.get("external_reference"):
            external_reference = pagamento.get("external_reference")

    if external_reference:
        pedido = obter_pedido_por_referencia(external_reference)

    if pedido and pedido.status == "pago":
        return render_template("pagamento_sucesso.html", pedido=pedido, carrinho=pedido.carrinho)

    return render_template(
        "pagamento_pendente.html",
        pedido=pedido,
        carrinho=pedido.carrinho if pedido else None
    )


@app.route("/pagamento/falha")
def pagamento_falha():
    external_reference = request.args.get("external_reference")

    pedido = obter_pedido_por_referencia(external_reference)
    carrinho = pedido.carrinho if pedido else None

    if pedido:
        pedido.status_pagamento = "rejected"
        pedido.status = "falha"

    if carrinho:
        carrinho.status_pagamento = "falha"
        carrinho.status = "ativo"
        carrinho.mercado_pago_preference_id = None
        carrinho.mercado_pago_payment_id = None
        carrinho.mercado_pago_init_point = None

    database.session.commit()

    return render_template("pagamento_falha.html", pedido=pedido, carrinho=carrinho)


@app.route("/pagamento/pendente")
def pagamento_pendente():
    payment_id = request.args.get("payment_id") or request.args.get("collection_id")
    external_reference = request.args.get("external_reference")

    pedido = None

    if payment_id:
        pagamento = atualizar_carrinho_por_pagamento(payment_id)

        if pagamento and pagamento.get("external_reference"):
            external_reference = pagamento.get("external_reference")

    if external_reference:
        pedido = obter_pedido_por_referencia(external_reference)

    if pedido and pedido.status == "pago":
        return render_template("pagamento_sucesso.html", pedido=pedido, carrinho=pedido.carrinho)

    return render_template(
        "pagamento_pendente.html",
        pedido=pedido,
        carrinho=pedido.carrinho if pedido else None
    )


@app.route("/status-pagamento/<int:id_carrinho>")
@login_required
def status_pagamento(id_carrinho):
    carrinho = Carrinho.query.get_or_404(id_carrinho)

    if carrinho.id_usuario != current_user.id and not current_user.is_admin:
        return jsonify({
            "sucesso": False,
            "mensagem": "Você não pode acessar este pedido."
        }), 403

    pedido = Pedido.query.filter_by(id_carrinho=carrinho.id).first()

    if pedido:
        status = status_visual_pedido(pedido)

        return jsonify({
            "sucesso": True,
            "status": carrinho.status,
            "status_pedido": pedido.status,
            "status_pagamento": pedido.status_pagamento,
            "classe": status["classe"],
            "icone": status["icone"],
            "texto": status["texto"],
            "descricao": status["descricao"]
        })

    return jsonify({
        "sucesso": True,
        "status": carrinho.status,
        "status_pedido": None,
        "status_pagamento": carrinho.status_pagamento,
        "classe": "bg-secondary",
        "icone": "bi-info-circle",
        "texto": "Status em análise",
        "descricao": "Estamos verificando o status do pedido."
    })


@app.route("/webhook/mercado-pago", methods=["POST"])
def webhook_mercado_pago():
    dados = request.get_json(silent=True) or {}

    tipo = (
        dados.get("type")
        or request.args.get("type")
        or request.args.get("topic")
    )

    pagamento_id = None

    if dados.get("data"):
        pagamento_id = dados["data"].get("id")

    if not pagamento_id:
        pagamento_id = request.args.get("data.id")

    if not pagamento_id:
        pagamento_id = request.args.get("id")

    print("WEBHOOK RECEBIDO:")
    print("Tipo:", tipo)
    print("Pagamento ID:", pagamento_id)

    if tipo == "merchant_order":
        return "", 200

    if tipo not in ["payment", "payments"]:
        return "", 200

    if not pagamento_id:
        return "", 200

    atualizar_carrinho_por_pagamento(pagamento_id)

    return "", 200