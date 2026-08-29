#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace PVGIMAGE {
enum PVGCodecType : int {};
enum PVGFormat : int {};

class PVGFrame {
public:
  int getWidth() const;
  int getHeight() const;
  PVGFormat getFormat() const;
  const unsigned char *getPlaneData(int) const;
  int getPlaneLinesize(int) const;
};

class PVGInformation;

class PVGImageCodec {
public:
  static PVGImageCodec *create(const unsigned char *, long, PVGCodecType, bool);
  bool parseInput(const unsigned char *, long, PVGInformation &, bool);
  int dequeueFrame(PVGFrame **);
  int receiveFrame(PVGFrame **);
  void releaseFrame(PVGFrame **);
  void codecClose();
};
} // namespace PVGIMAGE

static std::vector<unsigned char> read_file(const std::filesystem::path &p) {
  std::ifstream in(p, std::ios::binary);
  return {std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
}

static void write_file(const std::filesystem::path &p, const unsigned char *data,
                       size_t len) {
  std::filesystem::create_directories(p.parent_path());
  std::ofstream out(p, std::ios::binary);
  out.write(reinterpret_cast<const char *>(data),
            static_cast<std::streamsize>(len));
}

int main(int argc, char **argv) {
  if (argc < 2) {
    std::cerr << "usage: cubeo_pvg_decode_probe <tile_path> [skip]\n";
    return 2;
  }
  const size_t skip = argc > 2 ? static_cast<size_t>(std::stoull(argv[2])) : 0;
  auto bytes = read_file(argv[1]);
  if (skip >= bytes.size()) {
    std::cerr << "skip too large\n";
    return 2;
  }

  const unsigned char *data = bytes.data() + skip;
  const long len = static_cast<long>(bytes.size() - skip);

  for (int codec_type = 0; codec_type <= 12; ++codec_type) {
    PVGIMAGE::PVGImageCodec *codec = nullptr;
    try {
      codec = PVGIMAGE::PVGImageCodec::create(
          data, len, static_cast<PVGIMAGE::PVGCodecType>(codec_type), false);
    } catch (...) {
      std::cout << "codec=" << codec_type << " create threw\n";
      continue;
    }
    if (!codec) {
      std::cout << "codec=" << codec_type << " create null\n";
      continue;
    }

    PVGIMAGE::PVGFrame *frame = nullptr;
    int rc = -999;
    try {
      rc = codec->receiveFrame(&frame);
    } catch (...) {
      std::cout << "codec=" << codec_type << " receive threw\n";
    }

    if (!frame) {
      try {
        rc = codec->dequeueFrame(&frame);
      } catch (...) {
        std::cout << "codec=" << codec_type << " dequeue threw\n";
      }
    }

    if (!frame) {
      std::cout << "codec=" << codec_type << " rc=" << rc << " frame=null\n";
      try {
        codec->codecClose();
      } catch (...) {
      }
      continue;
    }

    int width = frame->getWidth();
    int height = frame->getHeight();
    int format = static_cast<int>(frame->getFormat());
    int stride = frame->getPlaneLinesize(0);
    const unsigned char *plane = frame->getPlaneData(0);
    std::cout << "codec=" << codec_type << " rc=" << rc << " size=" << width
              << "x" << height << " format=" << format
              << " stride=" << stride << " plane=" << static_cast<const void *>(plane)
              << "\n";

    if (plane && width > 0 && height > 0 && stride > 0 && height < 20000) {
      auto out = std::filesystem::path("/tmp/cubeo_pvg_probe") /
                 ("codec" + std::to_string(codec_type) + "_skip" +
                  std::to_string(skip) + "_fmt" + std::to_string(format) +
                  "_" + std::to_string(width) + "x" + std::to_string(height) +
                  "_stride" + std::to_string(stride) + ".raw");
      write_file(out, plane, static_cast<size_t>(stride) * height);
      std::cout << "wrote " << out << "\n";
    }

    try {
      codec->releaseFrame(&frame);
      codec->codecClose();
    } catch (...) {
    }
  }

  return 0;
}
