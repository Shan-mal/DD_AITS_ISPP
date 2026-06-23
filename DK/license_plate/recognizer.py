import cv2
import easyocr
import numpy as np
import re
from typing import Optional, Tuple

class LicensePlateRecognizer:
    def __init__(self, cascade_path: str = "haarcascade_russian_plate_number.xml"):
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

        plate_roi = image[y1:y2, x1:x2]
        return plate_roi

    def preprocess_for_ocr(self, plate_img: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11,
            C=2
        )
        denoised = cv2.fastNlMeansDenoising(binary, h=10)
        return denoised

    def recognize_text(self, plate_img: np.ndarray) -> Tuple[Optional[str], float]:
        results = self.reader.readtext(plate_img, detail=1, paragraph=False)
        if not results:
            return None, 0.0

        best_text = ""
        best_conf = 0.0
        for (bbox, text, conf) in results:
            clean_text = re.sub(r'[^АВЕКМНОРСТУХавекмнорстухA-Z0-9]', '', text.upper())
            if len(clean_text) >= 6 and conf > best_conf:
                best_text = clean_text
                best_conf = conf

        return best_text if best_text else None, best_conf

    def validate_format(self, plate: str) -> bool:
        pattern = r'^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$'
        return bool(re.match(pattern, plate))

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

        is_valid = self.validate_format(plate_text)
        return {
            "success": True,
            "plate": plate_text,
            "confidence": round(confidence, 2),
            "valid_format": is_valid
        }