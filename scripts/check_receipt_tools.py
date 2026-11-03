"""Exercise real PDF text extraction and raster OCR with a synthetic receipt."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from james.receipt_text import extract_text


def synthetic_pdf():
    stream = b'BT /F1 30 Tf 40 150 Td (COFFEE 4.50) Tj 0 -50 Td (MILK 1.80) Tj ET'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream']
    document, offsets = b'%PDF-1.4\n', [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(document))
        document += str(number).encode() + b' 0 obj\n' + obj + b'\nendobj\n'
    xref = len(document)
    document += b'xref\n0 6\n0000000000 65535 f \n'
    document += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    return document + f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


if __name__ == '__main__':
    data = synthetic_pdf()
    assert 'COFFEE 4.50' in extract_text(data)
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'receipt.pdf'
        path.write_bytes(data)
        for extension, flag in [('png', '-png'), ('jpg', '-jpeg')]:
            subprocess.run(['pdftoppm', '-singlefile', '-scale-to', '1600', flag, str(path),
                str(Path(directory) / 'receipt')], check=True, timeout=10, capture_output=True)
            text = extract_text((Path(directory) / f'receipt.{extension}').read_bytes())
            assert 'COFFEE' in text.upper(), text
    print('Synthetic PDF, JPEG and PNG recognition passed.')
