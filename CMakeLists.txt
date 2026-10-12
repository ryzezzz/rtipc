cmake_minimum_required(VERSION 3.20)

project(rtipc
    VERSION 0.1.0
    LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(MW_NATIVE      "启用 -march=native（同机编译运行请保持 ON）" ON)
option(MW_WERROR      "把警告当错误（建议在 CI 上打开）"            OFF)
option(MW_BUILD_BENCH "构建基准测试"                                ON)

set(CMAKE_CXX_FLAGS_DEBUG          "-O0 -g3 -fsanitize=address,undefined -fno-omit-frame-pointer")
set(CMAKE_CXX_FLAGS_TSAN           "-O1 -g -fsanitize=thread -fno-omit-frame-pointer")
set(CMAKE_CXX_FLAGS_RELWITHDEBINFO "-O2 -g -DNDEBUG")
set(CMAKE_CXX_FLAGS_RELEASE        "-O3 -DNDEBUG")

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE RelWithDebInfo CACHE STRING "构建类型" FORCE)
endif()

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

add_library(mw STATIC
    src/build_info.cpp
)
target_include_directories(mw PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(mw PUBLIC mw_flags Threads::Threads)
target_compile_definitions(mw PRIVATE MW_BUILD_TYPE_STR="${CMAKE_BUILD_TYPE}")

if(CMAKE_BUILD_TYPE STREQUAL "Debug" OR CMAKE_BUILD_TYPE STREQUAL "Tsan")
    target_compile_definitions(mw PRIVATE MW_SANITIZER=1)
endif()

enable_testing()
add_subdirectory(tests)

if(MW_BUILD_BENCH)
    add_subdirectory(bench)
endif()

message(STATUS "rtipc ${PROJECT_VERSION} | build=${CMAKE_BUILD_TYPE} | "
               "cxx=${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION} | "
               "native=${MW_NATIVE}")