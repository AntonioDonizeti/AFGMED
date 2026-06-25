from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from projetoafgmed import app, database
from projetoafgmed.models import Medico, Consulta
from projetoafgmed.rotas.utils import status_visual_consulta


@app.route("/consultas/<int:medico_id>", methods=["GET", "POST"])
@login_required
def consultas(medico_id):
    if getattr(current_user, "is_medico", False) and not getattr(current_user, "is_admin", False):
        flash("Usuários médicos não podem marcar consultas como pacientes.", "warning")
        return redirect(url_for("medicos"))

    medico = Medico.query.get_or_404(medico_id)
    horarios = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]

    if request.method == "POST":
        horario = request.form.get("horario")
        data_consulta = request.form.get("data_consulta")

        if not horario or not data_consulta:
            flash("Escolha data e horário para continuar.", "warning")
            return redirect(url_for("consultas", medico_id=medico.id))

        if horario not in horarios:
            flash("Horário inválido.", "danger")
            return redirect(url_for("consultas", medico_id=medico.id))

        try:
            data_obj = datetime.strptime(data_consulta, "%Y-%m-%d").date()
        except ValueError:
            flash("Data inválida.", "danger")
            return redirect(url_for("consultas", medico_id=medico.id))

        if data_obj < datetime.today().date():
            flash("Não é possível marcar consulta em data passada.", "warning")
            return redirect(url_for("consultas", medico_id=medico.id))

        existente = Consulta.query.filter(
            Consulta.medico_id == medico.id,
            Consulta.horario == horario,
            Consulta.data == data_obj,
            Consulta.status.in_(["agendada", "concluida"])
        ).first()

        if existente:
            flash("Horário já reservado para essa data!", "danger")
            return redirect(url_for("consultas", medico_id=medico.id))

        nova_consulta = Consulta(
            medico_id=medico.id,
            usuario_id=current_user.id,
            horario=horario,
            data=data_obj,
            status="agendada"
        )

        database.session.add(nova_consulta)
        database.session.commit()

        flash("Consulta agendada com sucesso!", "success")
        return redirect(url_for("meus_agendamentos"))

    consultas_marcadas = Consulta.query.filter_by(medico_id=medico.id).all()

    return render_template(
        "consultas.html",
        medico=medico,
        horarios=horarios,
        consultas=consultas_marcadas
    )


@app.route("/horarios_disponiveis/<int:medico_id>/<data>")
@login_required
def horarios_disponiveis(medico_id, data):
    try:
        data_obj = datetime.strptime(data, "%Y-%m-%d").date()
    except ValueError:
        return jsonify([])

    if data_obj < datetime.today().date():
        return jsonify([])

    consultas = Consulta.query.filter(
        Consulta.medico_id == medico_id,
        Consulta.data == data_obj,
        Consulta.status.in_(["agendada", "concluida"])
    ).all()

    horarios_ocupados = [c.horario for c in consultas]

    return jsonify(horarios_ocupados)


@app.route("/meus_agendamentos")
@login_required
def meus_agendamentos():
    consultas_usuario = Consulta.query.filter(
        Consulta.usuario_id == current_user.id,
        Consulta.status != "cancelada"
    ).order_by(
        Consulta.data.asc(),
        Consulta.horario.asc()
    ).all()

    return render_template(
        "meus_agendamentos.html",
        consultas=consultas_usuario,
        status_visual_consulta=status_visual_consulta
    )


@app.route("/cancelar_consulta/<int:consulta_id>", methods=["POST"])
@login_required
def cancelar_consulta(consulta_id):
    consulta = Consulta.query.get_or_404(consulta_id)

    if consulta.usuario_id != current_user.id and not getattr(current_user, "is_admin", False):
        flash("Você não pode cancelar esta consulta.", "danger")
        return redirect(url_for("meus_agendamentos"))

    if consulta.status != "agendada":
        flash("Apenas consultas agendadas podem ser canceladas.", "warning")
        return redirect(url_for("meus_agendamentos"))

    consulta.status = "cancelada"
    database.session.commit()

    flash("Consulta cancelada com sucesso!", "success")
    return redirect(url_for("meus_agendamentos"))


@app.route("/concluir-consulta/<int:consulta_id>", methods=["POST"])
@login_required
def concluir_consulta(consulta_id):
    consulta = Consulta.query.get_or_404(consulta_id)

    usuario_e_medico_da_consulta = (
        getattr(current_user, "is_medico", False)
        and current_user.id_medico == consulta.medico_id
    )

    if not usuario_e_medico_da_consulta and not getattr(current_user, "is_admin", False):
        flash("Você não pode concluir esta consulta.", "danger")
        return redirect(url_for("medicos"))

    if consulta.status != "agendada":
        flash("Apenas consultas agendadas podem ser concluídas.", "warning")
        return redirect(url_for("medicos"))

    consulta.status = "concluida"
    database.session.commit()

    flash("Consulta concluída com sucesso!", "success")
    return redirect(url_for("medicos"))