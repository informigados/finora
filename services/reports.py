from fpdf import FPDF
from fpdf.enums import XPos, YPos
from flask_babel import gettext as _


DETAIL_COL_WIDTHS = [16, 42, 26, 28, 18, 30, 30]

class PDFReport(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 16)
        self.cell(0, 10, _('FINORA - Relatório Financeiro'), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, _('Página %(page)s', page=self.page_no()), align='C')

def generate_pdf_report(month, year, finances, stats, output_path=None):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font('helvetica', '', 12)
    
    # Period Info
    pdf.cell(0, 10, _('Referência: %(month)s/%(year)s', month=month, year=year), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)
    
    # Summary Section
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, _('Resumo do Mês'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font('helvetica', '', 12)
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
    pdf.set_font('helvetica', 'B', 14)
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
        pdf.set_font('helvetica', 'B', 9)
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
        pdf.set_font('helvetica', '', 9)

    render_details_header()
    
    for f in finances:
        if pdf.get_y() > 270:
            pdf.add_page()
            pdf.ln(2)
            render_details_header()

        # Date
        date_str = f.due_date.strftime('%d/%m')
        pdf.cell(DETAIL_COL_WIDTHS[0], 8, date_str, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
        
        # Desc (truncate)
        desc = f.description
        if len(desc) > 22:
            desc = desc[:19] + '...'
        pdf.cell(DETAIL_COL_WIDTHS[1], 8, desc, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
        
        # Cat/Subcategory
        cat = _(f.category) if f.category else '-'
        if getattr(f, 'subcategory', None):
            cat = f'{cat} / {_(f.subcategory)}'
        if len(cat) > 13:
            cat = cat[:10] + '...'
        pdf.cell(DETAIL_COL_WIDTHS[2], 8, cat, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)

        # Payment method
        payment_method = _(f.payment_method) if f.payment_method else '-'
        if len(payment_method) > 15:
            payment_method = payment_method[:12] + '...'
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
