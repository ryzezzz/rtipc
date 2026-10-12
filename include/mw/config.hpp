#pragma once

#include <cstddef>
#include <cstdint>
#include <new>
#include <type_traits>

namespace mw {
inline constexpr std::size_t kCacheLine = std::hardware_destructive_interference_size;

static_assert(kCacheLine >= 32);
static_assert((kCacheLine & (kCacheLine - 1)) == 0);

[[nodiscard]] constexpr bool is_power_of_two(std::uint64_t v) noexcept {
    return v != 0 && (v & (v - 1)) == 0;
}

};  // namespace mw

#define MW_CACHE_ALIGNED alignas(::mw::kCacheLine)

#define MW_REQUIRE_POW2(expr)                                           \
    static_assert(::mw::is_power_of_two(static_cast<uint64_t>(expr)),   \
    #expr " must be a power of 2");