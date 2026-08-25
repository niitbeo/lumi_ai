#include <dlfcn.h>

#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace {

using PathSetMap = std::map<std::string, std::set<std::string>>;

template <typename T>
T load_symbol(void* handle, const char* name) {
  dlerror();
  void* symbol = dlsym(handle, name);
  if (const char* error = dlerror()) {
    std::cerr << "dlsym failed for " << name << ": " << error << '\n';
    std::exit(2);
  }
  return reinterpret_cast<T>(symbol);
}

bool write_binary(const std::filesystem::path& path, const std::string& data) {
  std::ofstream stream(path, std::ios::binary);
  stream.write(data.data(), static_cast<std::streamsize>(data.size()));
  return stream.good();
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 4) {
    std::cerr << "usage: kumoo_istar_probe ISTAR_PATH PASSWORD OUTPUT_DIR\n";
    return 64;
  }

  constexpr const char* kLibrary =
      "/Applications/Kumoo.app/Contents/Frameworks/libxcdl.dylib";
  void* handle = dlopen(kLibrary, RTLD_NOW | RTLD_LOCAL);
  if (!handle) {
    std::cerr << "dlopen failed: " << dlerror() << '\n';
    return 2;
  }

  using Constructor = void (*)(void*);
  using Destructor = void (*)(void*);
  using Open = int (*)(void*, const std::string&, const std::string&,
                       const std::string&, const PathSetMap&);
  using Read = int (*)(void*, const std::string&, std::string&);

  const auto construct = load_symbol<Constructor>(
      handle, "_ZN4xcdl21VirtualFileSystemFileC1Ev");
  const auto destruct = load_symbol<Destructor>(
      handle, "_ZN4xcdl21VirtualFileSystemFileD1Ev");
  const auto open = load_symbol<Open>(
      handle,
      "_ZN4xcdl21VirtualFileSystemFile4OpenERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEES9_S9_RKNS1_3mapIS7_NS1_3setIS7_NS1_4lessIS7_EENS5_IS7_EEEESD_NS5_INS1_4pairIS8_SF_EEEEEE");
  const auto read = load_symbol<Read>(
      handle,
      "_ZN4xcdl21VirtualFileSystemFile4ReadERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEERS7_");

  alignas(16) unsigned char object[64] = {};
  construct(object);

  const std::string istar_path = argv[1];
  const std::string password = argv[2];
  const std::string old_cache_path;
  const PathSetMap encrypted_paths;
  const int open_result =
      open(object, istar_path, password, old_cache_path, encrypted_paths);
  std::cout << "open_result=" << open_result << '\n';

  std::filesystem::path output_dir = argv[3];
  std::filesystem::create_directories(output_dir);
  const std::vector<std::string> logical_paths = {
      "/mask/colortransfer/ck.json",
      "mask/colortransfer/ck.json",
      "/mask/colortransfer/colorTransfer.jpg",
      "mask/colortransfer/colorTransfer.jpg",
  };

  for (const auto& logical_path : logical_paths) {
    std::string data;
    const int read_result = read(object, logical_path, data);
    std::cout << "read_result=" << read_result << " size=" << data.size()
              << " path=" << logical_path << '\n';
    if (!data.empty()) {
      const auto filename = std::filesystem::path(logical_path).filename();
      const auto output_path = output_dir / filename;
      if (!write_binary(output_path, data)) {
        std::cerr << "failed to write " << output_path << '\n';
      } else {
        std::cout << "wrote=" << output_path << '\n';
      }
    }
  }

  destruct(object);
  dlclose(handle);
  return open_result == 0 ? 0 : 1;
}
