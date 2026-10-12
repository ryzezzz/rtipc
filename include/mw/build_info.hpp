#pragma once

#include <cstddef>

namespace mw {

struct BuildInfo {
    const char* compiler;    // 编译器与版本
    long cxx_std;            // __cplusplus
    const char* build_type;  // 构建类型字符串
    std::size_t cache_line;  // 本平台缓存行大小
    bool sanitizer;          // 是否带 sanitizer 构建
};

[[nodiscard]] const BuildInfo& build_info() noexcept;

void print_build_info();

};  // namespace mw