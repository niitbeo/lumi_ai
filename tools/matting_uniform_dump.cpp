// Interposer: capture the OpenGL uniforms of Kumoo's matting shaders at runtime.
// Targets uniforms of `foregroundEstimator`/feathering (names from extracted GLSL):
// input_sigma_space, input_sigma_range, inputKernelSize, inputBlockSize,
// maskChannel, transparentMode, backMode, backColor, dstBackColor,
// input_textureSize. Also captures the matting shader source + small LUT textures.
//
// Uses the macOS __interpose section (works with two-level namespace).
// Build+run: tools/run_matting_uniform_dump.sh   Output: $CUBEO_UNIFORM_DUMP_DIR
#define GL_SILENCE_DEPRECATION 1
#include <OpenGL/gl.h>
#include <dlfcn.h>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <map>
#include <set>
#include <mutex>
#include <fstream>
#include <filesystem>

namespace {
std::mutex g_mu;
GLuint g_cur_prog = 0;
std::map<std::pair<GLuint, GLint>, std::string> g_loc2name;
int g_tex_dump = 0;

const std::set<std::string> kTargets = {
    "input_sigma_space", "input_sigma_range", "inputKernelSize", "inputBlockSize",
    "maskChannel", "transparentMode", "backMode", "backColor", "dstBackColor",
    "input_textureSize", "sigma", "coef",
};
std::filesystem::path dump_dir() {
    const char* e = std::getenv("CUBEO_UNIFORM_DUMP_DIR");
    return (e && *e) ? std::filesystem::path(e)
                     : std::filesystem::path(std::getenv("HOME")) / "cubeo_uniform_dump";
}
void logline(const std::string& s) {
    std::error_code ec; std::filesystem::create_directories(dump_dir(), ec);
    std::ofstream f(dump_dir() / "uniforms.log", std::ios::app);
    f << s << "\n";
}
const std::string* name_for(GLint loc) {
    auto it = g_loc2name.find({g_cur_prog, loc});
    return it == g_loc2name.end() ? nullptr : &it->second;
}
}  // namespace

// ---- hooks (call the real fn directly; __interpose routes external calls here) ----
extern "C" {
GLint  glGetUniformLocation(GLuint, const GLchar*);
void   glUseProgram(GLuint);
void   glUniform1i(GLint, GLint);
void   glUniform1f(GLint, GLfloat);
void   glUniform2f(GLint, GLfloat, GLfloat);
void   glUniform2fv(GLint, GLsizei, const GLfloat*);
void   glUniform4f(GLint, GLfloat, GLfloat, GLfloat, GLfloat);
void   glUniform4fv(GLint, GLsizei, const GLfloat*);
void   glShaderSource(GLuint, GLsizei, const GLchar* const*, const GLint*);
void   glTexImage2D(GLenum, GLint, GLint, GLsizei, GLsizei, GLint, GLenum, GLenum, const void*);
void   glReadPixels(GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void*);
}

static GLint hook_glGetUniformLocation(GLuint program, const GLchar* name) {
    GLint loc = glGetUniformLocation(program, name);
    if (loc >= 0 && name) {
        std::lock_guard<std::mutex> lk(g_mu);
        std::string n(name);
        g_loc2name[{program, loc}] = n;
        if (kTargets.count(n))
            logline("[loc] prog=" + std::to_string(program) + " " + n + " -> " + std::to_string(loc));
    }
    return loc;
}
static void hook_glUseProgram(GLuint program) {
    { std::lock_guard<std::mutex> lk(g_mu); g_cur_prog = program; }
    glUseProgram(program);
}
static void hook_glUniform1i(GLint loc, GLint v) {
    { std::lock_guard<std::mutex> lk(g_mu); if (auto* n = name_for(loc)) if (kTargets.count(*n))
        logline("[1i] prog=" + std::to_string(g_cur_prog) + " " + *n + " = " + std::to_string(v)); }
    glUniform1i(loc, v);
}
static void hook_glUniform1f(GLint loc, GLfloat v) {
    { std::lock_guard<std::mutex> lk(g_mu); if (auto* n = name_for(loc)) if (kTargets.count(*n))
        logline("[1f] prog=" + std::to_string(g_cur_prog) + " " + *n + " = " + std::to_string(v)); }
    glUniform1f(loc, v);
}
static void hook_glUniform2f(GLint loc, GLfloat a, GLfloat b) {
    { std::lock_guard<std::mutex> lk(g_mu); if (auto* n = name_for(loc)) if (kTargets.count(*n))
        logline("[2f] " + *n + " = (" + std::to_string(a) + ", " + std::to_string(b) + ")"); }
    glUniform2f(loc, a, b);
}
static void hook_glUniform2fv(GLint loc, GLsizei c, const GLfloat* v) {
    { std::lock_guard<std::mutex> lk(g_mu); if (auto* n = name_for(loc)) if (kTargets.count(*n) && v)
        logline("[2fv] " + *n + " = (" + std::to_string(v[0]) + ", " + std::to_string(v[1]) + ")"); }
    glUniform2fv(loc, c, v);
}
static void hook_glUniform4f(GLint loc, GLfloat a, GLfloat b, GLfloat c, GLfloat d) {
    { std::lock_guard<std::mutex> lk(g_mu); if (auto* n = name_for(loc)) if (kTargets.count(*n))
        logline("[4f] " + *n + " = (" + std::to_string(a) + ", " + std::to_string(b) + ", " +
                std::to_string(c) + ", " + std::to_string(d) + ")"); }
    glUniform4f(loc, a, b, c, d);
}
static void hook_glUniform4fv(GLint loc, GLsizei cnt, const GLfloat* v) {
    { std::lock_guard<std::mutex> lk(g_mu); if (auto* n = name_for(loc)) if (kTargets.count(*n) && v)
        logline("[4fv] " + *n + " = (" + std::to_string(v[0]) + ", " + std::to_string(v[1]) + ", " +
                std::to_string(v[2]) + ", " + std::to_string(v[3]) + ")"); }
    glUniform4fv(loc, cnt, v);
}
static void hook_glShaderSource(GLuint sh, GLsizei count, const GLchar* const* str, const GLint* len) {
    if (str) {
        std::string src;
        for (GLsizei i = 0; i < count; ++i) if (str[i]) src += str[i];
        if (src.find("foregroundEstimator") != std::string::npos ||
            src.find("featherTable") != std::string::npos ||
            src.find("mattingMask") != std::string::npos) {
            std::error_code ec; std::filesystem::create_directories(dump_dir(), ec);
            std::ofstream f(dump_dir() / ("shader_" + std::to_string(sh) + ".glsl"));
            f << src;
            logline("[shader] captured matting shader id=" + std::to_string(sh) +
                    " (" + std::to_string(src.size()) + " bytes)");
        }
    }
    glShaderSource(sh, count, str, len);
}
static void hook_glTexImage2D(GLenum target, GLint level, GLint internalFormat, GLsizei w, GLsizei h,
                              GLint border, GLenum format, GLenum type, const void* pixels) {
    // small LUTs, OR large single-channel textures (candidate mask/matte upload)
    bool small_lut = ((long)w * h > 0 && (long)w * h <= 2048 && (w <= 4 || h <= 4));
    bool big_mask  = false;   // retouch masks are noise for our purpose; skip
    if (pixels && level == 0 && (small_lut || big_mask)) {
        std::lock_guard<std::mutex> lk(g_mu);
        std::error_code ec; std::filesystem::create_directories(dump_dir(), ec);
        const char* tag = big_mask ? "masktex" : "lut";
        std::string fn = std::string(tag) + "_" + std::to_string(g_tex_dump++) + "_" + std::to_string(w) + "x" +
                         std::to_string(h) + "_fmt" + std::to_string(format) + "_t" + std::to_string(type) + ".bin";
        size_t bytes = (size_t)w * h * (type == GL_FLOAT ? 4 : (format == GL_RGBA ? 4 : 1));
        std::ofstream f(dump_dir() / fn, std::ios::binary);
        f.write((const char*)pixels, bytes);
        logline(std::string("[") + tag + "] " + fn + " bytes=" + std::to_string(bytes));
    }
    glTexImage2D(target, level, internalFormat, w, h, border, format, type, pixels);
}

static int g_rp = 0;
static void hook_glReadPixels(GLint x, GLint y, GLsizei w, GLsizei h, GLenum format, GLenum type, void* pixels) {
    glReadPixels(x, y, w, h, format, type, pixels);      // capture AFTER the real read fills the buffer
    if (!pixels || (long)w * h < 64 * 64) return;
    int ch = (format == GL_RGBA) ? 4 : (format == GL_RGB ? 3 : 1);
    int bpc = (type == GL_FLOAT) ? 4 : 1;
    // Only keep RGBA readbacks that actually have transparency (= a cutout/matte),
    // and skip tiny previews: prefer the largest transparent frames (full-res export).
    bool keep = false;
    if (ch == 4 && bpc == 1 && (long)w * h >= 256 * 256) {
        const unsigned char* p = (const unsigned char*)pixels;
        long n = (long)w * h, transp = 0, semi = 0;
        for (long i = 0; i < n; i += 97) {               // sparse scan for speed
            unsigned char a = p[i * 4 + 3];
            if (a < 250) transp++;
            if (a > 10 && a < 245) semi++;
        }
        keep = (transp > n / 97 / 50);                   // >~2% transparent → a cutout
        if (keep) { std::lock_guard<std::mutex> lk(g_mu);
            logline("[cutout] candidate " + std::to_string(w) + "x" + std::to_string(h) +
                    " semiFrac~" + std::to_string((double)semi * 97 / n)); }
    }
    if (!keep) return;
    std::lock_guard<std::mutex> lk(g_mu);
    std::error_code ec; std::filesystem::create_directories(dump_dir(), ec);
    std::string fn = "cutout_" + std::to_string(g_rp++) + "_" + std::to_string(w) + "x" +
                     std::to_string(h) + "_c" + std::to_string(ch) + "_t" + std::to_string(type) + ".bin";
    std::ofstream f(dump_dir() / fn, std::ios::binary);
    f.write((const char*)pixels, (size_t)w * h * ch * bpc);
    logline("[cutout] SAVED " + fn);
}

// ---- __interpose table ----
#define INTERPOSE(newf, oldf) \
    __attribute__((used)) static struct { const void* r; const void* o; } _ip_##oldf \
        __attribute__((section("__DATA,__interpose"))) = \
        { (const void*)(newf), (const void*)(oldf) };

INTERPOSE(hook_glGetUniformLocation, glGetUniformLocation)
INTERPOSE(hook_glUseProgram,         glUseProgram)
INTERPOSE(hook_glUniform1i,          glUniform1i)
INTERPOSE(hook_glUniform1f,          glUniform1f)
INTERPOSE(hook_glUniform2f,          glUniform2f)
INTERPOSE(hook_glUniform2fv,         glUniform2fv)
INTERPOSE(hook_glUniform4f,          glUniform4f)
INTERPOSE(hook_glUniform4fv,         glUniform4fv)
INTERPOSE(hook_glShaderSource,       glShaderSource)
INTERPOSE(hook_glTexImage2D,         glTexImage2D)
INTERPOSE(hook_glReadPixels,         glReadPixels)

__attribute__((constructor)) static void loaded() {
    std::error_code ec; std::filesystem::create_directories(dump_dir(), ec);
    logline("=== matting_uniform_dump loaded ===");
    fprintf(stderr, "[matting_uniform_dump] active, logging to %s\n", dump_dir().c_str());
}
