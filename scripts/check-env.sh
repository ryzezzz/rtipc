#!/usr/bin/env bash
# D1 环境体检：确认这台机器能支撑后续 D2~D10 的工作。
# 用法： bash scripts/check-env.sh
set -uo pipefail

pass=0
warn=0
fail=0
ok()   { printf '  [ OK ]   %s\n' "$1"; pass=$((pass + 1)); }
bad()  { printf '  [FAIL]   %s\n' "$1"; fail=$((fail + 1)); }
meh()  { printf '  [WARN]   %s\n' "$1"; warn=$((warn + 1)); }
info() { printf '  ----     %s\n' "$1"; }

echo "== 工具链 =="
for t in cmake ninja g++ git; do
  if command -v "$t" >/dev/null 2>&1; then
    ok "$t: $("$t" --version 2>/dev/null | head -1)"
  else
    bad "$t 未安装"
  fi
done

cmake_ver="$(cmake --version 2>/dev/null | head -1 | awk '{print $3}')"
if [ -n "${cmake_ver:-}" ]; then
  if [ "$(printf '%s\n' 3.20 "$cmake_ver" | sort -V | head -1)" = "3.20" ]; then
    ok "cmake 版本满足 >= 3.20（$cmake_ver）"
  else
    bad "cmake 版本过低（$cmake_ver），需要 >= 3.20"
  fi
fi

echo "== 编译器 C++20 能力 =="
if command -v g++ >/dev/null 2>&1; then
  probe="$(mktemp /tmp/mw_probe_XXXXXX.cpp)"
  cat >"$probe" <<'EOF'
#include <concepts>
#include <span>
#include <version>
#if !defined(__cpp_lib_span) || __cpp_lib_span < 202002L
#error "no std::span"
#endif
template <std::integral T>
constexpr T twice(T v) { return v * 2; }
int main() { return twice(21) == 42 ? 0 : 1; }
EOF
  if g++ -std=c++20 -fsyntax-only "$probe" >/dev/null 2>&1; then
    ok "g++ 支持 C++20（concepts / std::span）"
  else
    bad "g++ 的 C++20 支持不完整，请安装 g++-12 并使用 CXX=g++-12"
  fi
  rm -f "$probe"
fi

echo "== 内核与实时能力 =="
info "内核版本: $(uname -r)"
if grep -q 'CONFIG_PREEMPT_RT=y' "/boot/config-$(uname -r)" 2>/dev/null; then
  ok "PREEMPT_RT 已启用"
else
  meh "未检测到 PREEMPT_RT（D1 阶段正常，D7 需要）"
fi
info "cmdline: $(cat /proc/cmdline 2>/dev/null || echo n/a)"
if grep -qE 'isolcpus|nohz_full' /proc/cmdline 2>/dev/null; then
  ok "已配置 CPU 隔离参数"
else
  meh "尚未配置 isolcpus / nohz_full（D7 需要）"
fi

echo "== 观测能力 =="
for t in cyclictest perf bpftrace; do
  if command -v "$t" >/dev/null 2>&1; then
    ok "$t 可用"
  else
    meh "$t 不可用（后续阶段可能需要）"
  fi
done
if [ -r /sys/kernel/btf/vmlinux ]; then
  ok "BTF 可用（eBPF CO-RE 前提）"
else
  meh "无 /sys/kernel/btf/vmlinux，eBPF CO-RE 受限"
fi

echo "== PMU（perf 硬件事件） =="
if grep -q arch_perfmon /proc/cpuinfo 2>/dev/null; then
  ok "/proc/cpuinfo 报告 arch_perfmon"
else
  meh "未报告 arch_perfmon"
fi
if dmesg 2>/dev/null | grep -qi 'Performance Events'; then
  info "$(dmesg 2>/dev/null | grep -i 'Performance Events' | tail -1)"
fi
if command -v perf >/dev/null 2>&1; then
  if perf stat -e cycles -- true >/dev/null 2>&1; then
    ok "perf 硬件事件可用"
  else
    meh "perf 硬件事件不可用（虚拟化环境常见；D4 的 perf c2c 会受影响）"
  fi
fi

printf '\n== 结果：%d 项通过，%d 项警告，%d 项失败 ==\n' "$pass" "$warn" "$fail"
if [ "$fail" -ne 0 ]; then
  exit 1
fi