#include <fstream>
#include <map>
#include <set>
#include <string>

using StringSet = std::set<std::string>;
using TargetMap = std::map<std::string, StringSet>;

extern "C" bool real_vfs_open(void *, const std::string &, const std::string &,
                              const std::string &, const TargetMap &)
    __asm("__ZN4xcdl21VirtualFileSystemFile4OpenERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEES9_S9_RKNS1_3mapIS7_NS1_3setIS7_NS1_4lessIS7_EENS5_IS7_EEEESD_NS5_INS1_4pairIS8_SF_EEEEEE");
extern "C" bool real_vfs_read(void *, const std::string &, std::string &)
    __asm("__ZN4xcdl21VirtualFileSystemFile4ReadERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEERS7_");
extern "C" bool real_vfs_write(void *, const std::string &, std::string)
    __asm("__ZN4xcdl21VirtualFileSystemFile5WriteERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEES7_");
extern "C" bool real_vfs_flush(void *)
    __asm("__ZN4xcdl21VirtualFileSystemFile11FlushToDiskEv");

static void log_line(const std::string &line) {
  std::ofstream out("/tmp/cubeo_vfs_hook.log", std::ios::app);
  out << line << "\n";
}

static bool hook_vfs_open(void *self, const std::string &a,
                          const std::string &b, const std::string &c,
                          const TargetMap &targets) {
  log_line("[VFS_OPEN] a=" + a + " b=" + b + " c=" + c +
           " targets=" + std::to_string(targets.size()));
  for (const auto &entry : targets) {
    log_line("  [TARGET] " + entry.first + " count=" +
             std::to_string(entry.second.size()));
    for (const auto &value : entry.second) {
      log_line("    [TARGET_FILE] " + value);
    }
  }
  bool ok = real_vfs_open(self, a, b, c, targets);
  log_line(std::string("[VFS_OPEN_RESULT] ") + (ok ? "ok" : "fail"));
  return ok;
}

static bool hook_vfs_read(void *self, const std::string &path,
                          std::string &data) {
  bool ok = real_vfs_read(self, path, data);
  log_line("[VFS_READ] path=" + path + " ok=" + (ok ? std::string("1") : "0") +
           " bytes=" + std::to_string(data.size()));
  return ok;
}

static bool hook_vfs_write(void *self, const std::string &path,
                           std::string data) {
  log_line("[VFS_WRITE] path=" + path + " bytes=" +
           std::to_string(data.size()));
  bool ok = real_vfs_write(self, path, data);
  log_line(std::string("[VFS_WRITE_RESULT] ") + (ok ? "ok" : "fail"));
  return ok;
}

static bool hook_vfs_flush(void *self) {
  log_line("[VFS_FLUSH]");
  bool ok = real_vfs_flush(self);
  log_line(std::string("[VFS_FLUSH_RESULT] ") + (ok ? "ok" : "fail"));
  return ok;
}

#define DYLD_INTERPOSE(_replacement, _replacee)                                \
  __attribute__((used)) static struct {                                        \
    const void *replacement;                                                   \
    const void *replacee;                                                      \
  } _interpose_##_replacement __attribute__((section("__DATA,__interpose"))) = \
      {reinterpret_cast<const void *>(_replacement),                           \
       reinterpret_cast<const void *>(_replacee)}

DYLD_INTERPOSE(hook_vfs_open, real_vfs_open);
DYLD_INTERPOSE(hook_vfs_read, real_vfs_read);
DYLD_INTERPOSE(hook_vfs_write, real_vfs_write);
DYLD_INTERPOSE(hook_vfs_flush, real_vfs_flush);
