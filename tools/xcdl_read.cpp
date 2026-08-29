#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>

namespace xcdl {
class VirtualFileSystemFile {
public:
  VirtualFileSystemFile();
  ~VirtualFileSystemFile();
  int Open(const std::string &path, const std::string &password,
           const std::string &root_path,
           const std::map<std::string, std::set<std::string>> &root_paths);
  bool Read(const std::string &key, std::string &out);
  bool CloseUnderlyingHandle();
};
} // namespace xcdl

int main(int argc, char **argv) {
  if (argc < 5) {
    std::cerr << "usage: xcdl_read <istar_path> <password> <root_path> <key> [out]\n";
    return 2;
  }

  const std::string path = argv[1];
  const std::string password = argv[2];
  const std::string root_path = argv[3];
  const std::string key = argv[4];
  const std::string out_path = argc >= 6 ? argv[5] : "";

  std::map<std::string, std::set<std::string>> roots;
  if (!root_path.empty() && root_path != "-") {
    roots[root_path] = {};
  }

  xcdl::VirtualFileSystemFile vfs;
  int open_code = vfs.Open(path, password, root_path == "-" ? "" : root_path, roots);
  if (open_code != 0) {
    std::cerr << "open failed: " << open_code << "\n";
    return 1;
  }

  std::string data;
  if (!vfs.Read(key, data)) {
    std::cerr << "read failed\n";
    vfs.CloseUnderlyingHandle();
    return 1;
  }

  if (!out_path.empty()) {
    std::ofstream out(out_path, std::ios::binary);
    out.write(data.data(), static_cast<std::streamsize>(data.size()));
  } else {
    std::cout.write(data.data(), static_cast<std::streamsize>(data.size()));
  }
  vfs.CloseUnderlyingHandle();
  return 0;
}
