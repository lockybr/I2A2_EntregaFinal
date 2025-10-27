import pdf2image
import pytesseract
from PIL import Image
import os
import shutil

# Test helper: locate sample PDF in repo-relative assets/ directory
HERE = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PDF_PATH = os.path.join(REPO_ROOT, 'assets', 'nota_exemplo.pdf')

# Poppler: use env override or repo-local poppler if present
POPLER_PATH = os.environ.get('POPPLER_PATH') or os.path.join(REPO_ROOT, 'poppler', 'Library', 'bin')
if not os.path.exists(POPLER_PATH):
    POPPLER_PATH = None

# Tesseract: allow override via TESSERACT_CMD env var or system PATH
TESSERACT_PATH = os.environ.get('TESSERACT_CMD') or shutil.which('tesseract')
if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

try:
    images = pdf2image.convert_from_path(PDF_PATH, poppler_path=POPPLER_PATH)
    print(f'PDF convertido em {len(images)} imagem(ns)')
    for idx, img in enumerate(images):
        text = pytesseract.image_to_string(img, lang='por')
        print(f'--- Texto extraído da página {idx+1} ---')
        print(text)
except Exception as e:
    print('Erro no pipeline Poppler/Tesseract:', e)
