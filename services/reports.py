from pathlib import Path

from flask import current_app, has_app_context
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from flask_babel import gettext as _


DETAIL_COL_WIDTHS = [14, 38, 25, 27, 18, 38, 30]

class PDFReport(FPDF):
    def __init__(self):
        super().__init__()
        static_root = Path(current_app.static_folder) if has_app_context() else Path(__file__).resolve().parents[1] / 'static'
        font_root = static_root / 'vendor' / 'fonts' / 'noto-sans'
        for style, filename in (('', 'Regular'), ('B', 'Bold'), ('I', 'Italic')):
            self.add_font('Finora', style, str(font_root / f'NotoSans-{filename}.ttf'))

    def header(self):
        self.set_font('Finora', 'B', 16)
        self.cell(0, 10, _('FINORA - Relatório Financeiro'), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Finora', 'I', 8)
        self.cell(0, 10, _('Página %(page)s', page=self.page_no()), align='C')

def generate_pdf_report(month, year, finances, stats, output_path=None):
    pdf = PDFReport()
    pdf.set_margins(10, 10, 10)
    pdf.add_page()
    pdf.set_font('Finora', '', 12)
    
    # Period Info
    pdf.cell(0, 10, _('Referência: %(month)s/%(year)s', month=month, year=year), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)
    
    # Summary Section
    pdf.set_font('Finora', 'B', 14)
    pdf.cell(0, 10, _('Resumo do Mês'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font('Finora', '', 12)
    # Simple summary table
    pdf.cell(60, 10, _('Receitas: R$ %(value).2f', value=stats["total_receitas"]), border=1)
    pdf.cell(60, 10, _('Despesas: R$ %(value).2f', value=stats["total_despesas"]), border=1)
    pdf.cell(60, 10, _('Saldo: R$ %(value).2f', value=stats["total_geral"]), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(15)
    
    pdf.cell(60, 10, _('Pago: R$ %(value).2f', value=stats["total_pago"]), border=1)
    pdf.cell(60, 10, _('Pendente: R$ %(value).2f', value=stats["total_pendente"]), border=1)
    pdf.cell(60, 10, _('Atrasado: R$ %(value).2f', value=stats["total_atrasado"]), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(20)
    
    # Details Table
    pdf.set_font('Finora', 'B', 14)
    pdf.cell(0, 10, _('Lançamentos'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    detail_headers = [
        _('Data'),
        _('Descrição'),
        _('Categoria'),
        _('Método'),
        _('Tipo'),
        _('Valor'),
        _('Status'),
    ]

    def render_details_header():
        pdf.set_font('Finora', 'B', 9)
        for i, header in enumerate(detail_headers):
            next_x = XPos.RIGHT if i < len(detail_headers) - 1 else XPos.LMARGIN
            next_y = YPos.TOP if i < len(detail_headers) - 1 else YPos.NEXT
            pdf.cell(
                DETAIL_COL_WIDTHS[i],
                8,
                header,
                border=1,
                new_x=next_x,
                new_y=next_y,
                align='C',
            )
        pdf.set_font('Finora', '', 9)

    render_details_header()

    def fit_cell_text(text, width):
        if pdf.get_string_width(text) <= width - 2 * pdf.c_margin:
            return text
        while text and pdf.get_string_width(text + '...') > width - 2 * pdf.c_margin:
            text = text[:-1]
        return text + '...'
    
    for f in finances:
        if pdf.get_y() > 270:
            pdf.add_page()
            pdf.ln(2)
            render_details_header()

        # Date
        date_str = f.due_date.strftime('%d/%m')
        pdf.cell(DETAIL_COL_WIDTHS[0], 8, date_str, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
        
        # Desc (truncate)
        desc = fit_cell_text(f.description, DETAIL_COL_WIDTHS[1])
        pdf.cell(DETAIL_COL_WIDTHS[1], 8, desc, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
        
        # Cat/Subcategory
        cat = _(f.category) if f.category else '-'
        if getattr(f, 'subcategory', None):
            cat = f'{cat} / {_(f.subcategory)}'
        cat = fit_cell_text(cat, DETAIL_COL_WIDTHS[2])
        pdf.cell(DETAIL_COL_WIDTHS[2], 8, cat, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)

        # Payment method
        payment_method = _(f.payment_method) if f.payment_method else '-'
        payment_method = fit_cell_text(payment_method, DETAIL_COL_WIDTHS[3])
        pdf.cell(DETAIL_COL_WIDTHS[3], 8, payment_method, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
        
        # Type
        pdf.cell(DETAIL_COL_WIDTHS[4], 8, _(f.type), border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
        
        # Value
        pdf.cell(DETAIL_COL_WIDTHS[5], 8, f'R$ {f.value:.2f}', border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='R')
        
        # Status
        pdf.cell(DETAIL_COL_WIDTHS[6], 8, _(f.status), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        
    if output_path:
        pdf.output(output_path)
        return output_path

    pdf_bytes = pdf.output()
    if isinstance(pdf_bytes, str):
        return pdf_bytes.encode('latin-1')
    return bytes(pdf_bytes)
