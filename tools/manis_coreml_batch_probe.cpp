#include <dlfcn.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace manis {
class Net;
class ExtendOptions;
}

int main(int argc, char** argv) {
  if (argc < 2) {
    std::fprintf(stderr, "usage: %s <model_root> [framework]\n", argv[0]);
    return 2;
  }
  const fs::path root = fs::absolute(argv[1]);
  const char* framework = argc > 2
      ? argv[2]
      : "/Applications/Kumoo.app/Contents/Frameworks/Manis.framework/Versions/A/Manis";
  void* handle = dlopen(framework, RTLD_NOW | RTLD_LOCAL);
  if (!handle) {
    std::fprintf(stderr, "dlopen failed: %s\n", dlerror());
    return 3;
  }

  using CreateNet = manis::Net* (*)(manis::ExtendOptions*);
  using ReleaseNet = void (*)(manis::Net*);
  using OptionsCtor = void (*)(manis::ExtendOptions*);
  using OptionsDtor = void (*)(manis::ExtendOptions*);
  using OptionsAddInt = manis::ExtendOptions* (*)(manis::ExtendOptions*, int,
                                                   int);
  auto create = reinterpret_cast<CreateNet>(
      dlsym(handle, "_ZN5manis3Net9CreateNetEPNS_13ExtendOptionsE"));
  auto release = reinterpret_cast<ReleaseNet>(
      dlsym(handle, "_ZN5manis3Net10ReleaseNetEPS0_"));
  auto options_ctor = reinterpret_cast<OptionsCtor>(
      dlsym(handle, "_ZN5manis13ExtendOptionsC1Ev"));
  auto options_dtor = reinterpret_cast<OptionsDtor>(
      dlsym(handle, "_ZN5manis13ExtendOptionsD1Ev"));
  auto options_add_int = reinterpret_cast<OptionsAddInt>(
      dlsym(handle, "_ZN5manis13ExtendOptions3AddENS_14ExtendOptionIDEi"));
  if (!create || !release || !options_ctor || !options_dtor ||
      !options_add_int) {
    std::fprintf(stderr, "required Manis symbols are unavailable\n");
    return 4;
  }

  std::vector<fs::path> models;
  for (const auto& entry : fs::recursive_directory_iterator(root)) {
    if (entry.is_regular_file() && entry.path().extension() == ".manisa") {
      models.push_back(entry.path());
    }
  }
  std::sort(models.begin(), models.end());

  std::uint64_t option_storage = 0;
  auto* options = reinterpret_cast<manis::ExtendOptions*>(&option_storage);
  options_ctor(options);
  options_add_int(options, 2, 10);  // NET_OPTION_CFG_DEVICE_TYPE=COREML

  std::size_t loaded_count = 0;
  for (std::size_t index = 0; index < models.size(); ++index) {
    manis::Net* net = create(options);
    bool loaded = false;
    if (net) {
      auto** vtable = *reinterpret_cast<void***>(net);
      using LoadModelPath = bool (*)(manis::Net*, const char*, int);
      auto load_model = reinterpret_cast<LoadModelPath>(vtable[2]);
      const std::string path = models[index].string();
      loaded = load_model(net, path.c_str(), 0);
      release(net);
    }
    loaded_count += loaded ? 1 : 0;
    std::printf("MODEL %zu/%zu loaded=%d path=%s\n", index + 1,
                models.size(), loaded ? 1 : 0, models[index].c_str());
    std::fflush(stdout);
  }

  options_dtor(options);
  dlclose(handle);
  std::printf("SUMMARY total=%zu loaded=%zu\n", models.size(), loaded_count);
  return loaded_count == models.size() ? 0 : 1;
}
