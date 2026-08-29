# Phân Tích Kỹ Thuật Tính Năng Chụp Ảnh Kết Nối Máy Ảnh (Tethered Shooting) Của Cubeo

Tính năng chụp ảnh kết nối (Tethered Shooting / 联机拍) cho phép các nhiếp ảnh gia studio kết nối máy ảnh kỹ thuật số (Canon, Nikon, Sony...) trực tiếp vào máy tính qua cáp USB. Khi nhấn nút chụp trên máy ảnh, ảnh RAW/JPEG sẽ lập tức được truyền về máy tính, tự động áp dụng các Preset màu AI của Cubeo và hiển thị màn hình lớn cho khách xem.

Dưới đây là tài liệu phân tích kỹ thuật chi tiết về cấu trúc mã nguồn, đặc tả API của nhân C++ native và các kênh giao tiếp IPC.

---

## 1. Kiến Trúc Thư Viện Kết Nối Native (Tethering SDKs)

Tính năng kết nối máy ảnh được thực thi thông qua tệp nhị phân native **`nodegphoto.node`** (thực chất là một thư viện liên kết động DLL C++ đổi đuôi, đặt tại `bin/nodegphoto/nodegphoto.node`). 

Thư viện này tích hợp đồng thời 3 bộ phát triển phần mềm (SDK) lớn để tương thích tối đa với các hãng máy ảnh:

1.  **Canon EOS Digital SDK (`EDSDK.dll`, `EdsImage.dll`):** Bộ SDK chính thức từ Canon, dùng để lấy nét, xem trước (Live View), chụp và kéo ảnh RAW/JPEG tốc độ cao từ dòng máy Canon EOS.
2.  **Nikon SDK (`NkRoyalmile.dll`):** Bộ SDK chính thức từ Nikon, quản lý các máy ảnh Mirrorless/DSLR Nikon.
3.  **Open-source Libgphoto2 (`libgphoto2.dll`, `libgphoto2_port.dll`):** Thư viện mã nguồn mở chuẩn PTP/MTP kết nối với Sony, Fujifilm và các dòng máy kỹ thuật số phổ thông qua giao thức USB tiêu chuẩn.

---

## 2. Bản Đồ File Mã Nguồn Thành Phần (Codebase Architecture)

Trong mã nguồn rã dòng của Cubeo, tính năng này được chia làm các module xử lý chính:

*   **Hằng số IPC:** [module_93513.js](file:///C:/Users/nltruong/magimir_extracted_windows/src/debundled_ui/module_93513.js) (Định nghĩa các kênh truyền tín hiệu IPC, ví dụ: `GPHOTO_CONNECT_CAMERA`).
*   **Electron Main Process:** [module_15353.js](file:///C:/Users/nltruong/magimir_extracted_windows/src/debundled_electron_main/module_15353.js#L5971-L6100) (Nhận yêu cầu IPC từ giao diện, trực tiếp giao tiếp với file nhị phân `nodegphoto.node`).
*   **Giao diện React UI (Renderer):** [debundled_ui](file:///C:/Users/nltruong/magimir_extracted_windows/src/debundled_ui) (Chứa code vẽ giao diện nút kết nối, trích xuất thông số ISO, khẩu độ, tốc độ chụp của máy ảnh lên màn hình).

---

## 3. Đặc Tả Kênh Truyền Thông Tin IPC (Inter-Process Communication)

Giao diện React và tiến trình nền Electron trao đổi dữ liệu máy ảnh thông qua các sự kiện IPC sau:

### A. Quét & Ngắt Quét Thiết Bị Máy Ảnh
*   **Kênh yêu cầu:** `GPHOTO_SCAN_CAMERA_LIST` / `GPHOTO_STOP_SCAN_CAMERA_LIST`
*   **Dữ liệu nhận về:** Mảng JSON danh sách máy ảnh phát hiện được ở cổng USB:
    ```json
    [
      { "model": "Canon EOS R5", "port": "usb:001,005" },
      { "model": "Nikon Z6 II", "port": "usb:001,006" }
    ]
    ```

### B. Kết Nối & Lắng Nghe Máy Ảnh
*   **Kênh yêu cầu:** `GPHOTO_CONNECT_CAMERA`
*   **Dữ liệu gửi đi:** `{ "model": "Canon EOS R5", "port": "usb:001,005" }`
*   **Kênh phản hồi sự kiện:** `ON_GPHOTO_CONNECT_CAMERA_CALLBACK`
    *   *Sự kiện trả về:* `GP_EVENT_FILE_ADDED` (Khi máy ảnh vừa chụp và tạo ra 1 tệp ảnh mới trong thẻ nhớ).

### C. Đồng Bộ Thông Số Máy Ảnh (Định kỳ 1 giây/lần)
*   **Kênh yêu cầu:** `GPHOTO_GET_CAMERA_CONFIG`
*   **Dữ liệu trả về:** 
    ```json
    {
      "iso": "100",
      "aperture": "f/4.0",
      "shutterspeed": "1/200",
      "whitebalance": "Auto",
      "battery": 92
    }
    ```

### D. Tải Tệp Bất Đồng Bộ (Asynchronous Download)
*   **Kênh yêu cầu:** `GPHOTO_DOWNLOAD_FILE`
*   **Dữ liệu gửi đi:** 
    ```json
    {
      "folder": "/store_00010001/DCIM/100CANON",
      "name": "IMG_9999.CR3",
      "localPath": "C:\\Users\\nltruong\\Pictures\\联机拍\\IMG_9999.CR3"
    }
    ```

---

## 4. Đặc Tả API Nhân C++ Native (`nodegphoto.node`)

Nếu bạn tự xây dựng một ứng dụng C++ hoặc Node.js riêng để clone tính năng này, bạn có thể gọi trực tiếp API của module native `nodegphoto.node` như sau:

```javascript
// Nạp nhân native gphoto C++
const gphoto = require('./nodegphoto.node');

// 1. Khởi tạo môi trường gphoto và đường dẫn lưu log
gphoto.initGPhoto(nodegphotoBinaryDirectory, logDirectoryPath);

// 2. Quét tìm thiết bị máy ảnh kết nối qua USB
gphoto.scanCameraList((cameraList) => {
    console.log("Tìm thấy máy ảnh:", cameraList);
});

// 3. Kết nối máy ảnh và đăng ký lắng nghe sự kiện
gphoto.connectCamera("Canon EOS R5", "usb:001,005", (eventType, eventData) => {
    console.log("Loại sự kiện máy ảnh:", eventType); // Ví dụ: GP_EVENT_FILE_ADDED
    console.log("Chi tiết sự kiện:", eventData);       // Chứa thông tin folder và tên file ảnh vừa chụp
    
    if (eventType === "GP_EVENT_FILE_ADDED") {
        // Tự động tải ảnh từ thẻ nhớ máy ảnh về ổ cứng PC
        gphoto.download(eventData.folder, eventData.name, "C:\\Temp\\IMG_0001.JPG", (result) => {
            if (result.bSuccess) {
                console.log("Ảnh đã tải về tại:", result.localPath);
                // Tại đây có thể kích hoạt tiếp chuỗi xử lý AI preset tự động chỉnh màu ảnh!
            }
        });
    }
});

// 4. Lấy các thông số chụp ảnh hiện tại của máy ảnh
const cameraSettings = gphoto.getCameraConfig();
console.log("Thông số máy ảnh:", cameraSettings); // ISO, Khẩu, Tốc, Pin

// 5. Đóng kết nối giải phóng cổng USB
// gphoto.closeCamera();
// gphoto.unInitGPhoto();
```
