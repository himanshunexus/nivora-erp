import shutil
import subprocess
import tempfile


def render_pdf_from_html(html):
    executable = shutil.which("wkhtmltopdf")
    if not executable:
        return None

    with tempfile.NamedTemporaryFile(suffix=".html") as html_file, tempfile.NamedTemporaryFile(
        suffix=".pdf"
    ) as pdf_file:
        html_file.write(html.encode("utf-8"))
        html_file.flush()
        subprocess.run(
            [executable, html_file.name, pdf_file.name],
            check=True,
            capture_output=True,
        )
        pdf_file.seek(0)
        return pdf_file.read()
