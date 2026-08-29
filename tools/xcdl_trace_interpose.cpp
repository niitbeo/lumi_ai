#include <dlfcn.h>
#include <stdarg.h>
#include <stdio.h>
#include <string>

using OpenFn = int (*)(void *, const std::string *, const std::string *,
                       const std::string *, const void *);
using ReadFn = bool (*)(void *, const std::string *, std::string *);
using CreateFn = int (*)(void **, const std::string *, const std::string *);

extern "C" int real_xcdl_open(void *, const std::string *, const std::string *,
                              const std::string *, const void *)
    asm("__ZN4xcdl21VirtualFileSystemFile4OpenERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEES9_S9_RKNS1_3mapIS7_NS1_3setIS7_NS1_4lessIS7_EENS5_IS7_EEEESD_NS5_INS1_4pairIS8_SF_EEEEEE");
extern "C" bool real_xcdl_read(void *, const std::string *, std::string *)
    asm("__ZN4xcdl21VirtualFileSystemFile4ReadERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEERS7_");
extern "C" int real_istar_create(void **, const std::string *,
                                  const std::string *)
    asm("__ZN4xcdl16IStarDiskFactory6CreateEPPN5istar9IStarDiskERKNSt3__112basic_stringIcNS5_11char_traitsIcEENS5_9allocatorIcEEEESD_");

static FILE *trace_file() {
  static FILE *fp = fopen("/private/tmp/cubeo_xcdl_trace.log", "a");
  return fp ? fp : stderr;
}

static void log_line(const char *fmt, ...) {
  va_list args;
  va_start(args, fmt);
  vfprintf(trace_file(), fmt, args);
  va_end(args);
  fflush(trace_file());
}

__attribute__((constructor)) static void loaded() {
  log_line("XCDL_TRACE_LOADED\n");
}

extern "C" int my_xcdl_open(void *self, const std::string *path,
                            const std::string *password,
                            const std::string *root_path, const void *roots) {
  log_line("XCDL_OPEN path=[%s] password=[%s] root=[%s]\n", path->c_str(),
           password->c_str(), root_path->c_str());
  int rc = real_xcdl_open(self, path, password, root_path, roots);
  log_line("XCDL_OPEN_RET rc=%d path=[%s]\n", rc, path->c_str());
  return rc;
}

extern "C" bool my_xcdl_read(void *self, const std::string *key,
                             std::string *out) {
  log_line("XCDL_READ key=[%s]\n", key->c_str());
  bool ok = real_xcdl_read(self, key, out);
  log_line("XCDL_READ_RET ok=%d key=[%s] bytes=%zu\n", ok ? 1 : 0,
           key->c_str(), out ? out->size() : 0);
  return ok;
}

extern "C" int my_istar_create(void **disk, const std::string *path,
                               const std::string *password) {
  log_line("ISTAR_CREATE path=[%s] password=[%s]\n", path->c_str(),
           password->c_str());
  int rc = real_istar_create(disk, path, password);
  log_line("ISTAR_CREATE_RET rc=%d path=[%s]\n", rc, path->c_str());
  return rc;
}

struct Interpose {
  const void *replacement;
  const void *replacee;
};

__attribute__((used)) static const Interpose interposers[]
    __attribute__((section("__DATA,__interpose"))) = {
        {reinterpret_cast<const void *>(my_xcdl_open),
         reinterpret_cast<const void *>(real_xcdl_open)},
        {reinterpret_cast<const void *>(my_xcdl_read),
         reinterpret_cast<const void *>(real_xcdl_read)},
        {reinterpret_cast<const void *>(my_istar_create),
         reinterpret_cast<const void *>(real_istar_create)},
};
