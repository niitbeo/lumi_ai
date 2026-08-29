#include <dlfcn.h>

#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace {

constexpr const char* kDefaultFramework =
    "/Applications/Kumoo.app/Contents/Frameworks/Manis.framework/Versions/A/Manis";

template <typename T>
T symbol(void* handle, const char* name) {
  dlerror();
  void* value = dlsym(handle, name);
  if (const char* error = dlerror()) {
    std::cerr << "missing symbol " << name << ": " << error << "\n";
    return nullptr;
  }
  return reinterpret_cast<T>(value);
}

std::vector<unsigned char> read_file(const std::filesystem::path& path) {
  std::ifstream input(path, std::ios::binary | std::ios::ate);
  if (!input) return {};
  const auto size = input.tellg();
  if (size <= 0) return {};
  std::vector<unsigned char> data(static_cast<size_t>(size));
  input.seekg(0);
  input.read(reinterpret_cast<char*>(data.data()), size);
  return data;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 6 || argc > 7) {
    std::cerr << "usage: manis_cache_probe <model> <cache_dir> <device> <dtype> "
                 "<layout> [framework]\n";
    return 2;
  }

  const std::filesystem::path model_path = argv[1];
  const std::filesystem::path cache_dir = argv[2];
  const int device = std::stoi(argv[3]);
  const int dtype = std::stoi(argv[4]);
  const int layout = std::stoi(argv[5]);
  const char* framework = argc == 7 ? argv[6] : kDefaultFramework;

  std::error_code error;
  std::filesystem::create_directories(cache_dir, error);
  if (error) {
    std::cerr << "cannot create cache directory: " << error.message() << "\n";
    return 2;
  }

  void* handle = dlopen(framework, RTLD_NOW | RTLD_LOCAL);
  if (!handle) {
    std::cerr << "dlopen failed: " << dlerror() << "\n";
    return 2;
  }

  using CheckFn = bool (*)(const unsigned char*, unsigned int);
  using SetCacheFn = void (*)(const char*, bool);
  using CacheFileFn = bool (*)(const char*, int, int, int);
  using CacheBufferFn = bool (*)(const unsigned char*, unsigned int, int, int,
                                 int);
  using IsCachedFileFn = bool (*)(const char*, int, int, int);
  using IsSupportFn = bool (*)(int);
  using IsSupportDataFn = bool (*)(int, int);

  const auto check = symbol<CheckFn>(
      handle, "_ZN5manis15CheckModelValidEPKhj");
  const auto set_cache = symbol<SetCacheFn>(
      handle, "_ZN5manis17SetGlobalCacheDirEPKcb");
  const auto cache_file = symbol<CacheFileFn>(
      handle,
      "_ZN5manis10CacheModelEPKcNS_10DeviceTypeENS_8DataTypeENS_10LayoutTypeE");
  const auto cache_buffer = symbol<CacheBufferFn>(
      handle,
      "_ZN5manis10CacheModelEPKhjNS_10DeviceTypeENS_8DataTypeENS_10LayoutTypeE");
  const auto is_cached_file = symbol<IsCachedFileFn>(
      handle,
      "_ZN5manis13IsModelCachedEPKcNS_10DeviceTypeENS_8DataTypeENS_10LayoutTypeE");
  const auto is_support =
      symbol<IsSupportFn>(handle, "_ZN5manis9IsSupportENS_10DeviceTypeE");
  const auto is_support_data = symbol<IsSupportDataFn>(
      handle, "_ZN5manis9IsSupportENS_10DeviceTypeENS_8DataTypeE");
  if (!check || !set_cache || !cache_file || !cache_buffer || !is_cached_file ||
      !is_support || !is_support_data) {
    dlclose(handle);
    return 2;
  }

  const auto data = read_file(model_path);
  if (data.empty()) {
    std::cerr << "cannot read model: " << model_path << "\n";
    dlclose(handle);
    return 2;
  }

  const bool valid = check(data.data(), static_cast<unsigned int>(data.size()));
  std::cout << "valid=" << valid << " bytes=" << data.size() << "\n";
  std::cout << "device_support=" << is_support(device)
            << " device_dtype_support=" << is_support_data(device, dtype)
            << "\n";
  set_cache(cache_dir.c_str(), false);
  const bool before = is_cached_file(model_path.c_str(), device, dtype, layout);
  std::cout << "cached_before=" << before << "\n";
  const bool file_ok = cache_file(model_path.c_str(), device, dtype, layout);
  std::cout << "cache_file=" << file_ok << "\n";
  const bool buffer_ok =
      cache_buffer(data.data(), static_cast<unsigned int>(data.size()), device,
                   dtype, layout);
  std::cout << "cache_buffer=" << buffer_ok << "\n";
  const bool after = is_cached_file(model_path.c_str(), device, dtype, layout);
  std::cout << "cached_after=" << after << "\n";

  dlclose(handle);
  return valid && (file_ok || buffer_ok) ? 0 : 1;
}
