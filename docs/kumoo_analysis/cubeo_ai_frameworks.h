// ============================================================================
// 🕵️ CUBEO MAC OS AI FRAMEWORKS C++ HEADER RECOVERY
// Derived from binaries:
//   - libmtaigc.dylib
//   - MTLabEnvdet.framework
// ============================================================================

#ifndef CUBEO_AI_FRAMEWORKS_H
#define CUBEO_AI_FRAMEWORKS_H

#include <string>
#include <vector>
#include <functional>

// ----------------------------------------------------------------------------
// 1. MEITU AIGC (AI GENERATIVE CONTENT) ENGINE - libmtaigc.dylib
// ----------------------------------------------------------------------------
namespace mtaigc {

    struct MTImageAigcStatusResponse {
        int status_code;
        char status_message[256];
        long task_id;
    };

    // Chữ ký bảo mật và mã hóa HMAC-SHA256 gửi request AI Server Meitu
    std::string hmacSHA256(const std::string& data, const std::string& secretKey);
    std::string hexEncodeData(const std::string& inputData);

    // Tiền xử lý & Resize ảnh chuẩn bị đẩy lên AI Model AIGC
    bool resizeImage(const char* inputPath, const char* outputPath, int maxSideLength);
    unsigned char* load_and_resize(const char* imagePath, int* outW, int* outH, int* outChannels, int targetW, int targetH);
    void deleateImageChar(unsigned char* ptr);

    // Parse thông tin ảnh và phản hồi AIGC từ Server
    bool getImageInfo(const char* imagePath, int* width, int* height, int* channels);
    MTImageAigcStatusResponse toMtAigcResponse(MTImageAigcStatusResponse response, long taskId);
}

// ----------------------------------------------------------------------------
// 2. MEITU LAB ENVIRONMENT & HARDWARE DETECTOR - MTLabEnvdet.framework
// ----------------------------------------------------------------------------
namespace mtlab {

    struct GPUInfo {
        char gpu_name[128];
        int vram_size_mb;
        bool supports_metal;
    };

    struct IntelNPUInfo {
        char npu_name[128];
        bool is_available;
    };

    // Phát hiện và chọn lựa phần cứng tăng tốc AI trên macOS (NPU / GPU)
    GPUInfo GetGpuInfo();
    IntelNPUInfo GetIntelNpuInfo();

    // Bộ nhớ Cache dữ liệu suy luận AI cục bộ & Remote
    void GetLocalCache(const char* cacheKey, void** outData, size_t* outSize);
    void GetLocalTiamatCache(const char* key, void** outBuffer);
    void GetRemoteCache(const char* urlKey, void** outData);
    void ReleaseModuleResult(void* resultPtr);
}

#endif // CUBEO_AI_FRAMEWORKS_H
