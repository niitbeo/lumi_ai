#include <array>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace xcdl::xc {
class XCChacha20Decoder {
  alignas(std::max_align_t) unsigned char opaque_[0x120];

public:
  XCChacha20Decoder(const unsigned char *, int, const unsigned char *, int);
  ~XCChacha20Decoder();
  void start();
  std::string decode(const unsigned char *, int);
  void stop();
};

class XCXorDecoder {
  alignas(std::max_align_t) unsigned char opaque_[0x40];

public:
  XCXorDecoder(const unsigned char *, int, const unsigned char *, int);
  ~XCXorDecoder();
  void start();
  std::string decode(const unsigned char *, int);
  void stop();
};
} // namespace xcdl::xc

static std::vector<unsigned char> read_file(const std::filesystem::path &p) {
  std::ifstream in(p, std::ios::binary);
  return {std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
}

static void write_file(const std::filesystem::path &p, const std::string &data) {
  std::filesystem::create_directories(p.parent_path());
  std::ofstream out(p, std::ios::binary);
  out.write(data.data(), static_cast<std::streamsize>(data.size()));
}

static std::string hex_prefix(const std::string &s, size_t n = 16) {
  std::ostringstream os;
  for (size_t i = 0; i < std::min(n, s.size()); ++i) {
    os << std::hex << std::setw(2) << std::setfill('0')
       << (static_cast<unsigned int>(static_cast<unsigned char>(s[i])));
  }
  return os.str();
}

static bool looks_png(const std::string &s) {
  static const std::string png = "\x89PNG\r\n\x1a\n";
  return s.rfind(png, 0) == 0 || s.find("PNG") < 64 || s.find("IDAT") < 256;
}

static std::string safe(std::string s) {
  for (char &c : s) {
    if (!std::isalnum(static_cast<unsigned char>(c))) {
      c = '_';
    }
  }
  return s;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    std::cerr << "usage: cubeo_tile_decode_probe <tile_path>\n";
    return 2;
  }

  auto bytes = read_file(argv[1]);
  if (bytes.size() <= 16) {
    std::cerr << "tile too small\n";
    return 2;
  }

  std::vector<size_t> offsets = {16, 24, 32, 528};
  if (argc >= 3) {
    offsets = {static_cast<size_t>(std::stoull(argv[2]))};
  }

  std::vector<std::string> keys = {
      "82754b7e1448486d8dcc5ca54f13ce29",
      "5c1f841ef7fd4e75b6fba67480a1df77",
      "b1687b6e1f9e4268a3c92529d1c4e3b2",
      "effect.png",
      "effect.png.tile0",
      "ColorByte",
      "apollo",
      ".mt_cb",
  };
  std::vector<std::string> ivs = {
      "",
      "82754b7e1448486d8dcc5ca54f13ce29",
      "5c1f841ef7fd4e75b6fba67480a1df77",
      "b1687b6e1f9e4268a3c92529d1c4e3b2",
      "effect.png",
      "effect.png.tile0",
      std::string(reinterpret_cast<const char *>(bytes.data()), 16),
  };

  const std::filesystem::path out_dir = "/tmp/cubeo_tile_decode_probe";
  bool any = false;
  for (const auto &key : keys) {
    for (const auto &iv : ivs) {
      for (size_t offset : offsets) {
        if (offset >= bytes.size()) {
          continue;
        }
        const unsigned char *payload = bytes.data() + offset;
        const int payload_len = static_cast<int>(bytes.size() - offset);

      try {
        xcdl::xc::XCChacha20Decoder dec(
            reinterpret_cast<const unsigned char *>(key.data()),
            static_cast<int>(key.size()),
            reinterpret_cast<const unsigned char *>(iv.data()),
            static_cast<int>(iv.size()));
        dec.start();
        std::string decoded = dec.decode(payload, payload_len);
        dec.stop();
        std::cout << "CHACHA off=" << offset << " key=" << key
                  << " iv=" << safe(iv)
                  << " len=" << decoded.size()
                  << " head=" << hex_prefix(decoded)
                  << " png=" << looks_png(decoded) << "\n";
        if (looks_png(decoded)) {
          write_file(out_dir / ("chacha_" + safe(key) + "_" + safe(iv) + ".bin"),
                     decoded);
          any = true;
        }
      } catch (...) {
        std::cout << "CHACHA_THROW off=" << offset << " key=" << key
                  << " iv=" << safe(iv) << "\n";
      }

      try {
        xcdl::xc::XCXorDecoder dec(
            reinterpret_cast<const unsigned char *>(key.data()),
            static_cast<int>(key.size()),
            reinterpret_cast<const unsigned char *>(iv.data()),
            static_cast<int>(iv.size()));
        dec.start();
        std::string decoded = dec.decode(payload, payload_len);
        dec.stop();
        std::cout << "XOR off=" << offset << " key=" << key
                  << " iv=" << safe(iv)
                  << " len=" << decoded.size()
                  << " head=" << hex_prefix(decoded)
                  << " png=" << looks_png(decoded) << "\n";
        if (looks_png(decoded)) {
          write_file(out_dir / ("xor_" + safe(key) + "_" + safe(iv) + ".bin"),
                     decoded);
          any = true;
        }
      } catch (...) {
        std::cout << "XOR_THROW off=" << offset << " key=" << key
                  << " iv=" << safe(iv) << "\n";
      }
      }
    }
  }

  return any ? 0 : 1;
}
