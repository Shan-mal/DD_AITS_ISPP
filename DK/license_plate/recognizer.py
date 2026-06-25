import cv2
import easyocr
import numpy as np
import re
from typing import Optional, Tuple

class LicensePlateRecognizer:
    def __init__(self, cascade_path: str = "license_plate/haarcascade_russian_plate_number.xml"):
        self.plate_cascade = cv2.CascadeClassifier(cascade_path)
        self.reader = easyocr.Reader(['ru', 'en'], gpu=False)

    def detect_plate_region(self, image: np.ndarray) -> Optional[np.ndarray]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)

        plates = self.plate_cascade.detectMultiScale(
            enhanced,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(60, 20),
            flags=cv2.CASCADE_SCALE_IMAGE
        )

        if len(plates) == 0:
            return None

        plates = sorted(plates, key=lambda r: r[2] * r[3], reverse=True)
        x, y, w, h = plates[0]

        padding_x = int(w * 0.1)
        padding_y = int(h * 0.2)
        x1 = max(0, x - padding_x)
        y1 = max(0, y - padding_y)
        x2 = min(image.shape[1], x + w + padding_x)
        y2 = min(image.shape[0], y + h + padding_y)

        return image[y1:y2, x1:x2]

    def preprocess_for_ocr(self, plate_img: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11,
            C=2
        )
        return cv2.fastNlMeansDenoising(binary, h=10)

    def _correct_plate_text(self, text: str) -> str:
        """Постобработка: исправление типичных ошибок OCR."""
        # Приводим к верхнему регистру
        text = text.upper().strip()
        # Удаляем все, кроме букв и цифр
        text = re.sub(r'[^А-ЯA-Z0-9]', '', text)
        # Таблица замен (латиница -> кириллица, похожие цифры)
        replacements = {
            'A': 'А', 'B': 'В', 'E': 'Е', 'K': 'К', 'M': 'М', 'H': 'Н',
            'O': 'О', 'P': 'Р', 'C': 'С', 'T': 'Т', 'Y': 'У', 'X': 'Х',
            '0': 'О', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5',
            '6': '6', '7': '7', '8': '8', '9': '9',
            'I': '1', 'L': 'Л', 'Z': '2', 'S': '5', 'G': '6', 'J': '7',
            'З': '3',  # кириллическая З похожа на тройку, но в номере это цифра
            'Ч': '4',  # иногда путают
            'Б': '6',
            'Ь': '6',
        }
        new_text = ''
        for ch in text:
            new_text += replacements.get(ch, ch)
        # Пытаемся восстановить стандартный формат: А123БВ77 (1 буква, 3 цифры, 2 буквы, 2-3 цифры)
        # Если длина 8 или 9, пробуем пересобрать
        if 8 <= len(new_text) <= 9:
            # Предположим, что первая буква, затем 3 цифры, 2 буквы, остальные цифры
            # Просто вернём как есть — валидатор проверит
            pass
        return new_text

    def recognize_text(self, plate_img: np.ndarray) -> Tuple[Optional[str], float]:
        results = self.reader.readtext(plate_img, detail=1, paragraph=False)
        if not results:
            return None, 0.0

        best_text = ""
        best_conf = 0.0
        for (bbox, text, conf) in results:
            clean_text = re.sub(r'[^А-ЯA-Z0-9]', '', text.upper())
            if len(clean_text) >= 6 and conf > best_conf:
                best_text = clean_text
                best_conf = conf

        if not best_text:
            return None, 0.0

        corrected = self._correct_plate_text(best_text)
        return corrected, best_conf

    def validate_format(self, plate: str) -> bool:
        """Гибкая валидация: допускает 8-9 символов, первая буква, потом цифры и буквы."""
        pattern = r'^[А-Я]\d{3}[А-Я]{2}\d{2,3}$'
        if re.match(pattern, plate):
            return True
        # Альтернативный вариант для старых номеров или с ошибкой
        # Просто проверяем, что длина 8-9 и начинается с буквы
        if 8 <= len(plate) <= 9 and plate[0].isalpha():
            return True
        return False

    def run(self, image_path: str) -> dict:
        image = cv2.imread(image_path)
        if image is None:
            return {"success": False, "error": "Не удалось загрузить изображение"}

        plate_roi = self.detect_plate_region(image)
        if plate_roi is None:
            return {"success": False, "error": "Номер не обнаружен"}

        processed = self.preprocess_for_ocr(plate_roi)
        plate_text, confidence = self.recognize_text(processed)

        if plate_text is None:
            plate_text, confidence = self.recognize_text(plate_roi)

        if plate_text is None:
            return {"success": False, "error": "Текст не распознан"}

        # Улучшенная постобработка уже сделана в recognize_text
        is_valid = self.validate_format(plate_text)
        return {
            "success": True,
            "plate": plate_text,
            "confidence": round(float(confidence), 2),
            "valid_format": is_valid
        }