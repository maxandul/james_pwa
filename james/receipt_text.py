"""Bounded local extraction. Originals live only in a temporary directory."""
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory, TemporaryFile
import time
from unicodedata import normalize

MAX_TEXT = 24000
MAX_ROWS = 60


def tool_limits():
    # Native document/image readers run separately with bounded resources on Linux.
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))


def run_tool(args, deadline):
    try:
        with TemporaryFile() as output:
            subprocess.run(args, stdout=output, stderr=subprocess.DEVNULL,
                timeout=max(0.1, deadline - time.monotonic()),
                preexec_fn=tool_limits if os.name == "posix" else None,
                env={**os.environ, "OMP_THREAD_LIMIT": "1", "LC_ALL": "C"}, check=True)
            output.seek(0)
            result = output.read(256001)
        if len(result) > 256000:
            raise ValueError("Der Beleg ist zu umfangreich. Bitte einen kuerzeren Ausschnitt verwenden.")
        return result.decode("utf-8", errors="replace")
    except FileNotFoundError:
        raise ValueError("Die lokale Texterkennung ist hier nicht installiert. Du kannst den Belegtext einfuegen.") from None
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        raise ValueError("Der Beleg konnte nicht gelesen werden. Bitte ein klares Foto, ein ungeschuetztes PDF oder Text verwenden.") from None


def extract_text(data):
    deadline = time.monotonic() + 20
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Die Datei darf hoechstens 10 MB gross sein.")
    pdf = data.startswith(b"%PDF-")
    image = data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")
    if not pdf and not image:
        raise ValueError("Bitte ein PDF, JPEG oder PNG hochladen.")
    with TemporaryDirectory(prefix="james-receipt-") as directory:
        root = Path(directory)
        path = root / ("receipt.pdf" if pdf else "receipt.image")
        path.write_bytes(data)
        if pdf:
            info = run_tool(["pdfinfo", str(path)], deadline)
            pages = re.search(r"^Pages:\s+(\d+)", info, re.M)
            if not pages or not 1 <= int(pages[1]) <= 3:
                raise ValueError("Bitte einen Beleg mit hoechstens drei Seiten verwenden.")
            texts = []
            for number in range(1, int(pages[1]) + 1):
                page_text = run_tool(["pdftotext", "-f", str(number), "-l", str(number), "-layout", str(path), "-"], deadline)
                if len(page_text.strip()) < 20:
                    prefix = root / f"page-{number}"
                    run_tool(["pdftoppm", "-f", str(number), "-l", str(number), "-singlefile",
                        "-scale-to", "2400", "-png", str(path), str(prefix)], deadline)
                    page_text = run_tool(["tesseract", str(prefix) + ".png", "stdout", "-l", "deu+eng", "--psm", "6"], deadline)
                texts.append(page_text)
            text = "\n".join(texts)
        else:
            text = run_tool(["tesseract", str(path), "stdout", "-l", "deu+eng", "--psm", "6"], deadline)
    return clean_receipt_text(text)


def clean_receipt_text(text):
    text = normalize("NFKC", text).replace("\x00", "").replace("\x0c", "\n").strip()
    text = "".join(c for c in text if c in "\n\t" or ord(c) >= 32)
    if not text or len(text) > MAX_TEXT:
        raise ValueError("Bitte einen lesbaren Belegtext mit hoechstens 24'000 Zeichen verwenden.")
    return text


def label_key(text):
    return " ".join(re.findall(r"[^\W_]+", normalize("NFKC", text).casefold()))


def parse_lines(text):
    """Conservative suggestions, never a claim of complete receipt recognition."""
    rows = []
    ignored = re.compile(r"^(?:total|subtotal|zwischentotal|summe|mwst|mehrwertsteuer|visa|mastercard|twint|barzahlung|rueckgeld|rückgeld|rabatt|ersparnis|cumulus|supercard|chf|eur|zahlung|bezahlt|quittung|kassenbon)\b", re.I)
    price = re.compile(r"\s+-?\d+[.,]\d{2}(?:\s*[A-D*])?\s*$")
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw or ignored.match(raw) or not any(c.isalpha() for c in raw):
            continue
        label = price.sub("", raw).strip()
        # A second trailing price is usually the unit price.
        label = price.sub("", label).strip()
        amount = 1
        match = re.match(r"^(\d{1,3})\s*[x×]\s+(.+)$", label, re.I)
        if match:
            amount, label = int(match[1]), match[2]
        label = label[:100]
        if not label or not any(c.isalpha() for c in label):
            continue
        rows.append({"label": label, "raw": raw[:300], "quantity": amount if 1 <= amount <= 999 else 1})
        if len(rows) > MAX_ROWS:
            raise ValueError("Mehr als 60 moegliche Zeilen. Bitte den Beleg in kleinere Abschnitte aufteilen.")
    if not rows:
        raise ValueError("Keine moeglichen Artikel erkannt. Bitte den Belegtext pruefen oder zeilenweise einfuegen.")
    return rows
