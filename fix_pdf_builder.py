import re

def update_pdf_builder():
    with open('src/reports/builders/pdf_builder.py', 'r') as f:
        content = f.read()

    old_story = """
        story: list = []
        _emit(58, "Construyendo PDF: portada...")
        story.extend(self._cover(report_config, df_calls, df_data, logo_path))
        story.append(PageBreak())
        _emit(60, "Construyendo PDF: resumen...")
        story.extend(self._summary(df_calls, report_config))
        story.append(PageBreak())
        _emit(62, "Construyendo PDF: gráficos...")
        story.extend(self._charts(base_dir / "graphics"))
        _emit(65, "Construyendo PDF: tablas entrantes...")
        story.extend(self._call_tables(df_calls, report_config, "entrante"))
        _emit(75, "Construyendo PDF: tablas salientes...")
        story.extend(self._call_tables(df_calls, report_config, "saliente"))
        _emit(85, "Construyendo PDF: mapas...")
        story.extend(self._maps_section(base_dir, pdf_config))
        story.extend(self._notes(report_config, pdf_config))
"""

    new_story = """
        story: list = []
        _emit(58, "Construyendo PDF: portada...")
        story.extend(self._cover(report_config, df_calls, df_data, logo_path))
        story.append(PageBreak())

        if report_config.pdf_draft and len(report_config.pdf_draft) > 0:
            _emit(60, "Construyendo PDF: Procesando bloques personalizados...")
            for i, block in enumerate(report_config.pdf_draft):
                _emit(60 + min(25, int(i / len(report_config.pdf_draft) * 25)), f"Construyendo bloque: {block.get('title', 'Bloque')}...")
                story.extend(self._render_block(block, df_calls, df_data, base_dir, report_config))
        else:
            # Fallback legacy builder if no blocks
            _emit(60, "Construyendo PDF: resumen...")
            story.extend(self._summary(df_calls, report_config))
            story.append(PageBreak())
            _emit(62, "Construyendo PDF: gráficos...")
            story.extend(self._charts(base_dir / "graphics"))
            _emit(65, "Construyendo PDF: tablas entrantes...")
            story.extend(self._call_tables(df_calls, report_config, "entrante"))
            _emit(75, "Construyendo PDF: tablas salientes...")
            story.extend(self._call_tables(df_calls, report_config, "saliente"))
            _emit(85, "Construyendo PDF: mapas...")
            story.extend(self._maps_section(base_dir, pdf_config))

        story.extend(self._notes(report_config, pdf_config))
"""
    content = content.replace(old_story, new_story)

    with open('src/reports/builders/pdf_builder.py', 'w') as f:
        f.write(content)

update_pdf_builder()
