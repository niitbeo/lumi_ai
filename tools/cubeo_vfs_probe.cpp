#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace xcdl {
class VirtualFileSystemFile {
  alignas(std::max_align_t) unsigned char opaque_[65536];

public:
  VirtualFileSystemFile();
  ~VirtualFileSystemFile();
  bool Open(const std::string &, const std::string &, const std::string &,
            const std::map<std::string, std::set<std::string>> &);
  bool Read(const std::string &, std::string &);
  bool IsDirectoryExist(const std::string &);
  bool CloseUnderlyingHandle();
};
} // namespace xcdl

static std::string safe_name(std::string value) {
  for (char &ch : value) {
    if (ch == '/' || ch == '\\' || ch == ':' || ch == ' ') {
      ch = '_';
    }
  }
  return value;
}

static bool write_blob(const std::filesystem::path &out_dir,
                       const std::string &label, const std::string &vfs_path,
                       const std::string &data) {
  if (data.empty()) {
    return false;
  }
  std::filesystem::create_directories(out_dir);
  auto out_path = out_dir / (safe_name(label + "_" + vfs_path));
  std::ofstream out(out_path, std::ios::binary);
  out.write(data.data(), static_cast<std::streamsize>(data.size()));
  std::cout << "READ_OK label=" << label << " path=" << vfs_path
            << " bytes=" << data.size() << " out=" << out_path << "\n";
  return true;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    std::cerr << "usage: cubeo_vfs_probe <material_dir> [material_key]\n";
    return 2;
  }

  const std::string material_dir = argv[1];
  const std::string material_key = argc >= 3 ? argv[2] : "";
  const std::filesystem::path out_dir = "/tmp/cubeo_vfs_dump";

  std::vector<std::string> wanted = {
      "/mask/imL",
      "/mask/mlL",
      "/mask/cdL",
      "/mask/cdH",
      "/mask/idH",
      "/mask/mlH",
      "/mask/bdH",
      "/mask/beH",
      "mask/imL",
      "mask/mlL",
      "mask/cdL",
      "mask/cdH",
      "mask/idH",
      "mask/mlH",
      "mask/bdH",
      "mask/beH",
      "/mask/integrated_media.pb",
      "mask/integrated_media.pb",
      ".istar/mask/integrated_media.pb",
      "/.istar/mask/integrated_media.pb",
      ".istar/mask/curtainfill/curtain_mask.png",
      ".istar/mask/curtainfill/curtain_result.png",
      "/.istar/mask/curtainfill/curtain_mask.png",
      "/.istar/mask/curtainfill/curtain_result.png",
      "/mask/curtainfill/curtain_mask.png",
      "/mask/curtainfill/curtain_result.png",
      "mask/curtainfill/curtain_mask.png",
      "mask/curtainfill/curtain_result.png",
      "curtain_mask.png",
      "curtain_result.png",
      "/curtain_mask.png",
      "/curtain_result.png",
      ".istar/mask/curtainfill",
      "/.istar/mask/curtainfill",
      "/mask/curtainfill",
      "mask/curtainfill",
      ".istar/mask/image_seg",
      "/.istar/mask/image_seg",
      "/mask/image_seg",
      "mask/image_seg",
      "/mask/image_seg/",
      "mask/image_seg/",
      "/mask/colortransfer",
      "mask/colortransfer",
      "/mask/beauty",
      "mask/beauty",
      "/",
  };

  std::map<std::string, std::set<std::string>> target_map;
  std::map<std::string, std::set<std::string>> target_map_no_slash;
  std::map<std::string, std::set<std::string>> target_map_exact;
  std::map<std::string, std::set<std::string>> target_map_short;
  std::map<std::string, std::set<std::string>> empty_target_map;
  target_map["/mask"] = {
      "/mask/imL",
      "/mask/mlL",
      "/mask/cdL",
      "/mask/cdH",
      "/mask/idH",
      "/mask/mlH",
      "/mask/bdH",
      "/mask/beH",
      "/mask/integrated_media.pb",
      "/mask/curtainfill/curtain_mask.png",
      "/mask/curtainfill/curtain_result.png",
  };
  target_map["/mask/imL"] = {"/mask/imL"};
  target_map["/mask/mlL"] = {"/mask/mlL"};
  target_map["/mask/cdL"] = {"/mask/cdL"};
  target_map["/mask/cdH"] = {"/mask/cdH"};
  target_map["/mask/idH"] = {"/mask/idH"};
  target_map["/mask/mlH"] = {"/mask/mlH"};
  target_map["/mask/bdH"] = {"/mask/bdH"};
  target_map["/mask/beH"] = {"/mask/beH"};
  target_map["/mask/integrated_media.pb"] = {"/mask/integrated_media.pb"};
  target_map["/mask/curtainfill"] = {
      "/mask/curtainfill/curtain_mask.png",
      "/mask/curtainfill/curtain_result.png",
  };
  target_map["/mask/image_seg"] = {"/mask/image_seg", "/mask/image_seg/"};
  target_map["/"] = {"/mask/curtainfill/curtain_mask.png",
                     "/mask/curtainfill/curtain_result.png",
                     "/mask/integrated_media.pb",
                     "/mask/image_seg"};

  target_map_no_slash["mask"] = {
      "mask/imL",
      "mask/mlL",
      "mask/cdL",
      "mask/cdH",
      "mask/idH",
      "mask/mlH",
      "mask/bdH",
      "mask/beH",
      "mask/integrated_media.pb",
      "mask/curtainfill/curtain_mask.png",
      "mask/curtainfill/curtain_result.png",
  };
  target_map_no_slash["mask/imL"] = {"mask/imL"};
  target_map_no_slash["mask/mlL"] = {"mask/mlL"};
  target_map_no_slash["mask/cdL"] = {"mask/cdL"};
  target_map_no_slash["mask/cdH"] = {"mask/cdH"};
  target_map_no_slash["mask/idH"] = {"mask/idH"};
  target_map_no_slash["mask/mlH"] = {"mask/mlH"};
  target_map_no_slash["mask/bdH"] = {"mask/bdH"};
  target_map_no_slash["mask/beH"] = {"mask/beH"};
  target_map_no_slash["mask/integrated_media.pb"] = {"mask/integrated_media.pb"};
  target_map_no_slash["mask/curtainfill"] = {
      "mask/curtainfill/curtain_mask.png",
      "mask/curtainfill/curtain_result.png",
  };
  target_map_no_slash["mask/image_seg"] = {"mask/image_seg", "mask/image_seg/"};

  target_map_short["/mask/imL"] = {"/mask/imL"};
  target_map_short["/mask/mlL"] = {"/mask/mlL"};
  target_map_short["/mask/cdL"] = {"/mask/cdL"};
  target_map_short["/mask/cdH"] = {"/mask/cdH"};
  target_map_short["/mask/idH"] = {"/mask/idH"};
  target_map_short["/mask/mlH"] = {"/mask/mlH"};
  target_map_short["/mask/bdH"] = {"/mask/bdH"};
  target_map_short["/mask/beH"] = {"/mask/beH"};

  for (const auto &path : wanted) {
    target_map_exact[path] = {path};
  }

  struct OpenTry {
    std::string label;
    std::string a;
    std::string b;
    std::string c;
  };

  const std::string istar_path = material_dir + "/.istar";
  const std::string item_key =
      "mt_builtin_ex_offline_project_data_0_mt_builtin_sample_1";
  const std::string project_key = "mt_builtin_ex_offline_project_data_0";

  std::vector<OpenTry> tries = {
      {"dir_empty_empty", material_dir, "", ""},
      {"dir_istar_empty", material_dir, ".istar", ""},
      {"istar_empty_empty", material_dir + "/.istar", "", ""},
      {"dir_key_empty", material_dir, material_key, ""},
      {"dir_empty_key", material_dir, "", material_key},
      {"dir_istar_key", material_dir, ".istar", material_key},
      {"istar_key_empty", material_dir + "/.istar", material_key, ""},
      {"cache_absistar_key", material_key, istar_path, material_key},
      {"cache_absistar_key_all", material_key, istar_path, material_key},
      {"cache_absistar_key_noslash", material_key, istar_path, material_key},
      {"cache_absistar_key_exact", material_key, istar_path, material_key},
      {"cache_absistar_key_short", material_key, istar_path, material_key},
      {"dir_absistar_key", material_dir, istar_path, material_key},
      {"project_absistar_key", project_key, istar_path, material_key},
      {"item_absistar_key", item_key, istar_path, material_key},
      {"cache_absistar_item", material_key, istar_path, item_key},
      {"cache_absistar_item_all", material_key, istar_path, item_key},
      {"cache_absistar_item_noslash", material_key, istar_path, item_key},
      {"cache_absistar_item_exact", material_key, istar_path, item_key},
      {"cache_absistar_item_short", material_key, istar_path, item_key},
      {"cache_absistar_project", material_key, istar_path, project_key},
      {"cache_absistar_project_all", material_key, istar_path, project_key},
      {"cache_absistar_project_noslash", material_key, istar_path, project_key},
      {"cache_absistar_project_exact", material_key, istar_path, project_key},
      {"cache_absistar_project_short", material_key, istar_path, project_key},
      {"cache_absistar_dotistar", material_key, istar_path, ".istar"},
      {"cache_absistar_apollo", material_key, istar_path, "apollo"},
      {"cache_absistar_colorbyte", material_key, istar_path, "ColorByte"},
  };

  bool any = false;
  for (const auto &path : wanted) {
    std::map<std::string, std::set<std::string>> single_map;
    single_map[path] = {path};
    std::cout << "OPEN_SINGLE path=" << path << "\n";
    xcdl::VirtualFileSystemFile file;
    bool opened = false;
    try {
      opened = file.Open(material_key, istar_path, material_key, single_map);
    } catch (...) {
      std::cout << "OPEN_SINGLE_THROW path=" << path << "\n";
      continue;
    }
    std::cout << "OPEN_SINGLE_RESULT path=" << path << " ok=" << opened
              << "\n";
    if (opened) {
      std::string data;
      bool ok = false;
      try {
        ok = file.Read(path, data);
      } catch (...) {
        std::cout << "READ_SINGLE_THROW path=" << path << "\n";
      }
      std::cout << "READ_SINGLE_RESULT path=" << path << " ok=" << ok
                << " bytes=" << data.size() << "\n";
      if (ok) {
        any = write_blob(out_dir, "single", path, data) || any;
      }
      file.CloseUnderlyingHandle();
    }
  }

  for (const auto &t : tries) {
    std::cout << "OPEN_TRY label=" << t.label << " a=" << t.a << " b=" << t.b
              << " c=" << t.c << "\n";
    xcdl::VirtualFileSystemFile file;
    bool opened = false;
    try {
      const auto &open_map =
          t.label.find("_all") != std::string::npos
              ? empty_target_map
              : (t.label.find("_short") != std::string::npos
                     ? target_map_short
                     : (t.label.find("_noslash") != std::string::npos
                            ? target_map_no_slash
                            : (t.label.find("_exact") != std::string::npos
                                   ? target_map_exact
                                   : target_map)));
      opened = file.Open(t.a, t.b, t.c, open_map);
    } catch (...) {
      std::cout << "OPEN_THROW label=" << t.label << "\n";
      continue;
    }

    std::cout << "OPEN_RESULT label=" << t.label << " ok=" << opened << "\n";
    if (!opened) {
      continue;
    }

    for (const auto &path : wanted) {
      try {
        bool exists = file.IsDirectoryExist(path);
        if (exists) {
          std::cout << "DIR_EXISTS label=" << t.label << " path=" << path
                    << "\n";
        }
      } catch (...) {
      }
      std::string data;
      bool ok = false;
      try {
        ok = file.Read(path, data);
      } catch (...) {
        std::cout << "READ_THROW label=" << t.label << " path=" << path
                  << "\n";
        continue;
      }
      std::cout << "READ_RESULT label=" << t.label << " path=" << path
                << " ok=" << ok << " bytes=" << data.size() << "\n";
      if (ok) {
        any = write_blob(out_dir, t.label, path, data) || any;
      }
    }
    file.CloseUnderlyingHandle();
  }

  return any ? 0 : 1;
}
