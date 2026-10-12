#include "mw/build_info.hpp"

#include "mw/config.hpp"

#include <cstdio>

namespace mw {
namespace {

#if defined(__clang__)
constexpr const char* kCompiler = "clang " __clang_version__;
#elif defined(__GNUC__)
constexpr const char* kCompiler = "gcc " __VERSION__;
#elif defined(_MSC_VER)
constexpr const char* kCompiler = "msvc";
#else
constexpr const char* kCompiler = "unknown";
#endif

#if defined(MW_SANITIZER)
constexpr bool kSanitizer = true;
#else
constexpr bool kSanitizer = false;
#endif

#ifndef MW_BUILD_TYPE_STR
#define MW_BUILD_TYPE_STR "unknown"
#endif

} // namespace

const BuildInfo& build_info() noexcept {
    static const BuildInfo info{
        kCompiler,
        __cplusplus,
        MW_BUILD_TYPE_STR,
        kCacheLine,
        kSanitizer,
    };
    return info;
}

void print_build_info() {
    const BuildInfo& b = build_info();
    std::printf("rtipc | %s | c++ std %ld | build %s | cache line %zu B | sanitizer %s\n",
                b.compiler,
                b.cxx_std,
                b.build_type,
                b.cache_line,
                b.sanitizer ? "on" : "off");
}

} // namespace mw