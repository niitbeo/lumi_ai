#include <dlfcn.h>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <cstring>
#include <vector>

namespace manis {
class Net;
class Executor;
class ExtendOptions;
}

namespace {

void print_vtable(const char* label, void* object, int count) {
  auto** vtable = *reinterpret_cast<void***>(object);
  std::printf("%s=%p vtable=%p\n", label, object,
              static_cast<void*>(vtable));
  for (int index = 0; index < count; ++index) {
    Dl_info info{};
    const bool found = dladdr(vtable[index], &info) != 0;
    const auto base = found
        ? reinterpret_cast<std::uintptr_t>(info.dli_fbase)
        : 0;
    const auto address = reinterpret_cast<std::uintptr_t>(vtable[index]);
    std::printf("%s.vtable[%02d]=%p offset=0x%llx symbol=%s\n", label,
                index, vtable[index],
                static_cast<unsigned long long>(address - base),
                found && info.dli_sname ? info.dli_sname : "?");
  }
}

void dump_bytes(const char* label, const unsigned char* data, int size) {
  std::printf("%s (%d bytes):\n", label, size);
  for (int offset = 0; offset < size; offset += 16) {
    std::printf("  %04x:", offset);
    for (int index = 0; index < 16 && offset + index < size; ++index) {
      std::printf(" %02x", data[offset + index]);
    }
    std::printf("  ");
    for (int index = 0; index < 16 && offset + index < size; ++index) {
      const unsigned char value = data[offset + index];
      std::putchar(value >= 32 && value < 127 ? value : '.');
    }
    std::putchar('\n');
  }
}

}  // namespace

int main(int argc, char** argv) {
  const char* framework = argc > 1
      ? argv[1]
      : "/Applications/Kumoo.app/Contents/Frameworks/Manis.framework/Versions/A/Manis";
  void* handle = dlopen(framework, RTLD_NOW | RTLD_LOCAL);
  if (!handle) {
    std::fprintf(stderr, "dlopen failed: %s\n", dlerror());
    return 2;
  }

  using CreateNet = manis::Net* (*)(manis::ExtendOptions*);
  using ReleaseNet = void (*)(manis::Net*);
  auto create = reinterpret_cast<CreateNet>(
      dlsym(handle, "_ZN5manis3Net9CreateNetEPNS_13ExtendOptionsE"));
  auto release = reinterpret_cast<ReleaseNet>(
      dlsym(handle, "_ZN5manis3Net10ReleaseNetEPS0_"));
  using CreateExecutor = manis::Executor* (*)(manis::Net*,
                                               manis::ExtendOptions*);
  using ReleaseExecutor = void (*)(manis::Executor*);
  auto create_executor = reinterpret_cast<CreateExecutor>(dlsym(
      handle,
      "_ZN5manis8Executor14CreateExecutorEPNS_3NetEPNS_13ExtendOptionsE"));
  auto release_executor = reinterpret_cast<ReleaseExecutor>(
      dlsym(handle, "_ZN5manis8Executor15ReleaseExecutorEPS0_"));
  if (!create || !release || !create_executor || !release_executor) {
    std::fprintf(stderr, "missing CreateNet/ReleaseNet symbols\n");
    return 3;
  }

  std::uint64_t option_storage = 0;
  manis::ExtendOptions* options = nullptr;
  using OptionsCtor = void (*)(manis::ExtendOptions*);
  using OptionsDtor = void (*)(manis::ExtendOptions*);
  using OptionsAddInt = manis::ExtendOptions* (*)(manis::ExtendOptions*, int,
                                                   int);
  auto options_ctor = reinterpret_cast<OptionsCtor>(
      dlsym(handle, "_ZN5manis13ExtendOptionsC1Ev"));
  auto options_dtor = reinterpret_cast<OptionsDtor>(
      dlsym(handle, "_ZN5manis13ExtendOptionsD1Ev"));
  auto options_add_int = reinterpret_cast<OptionsAddInt>(
      dlsym(handle, "_ZN5manis13ExtendOptions3AddENS_14ExtendOptionIDEi"));
  if (argc > 4) {
    options = reinterpret_cast<manis::ExtendOptions*>(&option_storage);
    options_ctor(options);
    options_add_int(options, std::atoi(argv[3]), std::atoi(argv[4]));
  }

  manis::Net* net = create(options);
  if (!net) {
    std::fprintf(stderr, "CreateNet(nullptr) returned null\n");
    return 4;
  }
  print_vtable("net", net, 48);

  bool loaded = false;
  if (argc > 2) {
    using LoadModelPath = bool (*)(manis::Net*, const char*, int);
    auto** vtable = *reinterpret_cast<void***>(net);
    auto load_model = reinterpret_cast<LoadModelPath>(vtable[2]);
    loaded = load_model(net, argv[2], 0);
    std::printf("load_model=%d path=%s\n", loaded ? 1 : 0, argv[2]);
    if (loaded) {
      using GetNetInfo = bool (*)(manis::Net*, void*);
      using GetTensorInfo = bool (*)(manis::Net*, std::uint32_t, void*);
      alignas(16) unsigned char net_info[0x120]{};
      net_info[8] = 1;
      auto get_net_info = reinterpret_cast<GetNetInfo>(vtable[4]);
      const bool net_info_ok = get_net_info(net, net_info);
      std::printf("get_net_info=%d\n", net_info_ok ? 1 : 0);
      if (net_info_ok) dump_bytes("net_info", net_info, sizeof(net_info));

      auto get_input_info = reinterpret_cast<GetTensorInfo>(vtable[5]);
      auto get_output_info = reinterpret_cast<GetTensorInfo>(vtable[6]);
      for (std::uint32_t index = 0; index < 8; ++index) {
        alignas(16) unsigned char info[0x58]{};
        const bool ok = get_input_info(net, index, info);
        std::printf("get_input_info[%u]=%d\n", index, ok ? 1 : 0);
        if (!ok) break;
        dump_bytes("input_info", info, sizeof(info));
      }
      for (std::uint32_t index = 0; index < 8; ++index) {
        alignas(16) unsigned char info[0x58]{};
        const bool ok = get_output_info(net, index, info);
        std::printf("get_output_info[%u]=%d\n", index, ok ? 1 : 0);
        if (!ok) break;
        dump_bytes("output_info", info, sizeof(info));
      }
    }
  }
  if (loaded) {
    manis::Executor* executor = create_executor(net, options);
    std::printf("create_executor=%p\n", static_cast<void*>(executor));
    if (executor) {
      print_vtable("executor", executor, 48);
      void* implementation = *reinterpret_cast<void**>(
          reinterpret_cast<unsigned char*>(executor) + 0x18);
      if (implementation) {
        print_vtable("executor.impl", implementation, 32);
      }
      void* holder = implementation
          ? *reinterpret_cast<void**>(
                reinterpret_cast<unsigned char*>(implementation) + 0x8)
          : nullptr;
      if (holder) {
        print_vtable("executor.holder", holder, 32);
      }
      release_executor(executor);
    }
  }
  release(net);
  if (options) {
    options_dtor(options);
  }
  dlclose(handle);
  return 0;
}
