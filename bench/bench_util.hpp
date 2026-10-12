#pragma once

#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <vector>

namespace mw {

using Clock = std::chrono::steady_clock;

[[nodiscard]] inline std::uint64_t now_ns() noexcept {
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch())
            .count());
}

class LatencyHistogram {
public:
    explicit LatencyHistogram(std::size_t reserve_hint = (1u << 20)) {
        samples_.reserve(reserve_hint);
    }

    void record(std::uint64_t ns) { samples_.push_back(ns); }

    void clear() noexcept {
        samples_.clear();
        sorted_ = false;
    }

    [[nodiscard]] std::size_t size() const noexcept { return samples_.size(); }
    [[nodiscard]] bool empty() const noexcept { return samples_.empty(); }

    // 取分位之前必须先排序。重复调用是安全的（幂等）。
    void finish() {
        if (!sorted_) {
            std::sort(samples_.begin(), samples_.end());
            sorted_ = true;
        }
    }

    // 最近秩法（nearest-rank）分位数，p ∈ [0, 100]，调用前需 finish()
    [[nodiscard]] std::uint64_t percentile(double p) const {
        if (samples_.empty()) {
            return 0;
        }
        if (p <= 0.0) {
            return samples_.front();
        }
        if (p >= 100.0) {
            return samples_.back();
        }
        const double rank = (p / 100.0) * static_cast<double>(samples_.size());
        std::size_t idx = static_cast<std::size_t>(rank);
        if (idx > 0) {
            --idx;  // 转成 0 基索引
        }
        if (idx >= samples_.size()) {
            idx = samples_.size() - 1;
        }
        return samples_[idx];
    }

    [[nodiscard]] std::uint64_t min() const { return percentile(0.0); }
    [[nodiscard]] std::uint64_t max() const { return percentile(100.0); }
    [[nodiscard]] std::uint64_t p50() const { return percentile(50.0); }
    [[nodiscard]] std::uint64_t p99() const { return percentile(99.0); }
    [[nodiscard]] std::uint64_t p999() const { return percentile(99.9); }

    [[nodiscard]] double mean() const {
        if (samples_.empty()) {
            return 0.0;
        }
        long double sum = 0.0L;
        for (std::uint64_t v : samples_) {
            sum += static_cast<long double>(v);
        }
        return static_cast<double>(sum / static_cast<long double>(samples_.size()));
    }

    void print(const char* label) {
        finish();
        if (samples_.empty()) {
            std::printf("%-24s (no samples)\n", label);
            return;
        }
        std::printf(
            "%-24s n=%-9zu min=%-6llu p50=%-6llu p99=%-6llu p99.9=%-6llu max=%-8llu mean=%.1f  "
            "(ns)\n",
            label, samples_.size(), static_cast<unsigned long long>(min()),
            static_cast<unsigned long long>(p50()), static_cast<unsigned long long>(p99()),
            static_cast<unsigned long long>(p999()), static_cast<unsigned long long>(max()),
            mean());
    }

private:
    std::vector<std::uint64_t> samples_;
    bool sorted_ = false;
};

};  // namespace mw