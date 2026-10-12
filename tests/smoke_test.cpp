#include <gtest/gtest.h>

#include "mw/build_info.hpp"
#include "mw/config.hpp"

namespace {

TEST(Config, CacheLineIsSane) {
    EXPECT_GE(mw::kCacheLine, 32u);
    EXPECT_EQ(mw::kCacheLine & (mw::kCacheLine - 1), 0u);
}

TEST(Config, IsPowerOfTwo) {
    EXPECT_TRUE(mw::is_power_of_two(1));
    EXPECT_TRUE(mw::is_power_of_two(1024));
    EXPECT_TRUE(mw::is_power_of_two(1U << 20));
    EXPECT_FALSE(mw::is_power_of_two(0));
    EXPECT_FALSE(mw::is_power_of_two(1000));
}

TEST(BuildInfo, IsReadable) {
    const mw::BuildInfo& b = mw::build_info();
    ASSERT_NE(b.compiler, nullptr);
    ASSERT_NE(b.build_type, nullptr);
    EXPECT_GE(b.cxx_std, 202002L);
    EXPECT_EQ(b.cache_line, mw::kCacheLine);
    mw::print_build_info();
}

} // namespace
