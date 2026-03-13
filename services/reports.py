from fpdf import FPDF
from fpdf.enums import XPos, YPos

class PDFReport(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 16)
        self.cell(0, 10, 'FINORA - Relatório Financeiro', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def generate_pdf_report(month, year, finances, stats, output_path=None):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font('helvetica', '', 12)
    
    # Period Info
    pdf.cell(0, 10, f'Referência: {month}/{year}', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)
    
    # Summary Section
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, 'Resumo do Mês', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font('helvetica', '', 12)
    # Simple summary table
    pdf.cell(60, 10, f'Receitas: R$ {stats["total_receitas"]:.2f}', border=1)
    pdf.cell(60, 10, f'Despesas: R$ {stats["total_despesas"]:.2f}', border=1)
    pdf.cell(60, 10, f'Saldo: R$ {stats["total_geral"]:.2f}', border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(15)
    
    pdf.cell(60, 10, f'Pago: R$ {stats["total_pago"]:.2f}', border=1)
    pdf.cell(60, 10, f'Pendente: R$ {stats["total_pendente"]:.2f}', border=1)
    pdf.cell(60, 10, f'Atrasado: R$ {stats["total_atrasado"]:.2f}', border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(20)
    
    # Details Table
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, 'Lançamentos', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font('helvetica', 'B', 9)
    # Columns: Date, Desc, Cat, Type, Val, Status
    # Widths: 20, 60, 30, 20, 30, 30 = 190
    col_widths = [20, 60, 30, 20, 30, 30]
    headers = ['Data', 'Descrição', 'Categoria', 'Tipo', 'Valor', 'Status']
    
    for i, h in enumerate(headers):
        next_x = XPos.RIGHT if i < len(headers) - 1 else XPos.LMARGIN
        next_y = YPos.TOP if i < len(headers) - 1 else YPos.NEXT
        pdf.cell(col_widths[i], 8, h, border=1, new_x=next_x, new_y=next_y, align='C')
    
    pdf.set_font('helvetica', '', 9)
    for f in finances:
        # Date
        date_str = f.due_date.strftime('%d/%m')
        pdf.cell(col_widths[0], 8, date_str, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
        
        # Desc (truncate)
        desc = f.description
        if len(desc) > 30:
            desc = desc[:27] + '...'
        pdf.cell(col_widths[1], 8, desc, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
        
        # Cat
        cat = f.category
        if len(cat) > 15:
            cat = cat[:12] + '...'
        pdf.cell(col_widths[2], 8, cat, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
        
        # Type
        pdf.cell(col_widths[3], 8, f.type, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
        
        # Value
        pdf.cell(col_widths[4], 8, f'R$ {f.value:.2f}', border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='R')
        
        # Status
        pdf.cell(col_widths[5], 8, f.status, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        
    if output_path:
        pdf.output(output_path)
        return output_path

    pdf_bytes = pdf.output()
    if isinstance(pdf_bytes, str):
        return pdf_bytes.encode('latin-1')
    return bytes(pdf_bytes)
