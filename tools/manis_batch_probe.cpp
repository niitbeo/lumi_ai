#include <dlfcn.h>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace {

constexpr const char* kFramework =
    "/Applications/Kumoo.app/Contents/Frameworks/Manis.framework/Versions/A/Manis";

template <typename T>
T symbol(void* handle, const char* name) {
  return reinterpret_cast<T>(dlsym(handle, name));
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
  if (argc != 6) {
    std::cerr << "usage: manis_batch_probe <model_root> <cache_dir> <device> "
                 "<dtype> <layout>\n";
    return 2;
  }

  const std::filesystem::path root = argv[1];
  const std::filesystem::path cache_dir = argv[2];
  const int device = std::stoi(argv[3]);
  const int dtype = std::stoi(argv[4]);
  const int layout = std::stoi(argv[5]);

  std::error_code error;
  std::filesystem::create_directories(cache_dir, error);
  if (error) {
    std::cerr << "cannot create cache directory: " << error.message() << "\n";
    return 2;
  }

  void* handle = dlopen(kFramework, RTLD_NOW | RTLD_LOCAL);
  if (!handle) {
    std::cerr << "dlopen failed: " << dlerror() << "\n";
    return 2;
  }

  using CheckFn = bool (*)(const unsigned char*, unsigned int);
  using SetCacheFn = void (*)(const char*, bool);
  using CacheFileFn = bool (*)(const char*, int, int, int);
  const auto check =
      symbol<CheckFn>(handle, "_ZN5manis15CheckModelValidEPKhj");
  const auto set_cache =
      symbol<SetCacheFn>(handle, "_ZN5manis17SetGlobalCacheDirEPKcb");
  const auto cache_file = symbol<CacheFileFn>(
      handle,
      "_ZN5manis10CacheModelEPKcNS_10DeviceTypeENS_8DataTypeENS_10LayoutTypeE");
  if (!check || !set_cache || !cache_file) {
    std::cerr << "required Manis symbols are unavailable\n";
    dlclose(handle);
    return 2;
  }

  set_cache(cache_dir.c_str(), false);
  std::vector<std::filesystem::path> models;
  for (const auto& entry : std::filesystem::recursive_directory_iterator(root)) {
    if (!entry.is_regular_file()) continue;
    const std::string extension = entry.path().extension().string();
    if (extension == ".manis" || extension == ".manisa") {
      models.push_back(entry.path());
    }
  }
  std::sort(models.begin(), models.end());

  int valid_count = 0;
  int cache_count = 0;
  for (size_t index = 0; index < models.size(); ++index) {
    const auto& path = models[index];
    const auto data = read_file(path);
    const bool valid = !data.empty() &&
                       check(data.data(), static_cast<unsigned int>(data.size()));
    const bool cached = valid && cache_file(path.c_str(), device, dtype, layout);
    valid_count += valid ? 1 : 0;
    cache_count += cached ? 1 : 0;
    std::cout << "MODEL " << (index + 1) << "/" << models.size()
              << " valid=" << valid << " cached=" << cached
              << " bytes=" << data.size() << " path=" << path << "\n";
  }

  std::cout << "SUMMARY total=" << models.size() << " valid=" << valid_count
            << " cached=" << cache_count << "\n";
  dlclose(handle);
  return valid_count == static_cast<int>(models.size()) ? 0 : 1;
}
