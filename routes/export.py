from flask import Blueprint, send_file, current_app
from flask_login import login_required, current_user
from flask_babel import gettext as _
from services.reports import generate_pdf_report
from services.calculations import get_monthly_stats
from models.finance import Finance
from sqlalchemy import extract
from database.db import db
import csv
import io
import os

export_bp = Blueprint('export', __name__)

@export_bp.route('/export/<type>/<int:year>/<int:month>')
@login_required
def export_data(type, year, month):
    entries = db.session.query(Finance).filter(
        Finance.user_id == current_user.id,
        extract('year', Finance.due_date) == year,
        extract('month', Finance.due_date) == month
    ).order_by(Finance.due_date).all()
    
    if type == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Descrição', 'Valor', 'Categoria', 'Tipo', 'Status', 'Vencimento', 'Pagamento', 'Observações'])
        for e in entries:
            writer.writerow([
                e.id, 
                e.description, 
                e.value, 
                e.category, 
                e.type, 
                e.status, 
                e.due_date, 
                e.payment_date, 
                e.observations
            ])
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'finora_{year}_{month}.csv'
        )
        
    elif type == 'txt':
        output = io.StringIO()
        output.write(f"Relatório FINORA - {month}/{year}\n")
        output.write("="*80 + "\n")
        output.write(f"{'Data':<12} | {'Descrição':<30} | {'Valor':<10} | {'Status':<10}\n")
        output.write("-" * 80 + "\n")
        for e in entries:
            date_str = e.due_date.strftime('%d/%m/%Y')
            output.write(f"{date_str:<12} | {e.description:<30} | R$ {e.value:<7.2f} | {e.status:<10}\n")
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/plain',
            as_attachment=True,
            download_name=f'finora_{year}_{month}.txt'
        )
        
    elif type == 'pdf':
        stats = get_monthly_stats(month, year, user_id=current_user.id)
        
        # Path scoped to app root for predictable behavior in different runtimes.
        export_dir = os.path.join(current_app.root_path, 'exports')
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
             
        filename = f'finora_report_{year}_{month}.pdf'
        filepath = os.path.join(export_dir, filename)
        
        generate_pdf_report(month, year, entries, stats, filepath)
        
        return send_file(
            filepath,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
         
    return _('Tipo de exportação inválido.'), 400
