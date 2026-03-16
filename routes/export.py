from flask import Blueprint, Response, abort, current_app, flash, redirect, send_file, stream_with_context, url_for
from flask_login import login_required, current_user
from flask.typing import ResponseReturnValue
from flask_babel import gettext as _
from services.reports import generate_pdf_report
from services.calculations import get_monthly_stats
from services.profile_service import record_activity
from models.finance import Finance
from sqlalchemy import extract
from database.db import db
import csv
import io

export_bp = Blueprint('export', __name__)


def _build_entries_query(year: int, month: int):
    return db.session.query(Finance).filter(
        Finance.user_id == current_user.id,
        extract('year', Finance.due_date) == year,
        extract('month', Finance.due_date) == month,
    ).order_by(Finance.due_date, Finance.id)

@export_bp.route('/export/<type>/<int:year>/<int:month>')
@login_required
def export_data(type: str, year: int, month: int) -> ResponseReturnValue:
    entries_query = _build_entries_query(year, month)
    total_entries = entries_query.order_by(None).count()
    
    if type == 'csv':
        def generate_csv_rows():
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow([
                _('ID'),
                _('Descrição'),
                _('Valor'),
                _('Categoria'),
                _('Subcategoria'),
                _('Tipo'),
                _('Status'),
                _('Vencimento'),
                _('Pagamento'),
                _('Forma de pagamento/recebimento'),
                _('Observações'),
            ])
            yield '\ufeff' + buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

            for entry in entries_query.yield_per(500):
                writer.writerow([
                    entry.id,
                    entry.description,
                    entry.value,
                    _(entry.category) if entry.category else '',
                    _(entry.subcategory) if entry.subcategory else '',
                    _(entry.type),
                    _(entry.status),
                    entry.due_date,
                    entry.payment_date,
                    _(entry.payment_method) if entry.payment_method else '',
                    entry.observations,
                ])
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate(0)

        record_activity(
            current_user,
            'exports',
            'export_csv',
            'Exportação CSV concluída.',
            details={'year': year, 'month': month, 'entries': total_entries},
        )
        return Response(
            stream_with_context(generate_csv_rows()),
            mimetype='text/csv; charset=utf-8-sig',
            headers={
                'Content-Disposition': f'attachment; filename=finora_{year}_{month}.csv',
            },
        )
        
    elif type == 'txt':
        def generate_txt_rows():
            yield _('Relatório FINORA - %(month)s/%(year)s', month=month, year=year) + "\n"
            yield "=" * 80 + "\n"
            yield (
                f"{_('Data'):<12} | {_('Descrição'):<24} | {_('Categoria'):<24} | "
                f"{_('Método'):<20} | {_('Valor'):<10} | {_('Status'):<10}\n"
            )
            yield "-" * 120 + "\n"

            for entry in entries_query.yield_per(500):
                date_str = entry.due_date.strftime('%d/%m/%Y')
                description = entry.description[:24]
                category_label = _(entry.category) if entry.category else '-'
                if entry.subcategory:
                    category_label = f'{category_label} / {_(entry.subcategory)}'
                category_label = category_label[:24]
                payment_method = (_(entry.payment_method) if entry.payment_method else '-')[:20]
                yield (
                    f"{date_str:<12} | {description:<24} | {category_label:<24} | "
                    f"{payment_method:<20} | R$ {entry.value:<7.2f} | {_(entry.status):<10}\n"
                )

        record_activity(
            current_user,
            'exports',
            'export_txt',
            'Exportação TXT concluída.',
            details={'year': year, 'month': month, 'entries': total_entries},
        )
        return Response(
            stream_with_context(generate_txt_rows()),
            mimetype='text/plain; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename=finora_{year}_{month}.txt',
            },
        )
        
    elif type == 'pdf':
        max_pdf_rows = int(current_app.config.get('PDF_EXPORT_MAX_ROWS', 5000) or 5000)
        stats = get_monthly_stats(month, year, user_id=current_user.id)
        if total_entries > max_pdf_rows:
            flash(
                _(
                    'O relatório PDF está limitado a %(limit)s lançamentos por exportação. Refine o período ou use CSV/TXT para volumes maiores.',
                    limit=max_pdf_rows,
                ),
                'warning',
            )
            return redirect(url_for('dashboard.view_month', year=year, month=month))

        entries = entries_query.all()

        filename = f'finora_report_{year}_{month}.pdf'
        pdf_bytes = generate_pdf_report(month, year, entries, stats)
        record_activity(
            current_user,
            'exports',
            'export_pdf',
            'Exportação PDF concluída.',
            details={'year': year, 'month': month, 'entries': total_entries},
        )

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
         
    return abort(400, description=_('Tipo de exportação inválido.'))
