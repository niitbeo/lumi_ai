#include <cstdio>
#include <cstdlib>
#include <cstring>

extern "C" bool GetLocalTiamatCache(void* context, void* tiamat_operator,
                                     const char* cache_dir,
                                     const char* config_path,
                                     const char* vpk_path,
                                     const char* resource_root,
                                     const char* cache_name, int timeout_ms,
                                     void* out);

int main(int argc, char** argv) {
  if (argc < 5) {
    std::fprintf(stderr,
                 "usage: probe_get_local_tiamat_cache <cache_dir> <config_path> "
                 "<vpk_path> <resource_root> [cache_name]\n");
    return 2;
  }

  alignas(16) unsigned char operator_storage[256];
  std::memset(operator_storage, 0, sizeof(operator_storage));
  void* out = nullptr;
  const char* cache_name = argc > 5 ? argv[5] : "cache_1";

  bool ok = GetLocalTiamatCache(nullptr, operator_storage, argv[1], argv[2],
                                argv[3], argv[4], cache_name, 4000, &out);
  std::printf("ok=%d out=%p\n", ok ? 1 : 0, out);
  return ok ? 0 : 1;
}
