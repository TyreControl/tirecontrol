"""
GERADOR DE RELATÓRIOS
Arquivo: relatorios.py
Objetivo: Exportar relatórios em CSV e PDF
"""

import streamlit as st
import pandas as pd
from database import run_query
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import io

def gerar_relatorio_operacional(cliente_id, periodo_dias=30):
    """
    Relatório para operador/gerente
    """
    
    data_inicio = datetime.now() - timedelta(days=periodo_dias)
    
    # Query movimentos últimos X dias
    movimentos = run_query("""
        SELECT * FROM movimentacoes 
        WHERE cliente_id = %s AND data_movimento >= %s
        ORDER BY data_movimento DESC
    """, (cliente_id, data_inicio))
    
    if not movimentos:
        return None
    
    # Agregar por tipo
    movimentos_list = list(movimentos)
    montagens = len([m for m in movimentos_list if m.get('tipo_movimento') == 'MONTAGEM'])
    desmontagens = len([m for m in movimentos_list if m.get('tipo_movimento') == 'DESMONTAGEM'])
    recapagens = len([m for m in movimentos_list if m.get('tipo_movimento') == 'RECAPAGEM'])
    rodizios = len([m for m in movimentos_list if m.get('tipo_movimento') == 'RODIZIO'])
    
    # Criar DataFrame
    df = pd.DataFrame({
        'Data': [m.get('data_movimento') for m in movimentos_list],
        'Tipo': [m.get('tipo_movimento') for m in movimentos_list],
        'Pneu ID': [m.get('pneu_id') for m in movimentos_list],
        'Posição Nova': [m.get('destino_posicao') for m in movimentos_list],
        'Usuário': [m.get('usuario_responsavel') for m in movimentos_list]
    })
    
    return {
        'periodo': f"{periodo_dias} dias",
        'data_relatorio': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'resumo': {
            'total_movimentos': len(movimentos_list),
            'montagens': montagens,
            'desmontagens': desmontagens,
            'recapagens': recapagens,
            'rodizios': rodizios
        },
        'detalhes': df
    }

def gerar_relatorio_estoque(cliente_id):
    """
    Relatório de posição de estoque
    """
    
    pneus = run_query("""
        SELECT marca_fogo, marca, medida, status, ciclo_atual, km_vida_total
        FROM pneus 
        WHERE cliente_id = %s
        ORDER BY status, marca_fogo
    """, (cliente_id,))
    
    if not pneus:
        return None
    
    df = pd.DataFrame(pneus)
    
    # Contar por status
    resumo_status = df['status'].value_counts().to_dict()
    
    return {
        'data_relatorio': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'resumo': resumo_status,
        'detalhes': df,
        'total_ativos': len(df[df['status'] == 'MONTADO'])
    }

def gerar_relatorio_cpk(cliente_id):
    """
    Relatório de CPK
    """
    from analise_cpk import calcular_cpk_frota
    
    cpk_data = calcular_cpk_frota(cliente_id)
    
    if not cpk_data:
        return None
    
    return {
        'data_relatorio': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'cpk': cpk_data,
        'vidas': cpk_data['vidas']
    }

def exportar_csv(dados, nome_arquivo):
    """
    Exporta DataFrame para CSV
    """
    
    csv_buffer = io.StringIO()
    dados['detalhes'].to_csv(csv_buffer, index=False)
    
    csv_content = csv_buffer.getvalue()
    
    return csv_content.encode()

def exportar_pdf_operacional(relatorio):
    """
    Exporta relatório operacional para PDF
    """
    
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=30,
        alignment=1
    )
    
    title = Paragraph("RELATÓRIO OPERACIONAL - TYRECONTROL", title_style)
    elements.append(title)
    
    # Data
    date_style = ParagraphStyle('DateStyle', parent=styles['Normal'], fontSize=10, alignment=1)
    date_para = Paragraph(f"Período: {relatorio['periodo']} | Gerado em: {relatorio['data_relatorio']}", date_style)
    elements.append(date_para)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Resumo
    st_style = ParagraphStyle('SectionTitle', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#1f77b4'))
    elementos.append(Paragraph("RESUMO EXECUTIVO", st_style))
    
    resumo_data = [
        ['Métrica', 'Valor'],
        ['Período', relatorio['periodo']],
        ['Total de Movimentos', str(relatorio['resumo']['total_movimentos'])],
        ['Montagens', str(relatorio['resumo']['montagens'])],
        ['Desmontagens', str(relatorio['resumo']['desmontagens'])],
        ['Recapagens', str(relatorio['resumo']['recapagens'])],
        ['Rodízios', str(relatorio['resumo']['rodizios'])]
    ]
    
    resumo_table = Table(resumo_data, colWidths=[3*inch, 2*inch])
    resumo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    
    elements.append(resumo_table)
    elements.append(Spacer(1, 0.5 * inch))
    
    # Tabela detalhes
    elementos.append(Paragraph("DETALHES DOS MOVIMENTOS", st_style))
    
    # Converter DataFrame para lista para tabela
    detalhes = relatorio['detalhes'].head(20).values.tolist()
    detalhes_table = Table(detalhes, colWidths=[1*inch, 1.5*inch, 1.5*inch, 1.5*inch, 1*inch])
    detalhes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elementos.append(detalhes_table)
    
    # Build PDF
    doc.build(elements)
    pdf_buffer.seek(0)
    
    return pdf_buffer.getvalue()

def render_relatorios(cliente_id):
    """Interface Streamlit para relatórios"""
    
    st.set_page_config(page_title="Relatórios", layout="wide")
    
    st.title("📊 Gerador de Relatórios")
    st.caption("Exporte dados em CSV e PDF")
    
    tipo_relatorio = st.selectbox(
        "Tipo de Relatório",
        ["Operacional", "Estoque", "CPK"]
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if tipo_relatorio == "Operacional":
            periodo = st.selectbox("Período", [7, 15, 30, 60], format_func=lambda x: f"{x} dias")
            
            if st.button("Gerar Relatório"):
                relatorio = gerar_relatorio_operacional(cliente_id, periodo)
                
                if relatorio:
                    st.success("✅ Relatório gerado com sucesso!")
                    
                    # Preview
                    st.subheader("Preview")
                    st.dataframe(relatorio['detalhes'].head(10), use_container_width=True)
                    
                    # Resumo
                    col_a, col_b, col_c, col_d = st.columns(4)
                    col_a.metric("Total Movimentos", relatorio['resumo']['total_movimentos'])
                    col_b.metric("Montagens", relatorio['resumo']['montagens'])
                    col_c.metric("Desmontagens", relatorio['resumo']['desmontagens'])
                    col_d.metric("Rodízios", relatorio['resumo']['rodizios'])
                    
                    # Exportar
                    col_x, col_y = st.columns(2)
                    
                    with col_x:
                        csv_data = exportar_csv(relatorio, "relatorio_operacional")
                        st.download_button(
                            label="📥 Download CSV",
                            data=csv_data,
                            file_name=f"relatorio_operacional_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    
                    with col_y:
                        pdf_data = exportar_pdf_operacional(relatorio)
                        st.download_button(
                            label="📥 Download PDF",
                            data=pdf_data,
                            file_name=f"relatorio_operacional_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf"
                        )
                else:
                    st.warning("Sem dados para o período selecionado")
        
        elif tipo_relatorio == "Estoque":
            if st.button("Gerar Relatório de Estoque"):
                relatorio = gerar_relatorio_estoque(cliente_id)
                
                if relatorio:
                    st.success("✅ Relatório gerado com sucesso!")
                    
                    # Resumo por status
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Pneus Montados", relatorio['resumo'].get('MONTADO', 0))
                    col_b.metric("Pneus em Estoque", relatorio['resumo'].get('ESTOQUE', 0))
                    col_c.metric("Em Recapagem", relatorio['resumo'].get('RECAPAGEM', 0))
                    
                    # Tabela
                    st.dataframe(relatorio['detalhes'], use_container_width=True)
                else:
                    st.warning("Sem dados de estoque")
        
        elif tipo_relatorio == "CPK":
            if st.button("Calcular CPK"):
                relatorio = gerar_relatorio_cpk(cliente_id)
                
                if relatorio:
                    st.success("✅ CPK calculado com sucesso!")
                    
                    cpk = relatorio['cpk']
                    
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("CPK", cpk['cpk'])
                    col_b.metric("Status", cpk['status'].split()[1])
                    col_c.metric("% Dentro Spec", f"{cpk['percentual_dentro_spec']:.1f}%")
                    
                    st.info(f"💡 {cpk['recomendacao']}")

if __name__ == "__main__":
    if 'cliente_id' not in st.session_state:
        st.error("Erro: cliente_id não configurado")
    else:
        render_relatorios(st.session_state['cliente_id'])
