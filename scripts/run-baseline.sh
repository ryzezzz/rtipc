#!/usr/bin/env bash
# D1 基线采集（自动化版）
#
# 设计原则：机械部分全自动，判断部分留给人。
#   - 原始数据按"一次运行一个目录"归档，可追溯
#   - docs/baseline.md 只在标记块内自动更新，手写的"当日结论与踩坑"永远不会被覆盖
#   - 解析失败会显式报错，而不是把空值或错值写进文档
#
# 用法： bash scripts/run-baseline.sh
#      MW_BUILD_TYPE=Release bash scripts/run-baseline.sh   # 标注本次测量所用构建类型
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TS="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="docs/raw/$TS"
mkdir -p "$RUN_DIR"
echo "== 运行目录：$RUN_DIR =="

MACHINE="$RUN_DIR/machine.txt"

# ------------------------------------------------------------ 1) 机器信息
# 刻意输出 key=value 而不是"人看的报告"：让解析逻辑依赖稳定契约，
# 而不是去正则匹配 lscpu 的排版（排版会随 util-linux 版本变化）。
{
  echo "MACHINE_TIME=$(date -Is)"
  echo "MACHINE_UNAME=$(uname -a)"
  echo "MACHINE_KERNEL=$(uname -r)"
  echo "MACHINE_ARCH=$(uname -m)"
  echo "MACHINE_CMDLINE=$(cat /proc/cmdline 2>/dev/null || echo n/a)"
  echo "MACHINE_CPU_MODEL=$(awk -F: '/^model name/{gsub(/^[ \t]+/,"",$2); print $2; exit}' /proc/cpuinfo)"
  echo "MACHINE_CPU_COUNT=$(nproc)"
  echo "MACHINE_CPU_MHZ=$(awk -F: '/^cpu MHz/{gsub(/^[ \t]+/,"",$2); print $2; exit}' /proc/cpuinfo)"
  echo "MACHINE_MEM_TOTAL=$(awk '/^MemTotal/{print $2" "$3}' /proc/meminfo)"
  echo "MACHINE_VIRT=$(systemd-detect-virt 2>/dev/null || echo unknown)"
  echo "MACHINE_GCC=$(g++ --version 2>/dev/null | head -1 || echo n/a)"
  echo "MACHINE_BUILD_TYPE=${MW_BUILD_TYPE:-RelWithDebInfo}"
} > "$MACHINE"

PREEMPT="$(grep -h 'CONFIG_PREEMPT' "/boot/config-$(uname -r)" 2>/dev/null | tr '\n' ' ' || true)"
echo "MACHINE_PREEMPT=${PREEMPT:-unavailable}" >> "$MACHINE"

if grep -q arch_perfmon /proc/cpuinfo 2>/dev/null; then
  echo "MACHINE_ARCH_PERFMON=yes"
else
  echo "MACHINE_ARCH_PERFMON=no"
fi >> "$MACHINE"

if [ -r /sys/kernel/btf/vmlinux ]; then
  echo "MACHINE_BTF=yes"
else
  echo "MACHINE_BTF=no"
fi >> "$MACHINE"

if command -v perf >/dev/null 2>&1 && perf stat -e cycles -- true >/dev/null 2>&1; then
  echo "MACHINE_PERF_HW=yes"
else
  echo "MACHINE_PERF_HW=no"
fi >> "$MACHINE"

lscpu   > "$RUN_DIR/lscpu.txt"  2>/dev/null || true
free -h > "$RUN_DIR/memory.txt" 2>/dev/null || true
echo "  [ok] 机器信息 -> $MACHINE"

# ------------------------------------------------------------ 2) cyclictest
CYCLIC="$RUN_DIR/cyclictest.txt"
CYCLIC_ARGS=(-m -S -p99 -i1000 -h400 -l100000)

if command -v cyclictest >/dev/null 2>&1; then
  echo "== cyclictest ${CYCLIC_ARGS[*]} =="
  echo "   -m 锁内存 / -S 每核一线程 / -p99 实时优先级 / -i1000 周期1ms / -h400 直方图 / -l 循环数"
  if ! sudo cyclictest "${CYCLIC_ARGS[@]}" | tee "$CYCLIC"; then
    echo "  [warn] cyclictest 执行失败：检查 sudo 权限与 rt-tests 安装"
  fi
  echo "  [ok] cyclictest -> $CYCLIC"
else
  echo "  [warn] 未安装 cyclictest，跳过（sudo apt install -y rt-tests）"
  : > "$CYCLIC"
fi

# ------------------------------------------------------------ 3) mw_bench
BENCH_BIN="build/bench/mw_bench"
BENCH="$RUN_DIR/bench.txt"

if [ -x "$BENCH_BIN" ]; then
  echo "== mw_bench =="
  "$BENCH_BIN" | tee "$BENCH"
  echo "  [ok] mw_bench -> $BENCH"
else
  echo "  [warn] 未找到 $BENCH_BIN，跳过。先构建："
  echo "         CXX=g++-12 cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo"
  echo "         cmake --build build -j"
  : > "$BENCH"
fi

# ------------------------------------------------------------ 4) 渲染报告
echo
RENDER="scripts/render-baseline.py"
if ! command -v python3 >/dev/null 2>&1; then
  echo "  [warn] 未找到 python3，跳过 docs/baseline.md 自动更新"
elif [ ! -f "$RENDER" ]; then
  echo "  [warn] 未找到 $RENDER，跳过 docs/baseline.md 自动更新"
  echo "         请确认渲染脚本已放在 scripts/ 目录下（文件名需与这里一致）"
else
  python3 "$RENDER" "$RUN_DIR"
fi
