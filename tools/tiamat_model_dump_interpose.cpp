#include <dlfcn.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>

static std::string g_dump_dir = []() {
  if (const char* env = getenv("CUBEO_MODEL_DUMP_DIR")) return std::string(env);
  return std::string("/private/tmp/cubeo_model_dump");
}();

static void log_line(const std::string& msg) {
  std::ofstream out(g_dump_dir + "/trace.log", std::ios::app);
  out << msg << std::endl;
}

static uint64_t hash_bytes(const unsigned char* data, size_t size) {
  uint64_t h = 0xcbf29ce484222325ull;
  for (size_t i = 0; i < size; ++i) {
    h ^= data[i];
    h *= 0x100000001b3ull;
  }
  return h;
}

static void dump_bytes(const char* prefix, const char* key,
                       const unsigned char* data, size_t size) {
  if (!data || size == 0) return;
  uint64_t h = hash_bytes(data, size);
  char hex[33];
  snprintf(hex, sizeof(hex), "%016llx", h);
  
  std::string safe_key = key ? key : "null";
  for (auto& c : safe_key) if (c == '/') c = '_';
  
  char first16[33] = {0};
  for (size_t i = 0; i < std::min<size_t>(size, 16); ++i)
    snprintf(&first16[i * 2], 3, "%02x", data[i]);
    
  std::string filename = g_dump_dir + "/" + prefix + "__" + safe_key + "__" +
                         std::to_string(size) + "__" + hex + ".bin";
                         
  log_line(std::string(prefix) + " key=" + safe_key +
           " size=" + std::to_string(size) + " hash=" + hex +
           " first16=" + first16 + " out=" + filename);
           
  int fd = open(filename.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0644);
  if (fd >= 0) {
    write(fd, data, size);
    close(fd);
  }
}

extern "C" const unsigned char* orig_GetModelBufferByType(void*, const char*, unsigned long&, bool) __asm("__ZN4mtai8MTModels20GetModelBufferByTypeEPKcRmb");
extern "C" const unsigned char* orig_GetStrategyBufferByType(void*, const char*, unsigned long&) __asm("__ZN4mtai8MTModels23GetStrategyBufferByTypeEPKcRm");
extern "C" const char* orig_GetModelFileByType(void*, const char*) __asm("__ZN4mtai8MTModels18GetModelFileByTypeEPKc");
extern "C" bool orig_CheckModelValid(const unsigned char*, unsigned int) __asm("__ZN5manis15CheckModelValidEPKhj");
extern "C" bool orig_ParseModelInfo(const unsigned char*, unsigned int, char*, unsigned int) __asm("__ZN5manis14ParseModelInfoEPKhjPcj");
extern "C" bool orig_CacheModelBytes(const unsigned char*, unsigned int, int, int, int) __asm("__ZN5manis10CacheModelEPKhjNS_10DeviceTypeENS_8DataTypeENS_10LayoutTypeE");
extern "C" bool orig_GetLocalTiamatCache(void*, void*, const char*, const char*, const char*, const char*, const char*, int, void*) __asm("_GetLocalTiamatCache");
extern "C" bool orig_VfsOpen(void*, const std::string&, const std::string&, const std::string&, const std::map<std::string, std::set<std::string>>&) __asm("__ZN4xcdl21VirtualFileSystemFile4OpenERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEES9_S9_RKNS1_3mapIS7_NS1_3setIS7_NS1_4lessIS7_EENS5_IS7_EEEESD_NS5_INS1_4pairIS8_SF_EEEEEE");
extern "C" bool orig_VfsRead(void*, const std::string&, std::string&) __asm("__ZN4xcdl21VirtualFileSystemFile4ReadERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEERS7_");
extern "C" bool orig_VfsWrite(void*, const std::string&, std::string) __asm("__ZN4xcdl21VirtualFileSystemFile5WriteERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEES7_");
extern "C" bool orig_ReadFileData(void*, std::string&, const std::string&) __asm("__ZN4xcdl16VirtualFileCache12ReadFileDataERNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEERKS7_");

extern "C" const unsigned char* hook_GetModelBufferByType(void* self, const char* key, unsigned long& size, bool flag) {
  const unsigned char* ret = orig_GetModelBufferByType(self, key, size, flag);
  dump_bytes("MTModels_GetModelBufferByType", key, ret, size);
  return ret;
}

extern "C" const unsigned char* hook_GetStrategyBufferByType(void* self, const char* key, unsigned long& size) {
  const unsigned char* ret = orig_GetStrategyBufferByType(self, key, size);
  dump_bytes("MTModels_GetStrategyBufferByType", key, ret, size);
  return ret;
}

extern "C" const char* hook_GetModelFileByType(void* self, const char* key) {
  const char* ret = orig_GetModelFileByType(self, key);
  log_line(std::string("MTModels_GetModelFileByType key=") + (key ? key : "(null)") + " path=" + (ret ? ret : "(null)"));
  return ret;
}

extern "C" bool hook_CheckModelValid(const unsigned char* data, unsigned int size) {
  dump_bytes("manis_CheckModelValid", "buffer", data, size);
  return orig_CheckModelValid(data, size);
}

extern "C" bool hook_ParseModelInfo(const unsigned char* data, unsigned int size, char* out, unsigned int out_size) {
  dump_bytes("manis_ParseModelInfo", "buffer", data, size);
  return orig_ParseModelInfo(data, size, out, out_size);
}

extern "C" bool hook_CacheModelBytes(const unsigned char* data, unsigned int size, int device, int dtype, int layout) {
  dump_bytes("manis_CacheModelBytes", "buffer", data, size);
  return orig_CacheModelBytes(data, size, device, dtype, layout);
}

extern "C" bool hook_GetLocalTiamatCache(void* a0, void* a1, const char* cache_dir, const char* config_path, const char* vpk_path, const char* a5, const char* cache_name, int timeout, void* out) {
  const bool ok = orig_GetLocalTiamatCache(a0, a1, cache_dir, config_path, vpk_path, a5, cache_name, timeout, out);
  uintptr_t out_value = 0;
  if (out) std::memcpy(&out_value, out, sizeof(out_value));
  log_line(std::string("GetLocalTiamatCache ok=") + (ok ? "1" : "0") + " out_value=" + std::to_string(out_value));
  return ok;
}

extern "C" bool hook_VfsRead(void* self, const std::string& key, std::string& out) {
  const bool ok = orig_VfsRead(self, key, out);
  log_line("xcdl_VfsRead key=" + key + " ok=" + (ok ? "1" : "0"));
  if (ok && key.find("mtface_parsing_makeup") != std::string::npos) {
    dump_bytes("xcdl_VfsRead", key.c_str(), (const unsigned char*)out.data(), out.size());
  }
  return ok;
}

extern "C" bool hook_ReadFileData(void* self, std::string& out, const std::string& key) {
  const bool ok = orig_ReadFileData(self, out, key);
  log_line("xcdl_ReadFileData key=" + key + " ok=" + (ok ? "1" : "0"));
  if (ok && key.find("mtface_parsing_makeup") != std::string::npos) {
    dump_bytes("xcdl_ReadFileData", key.c_str(), (const unsigned char*)out.data(), out.size());
  }
  return ok;
}

struct InterposePair {
  const void* replacement;
  const void* replacee;
};

__attribute__((used)) static const InterposePair kInterposers[] __attribute__((section("__DATA,__interpose"))) = {
    {reinterpret_cast<const void*>(hook_GetModelBufferByType), reinterpret_cast<const void*>(orig_GetModelBufferByType)},
    {reinterpret_cast<const void*>(hook_GetStrategyBufferByType), reinterpret_cast<const void*>(orig_GetStrategyBufferByType)},
    {reinterpret_cast<const void*>(hook_GetModelFileByType), reinterpret_cast<const void*>(orig_GetModelFileByType)},
    {reinterpret_cast<const void*>(hook_CheckModelValid), reinterpret_cast<const void*>(orig_CheckModelValid)},
    {reinterpret_cast<const void*>(hook_ParseModelInfo), reinterpret_cast<const void*>(orig_ParseModelInfo)},
    {reinterpret_cast<const void*>(hook_CacheModelBytes), reinterpret_cast<const void*>(orig_CacheModelBytes)},
    {reinterpret_cast<const void*>(hook_GetLocalTiamatCache), reinterpret_cast<const void*>(orig_GetLocalTiamatCache)},
    {reinterpret_cast<const void*>(hook_VfsRead), reinterpret_cast<const void*>(orig_VfsRead)},
    {reinterpret_cast<const void*>(hook_ReadFileData), reinterpret_cast<const void*>(orig_ReadFileData)},
};
