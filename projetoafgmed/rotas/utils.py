from flask import current_app
from flask_login import current_user
import mercadopago

from projetoafgmed import database, bcrypt
from projetoafgmed.models import Usuario, Medico, Pedido, ItemPedido


SENHA_PADRAO_MEDICO = "123456"


def montar_resposta_carrinho(carrinho):
    itens = carrinho.itens if carrinho else []

    return {
        "sucesso": True,
        "carrinho_id": carrinho.id if carrinho else None,
        "quantidade": sum(item.quantidade for item in itens),
        "total": sum(item.quantidade * item.preco_unitario for item in itens),
        "itens": [
            {
                "id": item.id,
                "produto": item.produto.nome,
                "quantidade": item.quantidade,
                "preco_unitario": float(item.preco_unitario),
                "subtotal": float(item.quantidade * item.preco_unitario),
                "estoque": item.produto.estoque
            }
            for item in itens
        ]
    }


def calcular_total_carrinho(carrinho):
    if not carrinho:
        return 0

    return sum(item.quantidade * item.preco_unitario for item in carrinho.itens)


def criar_ou_atualizar_pedido(carrinho, endereco, cidade, estado, cep):
    total_produtos = calcular_total_carrinho(carrinho)
    total_entrega = 0
    total = total_produtos + total_entrega

    pedido = Pedido.query.filter_by(id_carrinho=carrinho.id).first()

    if not pedido:
        pedido = Pedido(
            id_usuario=carrinho.id_usuario,
            id_carrinho=carrinho.id,
            status="aguardando_pagamento",
            status_pagamento="pending",
            endereco=endereco,
            cidade=cidade,
            estado=estado,
            cep=cep,
            total_produtos=total_produtos,
            total_entrega=total_entrega,
            total=total
        )

        database.session.add(pedido)
        database.session.flush()
    else:
        pedido.endereco = endereco
        pedido.cidade = cidade
        pedido.estado = estado
        pedido.cep = cep
        pedido.total_produtos = total_produtos
        pedido.total_entrega = total_entrega
        pedido.total = total

    ItemPedido.query.filter_by(id_pedido=pedido.id).delete()
    database.session.flush()

    for item in carrinho.itens:
        item_pedido = ItemPedido(
            id_pedido=pedido.id,
            id_produto=item.produto.id,
            nome_produto=item.produto.nome,
            descricao_produto=item.produto.descricao,
            foto_produto=item.produto.foto,
            quantidade=item.quantidade,
            preco_unitario=item.preco_unitario,
            subtotal=item.quantidade * item.preco_unitario
        )

        database.session.add(item_pedido)

    return pedido


def status_visual_pedido(pedido):
    status_pagamento = (pedido.status_pagamento or "").lower()

    if pedido.status == "pago" or status_pagamento == "approved":
        return {
            "classe": "bg-success",
            "icone": "bi-check-circle",
            "texto": "Pagamento aprovado",
            "descricao": "Pedido confirmado e em preparação."
        }

    if pedido.status == "aguardando_pagamento" or status_pagamento in ["pending", "pendente", "in_process"]:
        return {
            "classe": "bg-warning text-dark",
            "icone": "bi-clock-history",
            "texto": "Aguardando pagamento",
            "descricao": "O pagamento ainda está pendente de confirmação."
        }

    if pedido.status in ["falha", "cancelado"] or status_pagamento in ["rejected", "cancelled"]:
        return {
            "classe": "bg-danger",
            "icone": "bi-x-circle",
            "texto": "Pagamento não aprovado",
            "descricao": "O pagamento não foi concluído."
        }

    return {
        "classe": "bg-secondary",
        "icone": "bi-info-circle",
        "texto": "Status em análise",
        "descricao": "Estamos verificando o status do pedido."
    }


def status_visual_consulta(consulta):
    status = (consulta.status or "agendada").lower()

    if status == "agendada":
        return {
            "classe": "bg-primary",
            "icone": "bi-calendar-check",
            "texto": "Agendada"
        }

    if status == "cancelada":
        return {
            "classe": "bg-danger",
            "icone": "bi-x-circle",
            "texto": "Cancelada"
        }

    if status == "concluida":
        return {
            "classe": "bg-success",
            "icone": "bi-check-circle",
            "texto": "Concluída"
        }

    return {
        "classe": "bg-secondary",
        "icone": "bi-info-circle",
        "texto": "Em análise"
    }


def obter_pedido_por_referencia(external_reference):
    if not external_reference:
        return None

    external_reference = str(external_reference)

    if external_reference.startswith("pedido:"):
        try:
            pedido_id = int(external_reference.replace("pedido:", ""))
            return Pedido.query.get(pedido_id)
        except ValueError:
            return None

    try:
        carrinho_id = int(external_reference)
        return Pedido.query.filter_by(id_carrinho=carrinho_id).first()
    except ValueError:
        return None


def sincronizar_usuario_medico(medico):
    email_medico = (medico.email or "").strip().lower()

    if not email_medico:
        return None, "Informe um e-mail para o médico."

    usuario_com_email = Usuario.query.filter_by(email=email_medico).first()
    usuario_vinculado = Usuario.query.filter_by(id_medico=medico.id).first()

    if usuario_com_email and usuario_com_email.id_medico and usuario_com_email.id_medico != medico.id:
        return None, "Este e-mail já está vinculado a outro médico."

    if usuario_vinculado and usuario_vinculado.email != email_medico:
        email_em_uso = Usuario.query.filter_by(email=email_medico).first()

        if email_em_uso and email_em_uso.id != usuario_vinculado.id:
            return None, "Este e-mail já está sendo usado por outro usuário."

        usuario = usuario_vinculado
        usuario.email = email_medico

    elif usuario_com_email:
        usuario = usuario_com_email

    else:
        senha_hash = bcrypt.generate_password_hash(SENHA_PADRAO_MEDICO).decode("utf-8")

        usuario = Usuario(
            nome=medico.nome,
            sobrenome=medico.sobrenome,
            email=email_medico,
            senha=senha_hash,
            is_medico=True,
            id_medico=medico.id
        )

        database.session.add(usuario)

    usuario.nome = medico.nome
    usuario.sobrenome = medico.sobrenome
    usuario.is_medico = True
    usuario.id_medico = medico.id

    return usuario, None


def medico_logado():
    if not getattr(current_user, "is_medico", False):
        return None

    if not current_user.id_medico:
        return None

    return Medico.query.get(current_user.id_medico)


def criar_preferencia_mercado_pago(pedido):
    access_token = current_app.config.get("MERCADO_PAGO_ACCESS_TOKEN")
    app_base_url = current_app.config.get("APP_BASE_URL")

    if not access_token:
        return None, "Access Token do Mercado Pago não configurado."

    if not app_base_url:
        return None, "APP_BASE_URL não configurada no .env."

    if not pedido.itens:
        return None, "Pedido sem itens."

    sdk = mercadopago.SDK(access_token)

    itens_mp = []

    for item in pedido.itens:
        itens_mp.append({
            "title": item.nome_produto,
            "description": item.descricao_produto or "Produto AFGMED",
            "quantity": int(item.quantidade),
            "currency_id": "BRL",
            "unit_price": float(item.preco_unitario)
        })

    preference_data = {
        "items": itens_mp,
        "external_reference": f"pedido:{pedido.id}",
        "back_urls": {
            "success": f"{app_base_url}/pagamento/sucesso",
            "failure": f"{app_base_url}/pagamento/falha",
            "pending": f"{app_base_url}/pagamento/pendente"
        },
        "auto_return": "approved",
        "notification_url": f"{app_base_url}/webhook/mercado-pago"
    }

    try:
        preference_response = sdk.preference().create(preference_data)

        print("RESPOSTA MERCADO PAGO:")
        print(preference_response)

        status_code = preference_response.get("status")

        if status_code not in [200, 201]:
            erro = preference_response.get("response", {})
            return None, str(erro)

        preference = preference_response.get("response", {})

        return preference, None

    except Exception as erro:
        print("ERRO MERCADO PAGO:")
        print(erro)
        return None, str(erro)


def atualizar_carrinho_por_pagamento(pagamento_id):
    access_token = current_app.config.get("MERCADO_PAGO_ACCESS_TOKEN")

    if not access_token:
        print("Access Token do Mercado Pago não configurado.")
        return None

    sdk = mercadopago.SDK(access_token)

    try:
        pagamento_response = sdk.payment().get(str(pagamento_id))
        pagamento = pagamento_response.get("response", {})
    except Exception as erro:
        print("ERRO AO BUSCAR PAGAMENTO NO MERCADO PAGO:")
        print(erro)
        return None

    print("PAGAMENTO RECEBIDO DO MERCADO PAGO:")
    print("ID:", pagamento.get("id"))
    print("STATUS:", pagamento.get("status"))
    print("REFERÊNCIA:", pagamento.get("external_reference"))

    external_reference = pagamento.get("external_reference")
    status_pagamento = pagamento.get("status", "pending")

    pedido = obter_pedido_por_referencia(external_reference)
    carrinho = pedido.carrinho if pedido else None

    if not pedido:
        return pagamento

    pedido.mercado_pago_payment_id = str(pagamento_id)
    pedido.status_pagamento = status_pagamento

    if carrinho:
        carrinho.mercado_pago_payment_id = str(pagamento_id)
        carrinho.status_pagamento = status_pagamento

    if status_pagamento == "approved":
        pedido.status = "pago"

        if carrinho:
            carrinho.status = "finalizado"
            carrinho.ativo = False

    elif status_pagamento in ["rejected", "cancelled"]:
        pedido.status = "falha"

        if carrinho:
            carrinho.status = "ativo"
            carrinho.status_pagamento = status_pagamento
            carrinho.mercado_pago_preference_id = None
            carrinho.mercado_pago_payment_id = None
            carrinho.mercado_pago_init_point = None

    elif status_pagamento in ["pending", "in_process"]:
        pedido.status = "aguardando_pagamento"

        if carrinho:
            carrinho.status = "aguardando_pagamento"

    database.session.commit()

    return pagamento