import pdf2image
import pytesseract
from PIL import Image
import os

PDF_PATH = r'c:\labz\fiscal-extraction-system-COMPLETO\nota_exemplo.pdf'
POPLER_PATH = r'C:\labz\fiscal-extraction-system-COMPLETO\poppler\Library\bin'
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

try:
    images = pdf2image.convert_from_path(PDF_PATH, poppler_path=POPLER_PATH)
    print(f'PDF convertido em {len(images)} imagem(ns)')
    for idx, img in enumerate(images):
        text = pytesseract.image_to_string(img, lang='por')
        print(f'--- Texto extraído da página {idx+1} ---')
        print(text)
except Exception as e:
    print('Erro no pipeline Poppler/Tesseract:', e)
