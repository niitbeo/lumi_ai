#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace xcdl {
class VirtualFileSystemFile {
 public:
  VirtualFileSystemFile();
  ~VirtualFileSystemFile();

  bool Open(const std::string& a,
            const std::string& b,
            const std::string& c,
            const std::map<std::string, std::set<std::string>>& targets);
  bool Read(const std::string& key, std::string& out);

 private:
  alignas(16) unsigned char storage_[4096];
};
}  // namespace xcdl

static bool try_read(const std::string& a,
                     const std::string& b,
                     const std::string& c,
                     const std::string& logical_key,
                     const std::map<std::string, std::set<std::string>>& targets,
                     int index) {
  std::cout << "TRY " << index << "\n"
            << "  a=" << a << "\n"
            << "  b=" << b << "\n"
            << "  c=" << c << "\n";
  xcdl::VirtualFileSystemFile vfs;
  bool opened = vfs.Open(a, b, c, targets);
  std::cout << "  open=" << opened << "\n";
  if (!opened) {
    return false;
  }

  std::string data;
  bool read = vfs.Read(logical_key, data);
  std::cout << "  read=" << read << " size=" << data.size() << "\n";
  if (!read || data.empty()) {
    return false;
  }

  std::string out_path = "/private/tmp/cubeo_xcdl_extract_" + std::to_string(index) + ".manis";
  std::ofstream out(out_path, std::ios::binary);
  out.write(data.data(), static_cast<std::streamsize>(data.size()));
  std::cout << "  wrote=" << out_path << "\n";
  return true;
}

int main(int argc, char** argv) {
  if (argc > 3 && std::string(argv[1]) == "--disk") {
    const std::string disk = argv[2];
    const std::string logical_key = argv[3];
    const std::string password = argc > 4 ? argv[4] : "";
    const std::string root = argc > 5 ? argv[5] : "";
    std::map<std::string, std::set<std::string>> targets;
    targets["/SegmentDetectModel"].insert("PhotoMattingAlpha.manis");
    targets["/SegmentDetectModel"].insert("PhotoMattingTrimap.manis");
    targets["/SegmentDetectModel"].insert("PhotoForeGround.manis");
    targets["/SegmentDetectModel"].insert("PhotoSam.manis");
    targets["/"].insert(logical_key);
    return try_read(disk, password, root, logical_key, targets, 99) ? 0 : 2;
  }

  const std::string resources = argc > 1 ? argv[1] : "/Applications/Kumoo.app/Contents/Resources";
  const std::string cache = argc > 2 ? argv[2] : "/private/tmp/cubeo_xcdl_cache";
  const std::string vpk = resources + "/megatron.vpk";
  const std::string conf = resources + "/megatron_conf.vpk";
  const std::string logical_key = "/SegmentDetectModel/PhotoMattingAlpha.manis";

  std::map<std::string, std::set<std::string>> targets;
  targets["/SegmentDetectModel"].insert("PhotoMattingAlpha.manis");
  targets["/SegmentDetectModel"].insert("PhotoMattingTrimap.manis");
  targets["/SegmentDetectModel"].insert("PhotoForeGround.manis");
  targets["/SegmentDetectModel"].insert("PhotoSam.manis");

  std::vector<std::tuple<std::string, std::string, std::string>> attempts = {
      {cache, resources, ""},
      {cache, vpk, ""},
      {cache, conf, ""},
      {resources, cache, ""},
      {vpk, cache, ""},
      {conf, cache, ""},
      {resources, vpk, conf},
      {cache, vpk, conf},
      {vpk, conf, cache},
      {cache, resources, vpk},
      {cache, resources, conf},
      {resources, cache, vpk},
      {resources, cache, conf},
  };

  for (size_t i = 0; i < attempts.size(); ++i) {
    const auto& [a, b, c] = attempts[i];
    if (try_read(a, b, c, logical_key, targets, static_cast<int>(i))) {
      return 0;
    }
  }

  std::cerr << "No VFS attempt could read " << logical_key << "\n";
  return 2;
}
