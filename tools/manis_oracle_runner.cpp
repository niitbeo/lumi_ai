#include <dlfcn.h>

#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace manis {
class Net;
class Executor;
class ExtendOptions;
class Tensor;
}  // namespace manis

namespace {

constexpr const char* kDefaultFramework =
    "/Applications/Kumoo.app/Contents/Frameworks/Manis.framework/Versions/A/Manis";

template <typename T>
T symbol(void* handle, const char* name) {
  return reinterpret_cast<T>(dlsym(handle, name));
}

std::vector<unsigned int> parse_dims(const std::string& value) {
  std::vector<unsigned int> dims;
  std::stringstream stream(value);
  std::string part;
  while (std::getline(stream, part, ',')) {
    if (part.empty()) return {};
    const unsigned long parsed = std::stoul(part);
    if (parsed == 0 || parsed > std::numeric_limits<unsigned int>::max()) {
      return {};
    }
    dims.push_back(static_cast<unsigned int>(parsed));
  }
  return dims;
}

std::vector<unsigned char> read_binary(const fs::path& path) {
  std::ifstream input(path, std::ios::binary | std::ios::ate);
  if (!input) return {};
  const auto end = input.tellg();
  if (end <= 0) return {};
  std::vector<unsigned char> result(static_cast<std::size_t>(end));
  input.seekg(0);
  input.read(reinterpret_cast<char*>(result.data()), end);
  return result;
}

bool write_binary(const fs::path& path, const void* data, std::size_t bytes) {
  std::ofstream output(path, std::ios::binary);
  if (!output || (bytes != 0 && data == nullptr)) return false;
  output.write(reinterpret_cast<const char*>(data),
               static_cast<std::streamsize>(bytes));
  return static_cast<bool>(output);
}

std::string json_escape(const std::string& value) {
  std::string result;
  for (const char ch : value) {
    switch (ch) {
      case '\\': result += "\\\\"; break;
      case '"': result += "\\\""; break;
      case '\n': result += "\\n"; break;
      case '\r': result += "\\r"; break;
      case '\t': result += "\\t"; break;
      default: result += ch; break;
    }
  }
  return result;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 7) {
    std::cerr << "usage: manis_oracle_runner <model.manis> <output-dir> "
                 "<input-name> <input-dims> <input-f32.bin> "
                 "<output-name> [output-name ...] [--framework PATH]\n";
    return 2;
  }

  const fs::path model_path = fs::absolute(argv[1]);
  const fs::path output_dir = fs::absolute(argv[2]);
  const std::string input_name = argv[3];
  const std::vector<unsigned int> input_dims = parse_dims(argv[4]);
  const fs::path input_path = fs::absolute(argv[5]);
  std::vector<std::string> output_names;
  const char* framework = kDefaultFramework;
  bool output_by_name = false;
  bool output_by_id = false;
  for (int index = 6; index < argc; ++index) {
    if (std::string(argv[index]) == "--framework") {
      if (++index >= argc) {
        std::cerr << "--framework requires a path\n";
        return 2;
      }
      framework = argv[index];
    } else if (std::string(argv[index]) == "--output-by-name") {
      output_by_name = true;
    } else if (std::string(argv[index]) == "--output-by-id") {
      output_by_id = true;
    } else {
      output_names.emplace_back(argv[index]);
    }
  }
  if (input_dims.empty() || output_names.empty()) {
    std::cerr << "input dimensions and output names must be non-empty\n";
    return 2;
  }

  std::uint64_t element_count = 1;
  for (const unsigned int dim : input_dims) element_count *= dim;
  const auto input_data = read_binary(input_path);
  const std::uint64_t expected_bytes = element_count * sizeof(float);
  if (input_data.size() != expected_bytes) {
    std::cerr << "input byte count mismatch: expected=" << expected_bytes
              << " actual=" << input_data.size() << "\n";
    return 2;
  }
  std::error_code error;
  fs::create_directories(output_dir, error);
  if (error) {
    std::cerr << "cannot create output directory: " << error.message() << "\n";
    return 2;
  }

  void* handle = dlopen(framework, RTLD_NOW | RTLD_LOCAL);
  if (!handle) {
    std::cerr << "dlopen failed: " << dlerror() << "\n";
    return 3;
  }

  using OptionsCtor = void (*)(manis::ExtendOptions*);
  using OptionsDtor = void (*)(manis::ExtendOptions*);
  using OptionsAddInt = manis::ExtendOptions* (*)(manis::ExtendOptions*, int,
                                                   int);
  using CreateNet = manis::Net* (*)(manis::ExtendOptions*);
  using ReleaseNet = void (*)(manis::Net*);
  using CreateExecutor = manis::Executor* (*)(manis::Net*,
                                               manis::ExtendOptions*);
  using ReleaseExecutor = void (*)(manis::Executor*);
  using TensorCtor = void (*)(manis::Tensor*, const int&, const int&,
                              const int&);
  using TensorDtor = void (*)(manis::Tensor*);
  using TensorAddDim = manis::Tensor* (*)(manis::Tensor*, unsigned int);
  using TensorCopyFromData = manis::Tensor* (*)(manis::Tensor*, const void*);
  using TensorGet = void* (*)(manis::Tensor*);
  using TensorGetDimNum = unsigned int (*)(const manis::Tensor*);
  using TensorGetDim = unsigned int (*)(const manis::Tensor*, unsigned int);
  using TensorGetBytes = std::uint64_t (*)(const manis::Tensor*);
  using TensorGetDataType = int (*)(const manis::Tensor*);
  using TensorData = const void* (*)(const manis::Tensor*);

  const auto options_ctor = symbol<OptionsCtor>(
      handle, "_ZN5manis13ExtendOptionsC1Ev");
  const auto options_dtor = symbol<OptionsDtor>(
      handle, "_ZN5manis13ExtendOptionsD1Ev");
  const auto options_add_int = symbol<OptionsAddInt>(
      handle, "_ZN5manis13ExtendOptions3AddENS_14ExtendOptionIDEi");
  const auto create_net = symbol<CreateNet>(
      handle, "_ZN5manis3Net9CreateNetEPNS_13ExtendOptionsE");
  const auto release_net = symbol<ReleaseNet>(
      handle, "_ZN5manis3Net10ReleaseNetEPS0_");
  const auto create_executor = symbol<CreateExecutor>(
      handle,
      "_ZN5manis8Executor14CreateExecutorEPNS_3NetEPNS_13ExtendOptionsE");
  const auto release_executor = symbol<ReleaseExecutor>(
      handle, "_ZN5manis8Executor15ReleaseExecutorEPS0_");
  const auto tensor_ctor = symbol<TensorCtor>(
      handle,
      "_ZN5manis6TensorC1ERKNS_10DeviceTypeERKNS_10LayoutTypeERKNS_8DataTypeE");
  const auto tensor_dtor = symbol<TensorDtor>(
      handle, "_ZN5manis6TensorD1Ev");
  const auto tensor_add_dim = symbol<TensorAddDim>(
      handle, "_ZN5manis6Tensor6AddDimEj");
  const auto tensor_copy_from_data = symbol<TensorCopyFromData>(
      handle, "_ZN5manis6Tensor12CopyFromDataEPKv");
  const auto tensor_get = symbol<TensorGet>(
      handle, "_ZN5manis6Tensor3GetEv");
  const auto tensor_get_dim_num = symbol<TensorGetDimNum>(
      handle, "_ZNK5manis6Tensor9GetDimNumEv");
  const auto tensor_get_dim = symbol<TensorGetDim>(
      handle, "_ZNK5manis6Tensor6GetDimEj");
  const auto tensor_get_bytes = symbol<TensorGetBytes>(
      handle, "_ZNK5manis6Tensor8GetBytesEv");
  const auto tensor_get_data_type = symbol<TensorGetDataType>(
      handle, "_ZNK5manis6Tensor11GetDataTypeEv");
  const auto tensor_data = symbol<TensorData>(
      handle, "_ZNK5manis6Tensor4DataEv");

  if (!options_ctor || !options_dtor || !options_add_int || !create_net ||
      !release_net || !create_executor || !release_executor || !tensor_ctor ||
      !tensor_dtor || !tensor_add_dim || !tensor_copy_from_data ||
      !tensor_get ||
      !tensor_get_dim_num || !tensor_get_dim || !tensor_get_bytes ||
      !tensor_get_data_type || !tensor_data) {
    std::cerr << "one or more required Manis symbols are unavailable\n";
    dlclose(handle);
    return 3;
  }

  alignas(8) std::uint64_t option_storage = 0;
  auto* options = reinterpret_cast<manis::ExtendOptions*>(&option_storage);
  options_ctor(options);
  options_add_int(options, 2, 1);  // NET_OPTION_CFG_DEVICE_TYPE=CPU.

  manis::Net* net = create_net(options);
  if (!net) {
    std::cerr << "CreateNet failed\n";
    options_dtor(options);
    dlclose(handle);
    return 4;
  }
  auto** net_vtable = *reinterpret_cast<void***>(net);
  using LoadModelPath = bool (*)(manis::Net*, const char*, int);
  const auto load_model = reinterpret_cast<LoadModelPath>(net_vtable[2]);
  if (!load_model(net, model_path.c_str(), 0)) {
    std::cerr << "LoadModel failed: " << model_path << "\n";
    release_net(net);
    options_dtor(options);
    dlclose(handle);
    return 4;
  }

  // Query the authoritative runtime shape. Some legacy converters represented
  // trailing singleton dimensions differently even though the flat element
  // count is identical.
  using GetTensorInfo = bool (*)(manis::Net*, std::uint32_t, void*);
  alignas(16) unsigned char input_info[0x58]{};
  const auto get_input_info =
      reinterpret_cast<GetTensorInfo>(net_vtable[5]);
  if (!get_input_info(net, 0, input_info)) {
    std::cerr << "GetInputTensorInfo(0) failed\n";
    release_net(net);
    options_dtor(options);
    dlclose(handle);
    return 4;
  }
  std::uint32_t runtime_rank = 0;
  std::memcpy(&runtime_rank, input_info + 4, sizeof(runtime_rank));
  if (runtime_rank == 0 || runtime_rank > 16 ||
      8 + runtime_rank * sizeof(std::uint32_t) > sizeof(input_info)) {
    std::cerr << "invalid runtime input rank: " << runtime_rank << "\n";
    release_net(net);
    options_dtor(options);
    dlclose(handle);
    return 4;
  }
  std::vector<unsigned int> runtime_input_dims(runtime_rank);
  std::memcpy(runtime_input_dims.data(), input_info + 8,
              runtime_rank * sizeof(std::uint32_t));
  std::uint64_t runtime_element_count = 1;
  for (const unsigned int dim : runtime_input_dims) runtime_element_count *= dim;
  if (runtime_element_count != element_count) {
    std::cerr << "runtime input element count mismatch: requested="
              << element_count << " runtime=" << runtime_element_count << "\n";
    release_net(net);
    options_dtor(options);
    dlclose(handle);
    return 4;
  }

  manis::Executor* executor = create_executor(net, options);
  if (!executor) {
    std::cerr << "CreateExecutor failed\n";
    release_net(net);
    options_dtor(options);
    dlclose(handle);
    return 4;
  }
  auto** executor_vtable = *reinterpret_cast<void***>(executor);
  using SetTensorByIndex = bool (*)(manis::Executor*, std::uint32_t,
                                    manis::Tensor*);
  using SetTensorByName = bool (*)(manis::Executor*, const char*,
                                   manis::Tensor*);
  using Run = bool (*)(manis::Executor*);
  // Index-based calls avoid requiring the original pre-hash tensor names,
  // which are intentionally absent from the serialized Mizar graph.
  const auto set_input =
      reinterpret_cast<SetTensorByIndex>(executor_vtable[2]);
  const auto set_output =
      reinterpret_cast<SetTensorByIndex>(executor_vtable[4]);
  const auto set_output_by_name =
      reinterpret_cast<SetTensorByName>(executor_vtable[5]);
  void* executor_implementation = *reinterpret_cast<void**>(
      reinterpret_cast<unsigned char*>(executor) + 0x18);
  void* executor_holder = executor_implementation
      ? *reinterpret_cast<void**>(
            reinterpret_cast<unsigned char*>(executor_implementation) + 0x8)
      : nullptr;
  void* internal_executor = executor_holder;
  auto** internal_executor_vtable = internal_executor
      ? *reinterpret_cast<void***>(internal_executor)
      : nullptr;
  using SetInternalTensorById = bool (*)(void*, const char*, void*);
  const auto set_output_by_id = internal_executor_vtable
      ? reinterpret_cast<SetInternalTensorById>(internal_executor_vtable[5])
      : nullptr;
  const auto run = reinterpret_cast<Run>(executor_vtable[8]);

  // These enum values are recovered from Kumoo's own CPU validation path.
  const int device_cpu = 1;
  const int layout_nchw = 0;
  const int data_float32 = 1;
  alignas(8) std::uint64_t input_tensor_storage = 0;
  auto* input_tensor =
      reinterpret_cast<manis::Tensor*>(&input_tensor_storage);
  tensor_ctor(input_tensor, device_cpu, layout_nchw, data_float32);
  for (const unsigned int dim : runtime_input_dims) {
    tensor_add_dim(input_tensor, dim);
  }
  tensor_copy_from_data(input_tensor, input_data.data());
  if (!set_input(executor, 0, input_tensor)) {
    std::cerr << "SetInput failed: " << input_name << "\n";
    tensor_dtor(input_tensor);
    release_executor(executor);
    release_net(net);
    options_dtor(options);
    dlclose(handle);
    return 5;
  }

  std::vector<std::uint64_t> output_tensor_storage(output_names.size(), 0);
  std::vector<manis::Tensor*> output_tensors;
  output_tensors.reserve(output_names.size());
  bool outputs_ok = true;
  for (std::size_t index = 0; index < output_names.size(); ++index) {
    auto* tensor = reinterpret_cast<manis::Tensor*>(
        &output_tensor_storage[index]);
    tensor_ctor(tensor, device_cpu, layout_nchw, data_float32);
    output_tensors.push_back(tensor);
    const bool set_ok = output_by_id && set_output_by_id
        ? set_output_by_id(internal_executor, output_names[index].c_str(),
                           tensor_get(tensor))
        : (output_by_name
               ? set_output_by_name(executor, output_names[index].c_str(), tensor)
               : set_output(executor, static_cast<std::uint32_t>(index), tensor));
    if (!set_ok) {
      std::cerr << "SetOutput failed: " << output_names[index] << "\n";
      outputs_ok = false;
      break;
    }
  }

  bool run_ok = false;
  if (outputs_ok) run_ok = run(executor);
  if (!run_ok) std::cerr << "Run failed\n";

  std::cout << "{\"model\":\"" << json_escape(model_path.string())
            << "\",\"run_ok\":" << (run_ok ? "true" : "false")
            << ",\"runtime_input_shape\":[";
  for (std::size_t index = 0; index < runtime_input_dims.size(); ++index) {
    if (index != 0) std::cout << ',';
    std::cout << runtime_input_dims[index];
  }
  std::cout << "],\"outputs\":[";
  bool dump_ok = run_ok;
  for (std::size_t index = 0; index < output_tensors.size(); ++index) {
    if (index != 0) std::cout << ',';
    const auto* tensor = output_tensors[index];
    const unsigned int rank = tensor_get_dim_num(tensor);
    const std::uint64_t bytes = tensor_get_bytes(tensor);
    const int dtype = tensor_get_data_type(tensor);
    const void* data = tensor_data(tensor);
    const fs::path dump_path = output_dir / (output_names[index] + ".bin");
    const bool wrote = run_ok && write_binary(dump_path, data, bytes);
    dump_ok = dump_ok && wrote;
    std::cout << "{\"name\":\"" << json_escape(output_names[index])
              << "\",\"shape\":[";
    for (unsigned int dim_index = 0; dim_index < rank; ++dim_index) {
      if (dim_index != 0) std::cout << ',';
      std::cout << tensor_get_dim(tensor, dim_index);
    }
    std::cout << "],\"dtype_enum\":" << dtype << ",\"bytes\":"
              << bytes << ",\"path\":\""
              << json_escape(dump_path.string()) << "\",\"wrote\":"
              << (wrote ? "true" : "false") << '}';
  }
  std::cout << "]}\n";

  for (auto* tensor : output_tensors) tensor_dtor(tensor);
  tensor_dtor(input_tensor);
  release_executor(executor);
  release_net(net);
  options_dtor(options);
  dlclose(handle);
  return dump_ok ? 0 : 6;
}
