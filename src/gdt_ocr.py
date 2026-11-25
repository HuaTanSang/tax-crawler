import re
from pathlib import Path


def get_captcha(image_path):
    import cv2
    import numpy as np
    import pytesseract

    image_bytes = Path(image_path).read_bytes()
    # Ảnh tải xuống đã chỉ chứa CAPTCHA, nên xử lý toàn ảnh.
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("Không đọc được ảnh CAPTCHA.")
    if image.ndim == 3 and image.shape[2] == 4:
        # PNG của GDT có chữ ở kênh alpha; bỏ alpha sẽ biến toàn ảnh thành đen.
        alpha = image[:, :, 3:4].astype(np.float32) / 255
        image = (image[:, :, :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
    resized = cv2.resize(image, (390, 150))
    # Giữ kích thước và phép giãn nét theo hàm OCR bạn cung cấp.
    grayscale = (
        resized if resized.ndim == 2 else cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    )
    dilation = cv2.dilate(grayscale, np.ones((6, 6), np.uint8), iterations=1)
    # Giữ ngưỡng >= 150 của hàm gốc trên ảnh uint8.
    _, binary = cv2.threshold(dilation, 149, 255, cv2.THRESH_BINARY)
    filtered = cv2.medianBlur(binary, 5)
    # Lọc nhiễu rồi thêm lề trắng phía dưới trước khi đưa cho Tesseract.
    padded = cv2.copyMakeBorder(filtered, 0, 30, 0, 0, cv2.BORDER_CONSTANT, value=255)
    recognized = pytesseract.image_to_string(
        padded, nice=20, config="--psm 7", timeout=15
    )
    captcha = re.sub(r"[^A-Za-z0-9]", "", recognized)
    # Mã OCR trống sẽ khiến caller lấy ảnh mới thay vì gửi request thiếu mã.
    if not captcha:
        raise ValueError("OCR trả về mã CAPTCHA trống.")
    if len(captcha) != 5:
        raise ValueError(f"OCR cần mã CAPTCHA 5 ký tự, đọc được {captcha!r}.")
    return captcha
