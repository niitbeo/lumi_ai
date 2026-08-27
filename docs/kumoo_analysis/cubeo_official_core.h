// ============================================================================
// 🕵️ CUBEO MAC OS FULL C++ HEADER SPECIFICATION (COMPLETE RECOVERY)
// Source: /Applications/Kumoo.app/Contents/MacOS/YunXiu-PC
// Framework: Qt 6.2.8 + ARKernelCPP + Manis Engine + Meitu Lab (MTLab)
// ============================================================================

#ifndef CUBEO_OFFICIAL_CORE_H
#define CUBEO_OFFICIAL_CORE_H

#include <string>
#include <vector>
#include <functional>
#include <memory>

namespace merak {
    struct ComFace;
    struct ComModel;
    struct ComManisEngineInferenceOptions;
    struct ComMatToTensorsOptions;
    struct InnovationIrtToothOptions;
}

namespace manisEngine {
    class ManisEngine {
    public:
        ManisEngine();
        ~ManisEngine();
        bool LoadModel(const char* modelPath);
        bool Forward();
    };
}

namespace arkernelcpp {

    // Các kiểu dữ liệu tương tác gốc của Cubeo
    enum class DataRequireType {
        FACE_LANDMARKS_106 = 1,
        SKIN_SEGMENTATION = 2,
        LIP_SEGMENTATION = 3,
        MESH_3D_FACE = 4,
        BODY_MATTING = 5
    };

    enum class VoidOperationType {
        RESET_ALL = 0,
        CLEAR_CACHE = 1,
        RELOAD_SHADERS = 2
    };

    struct ARKernelFaceDataInterface;
    struct ARKernelBaseDataInterface;
    struct ARKernelPublicInteractionService;
    struct ARKernelPlistDataInterface;
    struct ARKernelGroupDataInterface;
    struct stGroupData;
    struct ExternalFunctionStruct;

    // Class điều khiển Giao diện & Thuật toán UI gốc toàn bộ Cubeo trên Mac
    class ARKernelInterface {
    public:
        ARKernelInterface();
        ~ARKernelInterface();

        // 1. KHỞI TẠO VÀ CẤU HÌNH GIAO DIỆN
        bool Initialize(ARKernelPublicInteractionService* service, const char* resourcePath);
        bool ParserConfiguration(const char* configPath, const char* zipPath, const char* extraPath, int mode);
        bool ParserGroupConfiguration(stGroupData* groupData);
        void GenConfigJSONBuffer();
        void FreeConfigJSONBuffer(void* buffer);

        // 2. SỰ KIỆN TƯƠNG TÁC CHUỘT / TOUCH TRÊN CANVAS UI
        void OnTouchBegin(float x, float y, unsigned int touchId);
        void OnTouchMove(float x, float y, unsigned int touchId);
        void OnTouchEnd(float x, float y, unsigned int touchId);

        // 3. XỬ LÝ RENDER ĐỒ HỌA OPENGL / METAL CHUẨN MAC OS
        int OnDrawFrame(unsigned int fboIn, unsigned int fboOut, int width, int height, unsigned int format, unsigned int target);
        void GenDepthBuffer(unsigned int width, unsigned int height);
        void SetDepthBuffer(void* buffer);
        void DeleteDepthBuffer(void*& buffer);

        // 4. THUẬT TOÁN AI KHUÔN MẶT, BÓP MẶT & RETOUCH
        void FaceInterPoint(ARKernelFaceDataInterface* faceData);
        void GetFaceliftOffsetPoint(float* outX, float* outY, int width, int height);
        void GetTotalFaceState();
        void ResetFaceState();
        void ForceClearFaceDataMemory();
        void SetNativeRuntimeModifyFaceData(const ARKernelFaceDataInterface* faceData);
        const ARKernelFaceDataInterface* GetNativeRuntimeModifyFaceData();

        // 5. QUẢN LÝ CÁC SLIDER THÔNG SỐ VÀ LAYER TRANG ĐIỂM
        void SetAllGroupOrder(std::vector<std::string>& groupNames);
        void SetAllPartsAlpha(float alpha);
        void ReloadPartControl();
        void ReloadPartDefault();
        void UnloadPart();
        void GetLoadedPartControl();
        void DeleteConfiguration(ARKernelPlistDataInterface*& config);
        void DeleteGroupConfiguration(ARKernelGroupDataInterface*& groupConfig);

        // 6. TRUYỀN THÔNG ĐIỆP GIỮA QT 6 UI VÀ CORE C++
        void PostMessage(const std::string& target, const std::string& payload, bool async);
        void PostMessageToScript(const std::string& scriptName, const std::string& params, bool async);
        void UpdateCacheData();
        void UpdateDataRequire();
        void NeedDataRequireType(DataRequireType type);
        void GetErrorCache();

        // 7. CALLBACKS KẾT NỐI HỆ THỐNG
        void SetMessageCallbackFunc(std::function<void(std::string, std::string)> callback);
        void SetPrepareCallbackFunc(std::function<bool(long)> callback);
        void SetDrawFrameCallbackFunc(std::function<int(long, unsigned int, unsigned int, unsigned int, unsigned int, int, int)> callback);
        void SetIsInFreezeCallbackFunc(std::function<void(bool)> callback);
        void SetExternalFunctionStruct(const ExternalFunctionStruct* extStruct);
        void SetNativeData(const ARKernelBaseDataInterface* data);
        void CreateExternalFromPtr(long ptr);
        void VoidOperation(VoidOperationType opType);
        void SetMusicVolume(float volume);
    };
}

#endif // CUBEO_OFFICIAL_CORE_H
