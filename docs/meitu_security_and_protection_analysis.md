# Phân Tích Kỹ Thuật Kiến Trúc Bảo Mật & Bản Quyền Của Cubeo

Tài liệu này phân tích chi tiết cơ chế bảo mật bản quyền, giải pháp kiểm tra thiết bị ngoại tuyến (Offline Mode) của Cubeo (MagiMir). Đồng thời, tài liệu chỉ ra **hai lỗ hổng kiến trúc nghiêm trọng** giúp chúng ta giải mã thành công toàn bộ hệ thống mô hình AI cục bộ từ tệp `.lib` sang `.onnx` nguyên bản.

---

## 1. Cơ Chế Chạy Ngoại Tuyến & Xác Thực Thiết Bị (Offline Mode)

Để phục vụ các studio chụp ảnh cưới ngoại cảnh (không có kết nối mạng Internet), Cubeo triển khai chế độ chạy ngoại tuyến có thời hạn đệm:
*   **Thời hạn đệm ngoại tuyến (Offline Grace Period):** Quy định mặc định là **15 ngày** (`cacheValidity: "15天"` trong file `925.js`).
*   **Vân tay thiết bị (Device Fingerprinting):** Trích xuất địa chỉ MAC vật lý của các card mạng đang hoạt động thông qua thư viện native C++ `getmac`: `(0, ct.y)()`.
*   **Quy trình vận hành:**
    *   *Khi có kết nối mạng:* Khi đăng nhập, ứng dụng quét địa chỉ MAC và gửi lên server. Máy chủ ký số (Digital Signature) và trả về một **License Token** lưu trong cache cục bộ.
    *   *Khi mất kết nối mạng:* Mỗi khi mở app, hệ thống đọc License Token cục bộ. Nếu thời gian offline chưa quá 15 ngày, toàn bộ các tính năng AI offline tiếp tục hoạt động. Quá 15 ngày, phần mềm sẽ hiển thị màn hình khóa yêu cầu cắm mạng để kích hoạt lại token mới.

---

## 2. Các Lớp Bảo Vệ Mô Hình AI Của Meitu

Các mô hình học sâu (AI Models) là tài sản trí tuệ đắt giá nhất của Meitu. Họ bảo vệ bằng giải pháp mã hóa hai lớp:
1.  **Mã hóa tệp cục bộ (.lib):** Các mô hình tải về máy khách không lưu dưới dạng tệp `.onnx` thông thường mà được mã hóa xáo trộn và đổi đuôi thành `.lib` (ví dụ: `Ttmscv1B.lib`, `Thmscv1.lib`).
2.  **Giải mã trực tiếp trên RAM (In-Memory Decryption):** Khi chạy suy luận, lõi C++ (`magpie.node`) giải mã các byte mô hình và nạp thẳng vào engine ONNX Runtime / MNN ở bộ nhớ RAM. **Tuyệt đối không bao giờ ghi tệp tin đã giải mã `.onnx` ra đĩa cứng** để ngăn chặn việc sao chép vật lý.

---

## 3. Hai Lỗ Hổng Kiến Trúc Nghiêm Trọng Được Khai Thác

Dù có hệ thống bảo vệ nhị phân chặt chẽ, kiến trúc của Cubeo vẫn tồn tại 2 lo hổng lớn cho phép bẻ khóa toàn bộ:

### Lỗ hổng 1: Lưu trữ khóa giải mã dạng văn bản thô (Plaintext SQLite Leak)
*   **Mô tả:** Hệ thống lưu trữ toàn bộ khóa đối xứng giải mã AES-256 dưới dạng chuỗi văn bản thô Base64 trong bảng **`modelFile`** tại tệp cơ sở dữ liệu SQLite **`base.db`** (nằm ở `AppData\Roaming\MagiMir\database\base.db`). Cơ sở dữ liệu SQLite này hoàn toàn **không được mã hóa** bằng mật khẩu (như SQLCipher).
*   **Cách khai thac:** Chỉ cần dùng thư viện `sqlite3` đọc bảng `modelFile`, trích xuất cột `encryptKey` tương ứng với từng tên file và tiến hành giải mã AES offline hàng loạt.

### Lỗ hổng 2: Rò rỉ bộ nhớ đệm giải mã trong RAM (RAM Memory Residual)
*   **Mô tả:** Khi nhân C++ giải mã tệp `.lib` ra vùng nhớ đệm (RAM Buffer) để nạp vào ONNX Runtime, lập trình viên của Meitu đã quên không xóa trắng vùng nhớ đệm này sau khi nạp xong (thiếu lệnh giải phóng an toàn `memset(buffer, 0, size)`).
*   **Cách khai thac:** Cấu trúc tệp tin `.onnx` gốc đã giải mã vẫn nằm nguyên trên phân vùng bộ nhớ Heap của tiến trình suốt phiên làm việc. Hacker có thể sử dụng các công cụ chụp ảnh bộ nhớ (như ProcDump) để quét RAM của tiến trình và trích xuất trực tiếp mô hình thô thông qua các Byte nhận dạng định dạng (Magic Bytes).

---

## 4. Cơ Chế Bảo Vệ Nhân C++ (`magpie.node`)

Để ngăn chặn việc sao chép file nhị phân `magpie.node` sang các ứng dụng khác:
*   **Xác thực Token chữ ký số:** Các hàm xuất ảnh yêu cầu phải truyền xuống một License Token được ký số bởi máy chủ. Nhân C++ nhúng sẵn Public Key của Meitu để xác thực tính toàn vẹn của Token này.
*   **Quét địa chỉ MAC ở tầng C++:** Lõi `magpie.node` tự động gọi Win32 API `GetAdaptersAddresses` để lấy địa chỉ MAC phần cứng của máy tính và so khớp trực tiếp với địa chỉ MAC được mã hóa bên trong License Token, ngăn chặn việc giả mạo hoặc chia sẻ Token giữa các máy tính khác nhau.

---

## 5. Mã Nguồn Giải Mã Mô Hình Từ Khóa SQLite (Python)

Đoạn mã Python dưới đây mô phỏng phương pháp đọc trực tiếp database `base.db` không khóa, lấy khóa giải mã AES Base64 và tiến hành giải mã tệp `.lib` thành tệp mô hình `.onnx` tiêu chuẩn chạy offline:

```python
import sqlite3
import base64
import os
from Crypto.Cipher import AES

DB_PATH = r"C:\Users\nltruong\AppData\Roaming\MagiMir\database\base.db"
MODEL_DIR = r"C:\Users\nltruong\AppData\Roaming\MagiMir\model"
OUTPUT_DIR = r"C:\Users\nltruong\scratch\decrypted_models"

def decrypt_model(lib_path, out_onnx_path, b64_key):
    """
    Giải mã file .lib thành .onnx bằng thuật toán AES-256-CTR
    """
    # 1. Chuyển khóa Base64 thành byte nhị phân 32 bytes
    aes_key = base64.b64decode(b64_key)
    
    # Đọc toàn bộ dữ liệu file .lib đã mã hóa
    with open(lib_path, "rb") as f:
        encrypted_data = f.read()

    # 2. Khởi tạo thuật toán giải mã AES-256-CTR
    # Thông thường IV cho CTR bắt đầu bằng giá trị 0
    iv = bytes([0] * 16)
    cipher = AES.new(aes_key, AES.MODE_CTR, initial_value=iv, nonce=b"")
    
    # 3. Giải mã dữ liệu
    decrypted_data = cipher.decrypt(encrypted_data)

    # 4. Ghi file ONNX kết quả
    with open(out_onnx_path, "wb") as f:
        f.write(decrypted_data)
    print(f"[+] Giải mã thành công: {os.path.basename(lib_path)} -> {os.path.basename(out_onnx_path)}")

def main():
    if not os.path.exists(DB_PATH):
        print(f"[-] Không tìm thấy database tại: {DB_PATH}")
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Kết nối cơ sở dữ liệu SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Truy vấn danh sách file model và khóa giải mã
        cursor.execute("SELECT fileName, encryptKey FROM modelFile")
        rows = cursor.fetchall()
        
        print(f"[*] Tìm thấy {len(rows)} thông tin mô hình trong database.")
        for row in rows:
            filename, encrypt_key = row
            # Tên file gốc trên ổ đĩa thường đổi đuôi sang .lib
            lib_name = filename.replace(".onnx", ".lib").replace(".xml", ".lib")
            lib_path = os.path.join(MODEL_DIR, lib_name)
            
            if os.path.exists(lib_path):
                out_path = os.path.join(OUTPUT_DIR, filename)
                decrypt_model(lib_path, out_path, encrypt_key)
            else:
                # Tệp chưa được tải về máy khách (Download-on-demand)
                print(f"[i] Bỏ qua (chưa tải về máy): {lib_name}")

    except Exception as e:
        print("[-] Lỗi truy vấn database:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
```
