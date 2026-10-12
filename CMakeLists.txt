cmake_minimum_required(VERSION 3.20)

project(rtipc
    VERSION 0.1.0
    DESCRIPTION "Realtime IPC middleware for autonomous driving"
    LANGUAGES CXX)

# ------------------------------------------------------------------ 语言标准
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)   # 生成 compile_commands.json，供 clangd / IDE 使用

# ------------------------------------------------------------------ 可开关选项
option(MW_NATIVE      "启用 -march=native（同机编译运行请保持 ON）" ON)
option(MW_WERROR      "把警告当错误（建议在 CI 上打开）"            OFF)
option(MW_BUILD_BENCH "构建基准测试"                              ON)

# ------------------------------------------------------------------ 构建类型
# Debug          : -O0 + ASan + UBSan，找内存与未定义行为问题
# Tsan           : -O1 + TSan，找数据竞争（与 ASan 互斥，所以单独一种）
# RelWithDebInfo : -O2 + 调试符号，日常开发与"真实测量"用这一种（默认）
# Release        : -O3，最终交付
#
# 注意：测量性能/延迟时一定要用 RelWithDebInfo 或 Release。
# Debug 带 sanitizer，指令数与内存访问模式都被改变，测出来的数字没有意义。
set(CMAKE_CXX_FLAGS_DEBUG          "-O0 -g3 -fsanitize=address,undefined -fno-omit-frame-pointer")
set(CMAKE_CXX_FLAGS_TSAN           "-O1 -g -fsanitize=thread -fno-omit-frame-pointer")
set(CMAKE_CXX_FLAGS_RELWITHDEBINFO "-O2 -g -DNDEBUG")
set(CMAKE_CXX_FLAGS_RELEASE        "-O3 -DNDEBUG")

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE RelWithDebInfo CACHE STRING "构建类型" FORCE)
endif()

# ------------------------------------------------------------------ 公共编译选项
add_library(mw_flags INTERFACE)
target_compile_options(mw_flags INTERFACE
    -Wall -Wextra -Wpedantic -Wshadow -Wnon-virtual-dtor)
if(MW_NATIVE)
    target_compile_options(mw_flags INTERFACE -march=native)
endif()
if(MW_WERROR)
    target_compile_options(mw_flags INTERFACE -Werror)
endif()

find_package(Threads REQUIRED)

# ------------------------------------------------------------------ 主库
add_library(mw STATIC
    src/build_info.cpp
)
target_include_directories(mw PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(mw PUBLIC mw_flags Threads::Threads)
target_compile_definitions(mw PRIVATE MW_BUILD_TYPE_STR="${CMAKE_BUILD_TYPE}")

if(CMAKE_BUILD_TYPE STREQUAL "Debug" OR CMAKE_BUILD_TYPE STREQUAL "Tsan")
    target_compile_definitions(mw PRIVATE MW_SANITIZER=1)
endif()

# ------------------------------------------------------------------ 测试与基准
enable_testing()
add_subdirectory(tests)

if(MW_BUILD_BENCH)
    add_subdirectory(bench)
endif()

message(STATUS "rtipc ${PROJECT_VERSION} | build=${CMAKE_BUILD_TYPE} | "
               "cxx=${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION} | "
               "native=${MW_NATIVE}")