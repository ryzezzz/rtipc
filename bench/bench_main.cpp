#include "bench_util.hpp"

#include "mw/build_info.hpp"

#include <cstddef>
#include <cstdint>
#include <cstdio>

int main() {
    mw::print_build_info();

    constexpr std::size_t kIters = 5'000'000;

    // ---- 1) 时钟调用本身的开销（循环里只调用不记录）
    std::uint64_t sink = 0;
    const std::uint64_t t0 = mw::now_ns();
    for (std::size_t i = 0; i < kIters; ++i) {
        sink += mw::now_ns();
    }
    const std::uint64_t t1 = mw::now_ns();
    const double per_call = static_cast<double>(t1 - t0) / static_cast<double>(kIters);

    std::printf("now_ns() 单次开销        : %.2f ns\n", per_call);

    // ---- 2) 两次连续调用的间隔分布 = 时钟读数的粒度
    mw::LatencyHistogram clock_gap(kIters);
    {
        std::uint64_t prev = mw::now_ns();
        for (std::size_t i = 0; i < kIters; ++i) {
            const std::uint64_t cur = mw::now_ns();
            clock_gap.record(cur - prev);
            prev = cur;
        }
    }
    clock_gap.print("两次 now_ns() 间隔");

    // ---- 3) 直方图 record() 一次的开销
    mw::LatencyHistogram hist(kIters);
    const std::uint64_t t2 = mw::now_ns();
    for (std::size_t i = 0; i < kIters; ++i) {
        hist.record(static_cast<std::uint64_t>(i));
    }
    const std::uint64_t t3 = mw::now_ns();
    std::printf("record() 单次开销        : %.2f ns  (n=%zu)\n",
                static_cast<double>(t3 - t2) / static_cast<double>(kIters),
                hist.size());

    std::printf("\n结论：任何小于 %.0f ns 的差异，都不该被当作有效结论。\n", per_call);
    std::printf("(sink=%llu，仅用于阻止编译器把上面的循环优化掉)\n",
                static_cast<unsigned long long>(sink));
    return 0;
}