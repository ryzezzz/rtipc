#!/usr/bin/env python3
"""把一次基线采集的原始数据渲染进 docs/baseline.md。

设计要点
  1. 只更新标记块之间的内容，块外的一切（手写结论、踩坑记录）原样保留。
  2. 解析不出来的字段绝不瞎填，而是列入"待人工确认"清单并显式打印。
  3. 每次运行都把自己写出的报告冻结一份到 docs/raw/<时间戳>/baseline.md，便于回溯。

关于标记（重要）
  v1 用的是 HTML 注释 `<!-- AUTO:BASELINE:BEGIN -->`。它渲染时不可见，但有一个致命缺点：
  很多工具链（Markdown 预览、编辑器扩展、剪贴板管理器）会把 HTML 注释直接删除，
  于是复制粘贴之后标记常量变成空串，partition() 抛 "ValueError: empty separator"。

  v2 改用 `[//]: # (AUTO:BASELINE:BEGIN)` —— 它是 Markdown 的"链接引用定义"语法，
  渲染时同样不可见，但它是**普通文本**，不会被任何注释剥离逻辑碰到。
  同时保留对旧标记的兼容，便于平滑迁移。
"""
import os
import re
import sys

# 标记候选，按优先级排列；第一个是当前使用的写法，其余为历史兼容
MARKERS = (
    ("[//]: # (AUTO:BASELINE:BEGIN)", "[//]: # (AUTO:BASELINE:END)"),
    ("<!-- AUTO:BASELINE:BEGIN -->", "<!-- AUTO:BASELINE:END -->"),
    ("=== AUTO:BASELINE:BEGIN ===", "=== AUTO:BASELINE:END ==="),
)
DEFAULT_BEGIN, DEFAULT_END = MARKERS[0]

DEFAULT_TEMPLATE = f"""# 系统基线

> 本文件由 `scripts/run-baseline.sh` 自动更新。
> **只有标记块内的内容会被覆盖**；标记块外的手写内容（下方「当日结论与踩坑」）永远不会被触碰。
>
> 标记写成 `[//]: # (AUTO:BASELINE:BEGIN)` 这种形式，有两个原因：
> ① 它是 Markdown 的链接引用定义，渲染时不可见；
> ② 它是普通文本，不会像 HTML 注释那样在复制粘贴时被工具剥离。

{DEFAULT_BEGIN}
（尚无数据。运行： bash scripts/run-baseline.sh ）
{DEFAULT_END}

## 当日结论与踩坑

- 
"""


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def pick_marker(doc):
    """在文档里找出实际使用的标记对，兼容历史写法。"""
    for begin, end in MARKERS:
        if begin and end and begin in doc and end in doc:
            return begin, end
    return DEFAULT_BEGIN, DEFAULT_END


def parse_kv(text):
    out = {}
    for line in text.splitlines():
        if line.startswith("MACHINE_") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


PER_CPU = re.compile(
    r"^T:\s*(\d+)\s*\(\s*\d+\)\s*P:\s*\d+\s*I:\s*\d+\s*C:\s*(\d+)"
    r"\s*Min:\s*(\d+)\s*Act:\s*(\d+)\s*Avg:\s*(\d+)\s*Max:\s*(\d+)"
)


def parse_cyclictest(text):
    """返回 (per_cpu, summary)。per_cpu 可能为空——取决于 cyclictest 是否打印了 T: 行。"""
    per_cpu = {}
    for raw in text.splitlines():
        m = PER_CPU.match(raw.strip())
        if m:
            per_cpu[int(m.group(1))] = {
                "loops": int(m.group(2)),
                "min": int(m.group(3)),
                "avg": int(m.group(5)),
                "max": int(m.group(6)),
            }

    summary = {}
    for key, label in (("min", "# Min Latencies"),
                       ("avg", "# Avg Latencies"),
                       ("max", "# Max Latencies")):
        for raw in text.splitlines():
            s = raw.strip()
            if s.startswith(label):
                vals = [int(x) for x in re.findall(r"\d+", s.split(":", 1)[1])]
                if vals:
                    summary[key] = vals
    return per_cpu, summary


def parse_bench(text):
    out = {}
    m = re.search(r"now_ns\(\)\s*单次开销\s*:\s*([0-9.]+)", text)
    if m:
        out["clock_ns"] = float(m.group(1))
    m = re.search(r"record\(\)\s*单次开销\s*:\s*([0-9.]+)", text)
    if m:
        out["record_ns"] = float(m.group(1))
    m = re.search(
        r"n=(\d+)\s*min=(\d+)\s*p50=(\d+)\s*p99=(\d+)\s*p99\.9=(\d+)\s*max=(\d+)", text)
    if m:
        out["gap"] = {
            "n": int(m.group(1)), "min": int(m.group(2)), "p50": int(m.group(3)),
            "p99": int(m.group(4)), "p999": int(m.group(5)), "max": int(m.group(6)),
        }
    return out


def build_rows(per_cpu, summary):
    """统一成 [(cpu, min, avg, max)]；优先用 per_cpu，否则退化到 summary 数组。"""
    if per_cpu:
        return [(c, per_cpu[c]["min"], per_cpu[c]["avg"], per_cpu[c]["max"])
                for c in sorted(per_cpu)]
    if summary:
        n = max(len(v) for v in summary.values())

        def g(key, i):
            v = summary.get(key, [])
            return v[i] if i < len(v) else "?"

        return [(i, g("min", i), g("avg", i), g("max", i)) for i in range(n)]
    return []


def yesno(v):
    return {"yes": "可用", "no": "不可用"}.get(str(v).lower(), str(v))


def render_block(kv, per_cpu, summary, bench, run_dir, todo):
    L = []
    virt = kv.get("MACHINE_VIRT", "未知")
    L.append("> ⚠️ 本机虚拟化类型：**%s**。虚拟化环境下采集的数字只代表"
             "**开发环境的噪声水平**，不能作为实时性结论。" % virt)
    L.append("> 真正的「PREEMPT_RT 之前」基线，必须在 D7 的目标机器上重测一次。")
    L.append("")

    L.append("### 环境")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("| --- | --- |")
    for k, v in (
        ("采集时间", kv.get("MACHINE_TIME", "?")),
        ("内核版本", kv.get("MACHINE_KERNEL", "?")),
        ("架构", kv.get("MACHINE_ARCH", "?")),
        ("虚拟化", virt),
        ("CPU 型号", kv.get("MACHINE_CPU_MODEL", "?")),
        ("CPU 核数", kv.get("MACHINE_CPU_COUNT", "?")),
        ("CPU 主频", kv.get("MACHINE_CPU_MHZ", "?")),
        ("内存", kv.get("MACHINE_MEM_TOTAL", "?")),
        ("内核 cmdline", "`%s`" % kv.get("MACHINE_CMDLINE", "?")),
        ("抢占模型", kv.get("MACHINE_PREEMPT", "?")),
        ("编译器", kv.get("MACHINE_GCC", "?")),
        ("原始数据", "`%s/`" % run_dir.replace("\\", "/")),
    ):
        L.append("| %s | %s |" % (k, v))
    L.append("")

    L.append("### cyclictest")
    L.append("")
    L.append("    sudo cyclictest -m -S -p99 -i1000 -h400 -l100000")
    L.append("")
    rows = build_rows(per_cpu, summary)
    if rows:
        L.append("| 线程 (CPU) | Min (µs) | Avg (µs) | Max (µs) |")
        L.append("| --- | --- | --- | --- |")
        for cpu, lo, av, hi in rows:
            L.append("| %s | %s | %s | %s |" % (cpu, lo, av, hi))
        nums = [r[3] for r in rows if isinstance(r[3], int)]
        if nums:
            worst = max(nums)
            where = ", ".join(str(r[0]) for r in rows if r[3] == worst)
            L.append("")
            L.append("**全机最坏唤醒延迟（Max）**：**%d µs**，出现在 CPU %s。" % (worst, where))
    else:
        L.append("> ⚠️ **未能从 cyclictest 输出中解析出汇总行。**")
        L.append("> 可能原因：未安装 rt-tests、sudo 未放行、或输出格式与预期不符。")
        L.append("> 请打开 `%s/cyclictest.txt` 人工核对，不要跳过这一步。"
                 % run_dir.replace("\\", "/"))
    L.append("")

    L.append("### 测量分辨率地板（mw_bench）")
    L.append("")
    if bench.get("gap") or bench.get("clock_ns") is not None:
        L.append("| 指标 | 值 |")
        L.append("| --- | --- |")
        if bench.get("clock_ns") is not None:
            L.append("| `now_ns()` 单次开销 | %.2f ns |" % bench["clock_ns"])
        if bench.get("record_ns") is not None:
            L.append("| `record()` 单次开销 | %.2f ns |" % bench["record_ns"])
        g = bench.get("gap")
        if g:
            L.append("| 两次 `now_ns()` 间隔 min | %d ns |" % g["min"])
            L.append("| 两次 `now_ns()` 间隔 p50 | %d ns |" % g["p50"])
            L.append("| 两次 `now_ns()` 间隔 p99.9 | %d ns |" % g["p999"])
            L.append("| 两次 `now_ns()` 间隔 max | %d ns |" % g["max"])
            L.append("| 样本数 | %d |" % g["n"])
        L.append("")
        if bench.get("clock_ns") is not None:
            L.append("> **任何小于 %.0f ns 的差异，都不该被当作有效结论。**" % bench["clock_ns"])
    else:
        L.append("> ⚠️ 未解析到 `mw_bench` 输出。先构建并运行：")
        L.append("> `cmake --build build -j && ./build/bench/mw_bench`")
    L.append("")

    L.append("### 观测能力")
    L.append("")
    L.append("| 能力 | 状态 |")
    L.append("| --- | --- |")
    L.append("| `arch_perfmon` 报告 | %s |" % yesno(kv.get("MACHINE_ARCH_PERFMON", "?")))
    L.append("| perf 硬件事件（PMU） | %s |" % yesno(kv.get("MACHINE_PERF_HW", "?")))
    L.append("| BTF / eBPF CO-RE | %s |" % yesno(kv.get("MACHINE_BTF", "?")))
    L.append("| PREEMPT_RT | %s |" % (
        "已启用" if "CONFIG_PREEMPT_RT=y" in kv.get("MACHINE_PREEMPT", "") else "未启用（D7 需要）"))
    L.append("")

    if todo:
        L.append("### 待人工确认（脚本无法替你判断）")
        L.append("")
        for t in todo:
            L.append("- [ ] %s" % t)
        L.append("")

    return "\n".join(L).rstrip()


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scripts/render_baseline.py docs/raw/<时间戳>", file=sys.stderr)
        return 2

    # 防御：标记常量被清空时给出可读的错误，而不是 partition() 的 empty separator
    if not DEFAULT_BEGIN or not DEFAULT_END:
        print("错误：标记常量为空。", file=sys.stderr)
        print("这通常意味着源文件在复制/粘贴过程中被工具删掉了标记内容。", file=sys.stderr)
        print("请检查本文件开头 MARKERS 的定义，它应当包含非空字符串。", file=sys.stderr)
        return 3

    run_dir = sys.argv[1].rstrip("/\\")
    kv = parse_kv(read(os.path.join(run_dir, "machine.txt")))
    per_cpu, summary = parse_cyclictest(read(os.path.join(run_dir, "cyclictest.txt")))
    bench = parse_bench(read(os.path.join(run_dir, "bench.txt")))

    todo = []
    if not per_cpu and not summary:
        todo.append("cyclictest 输出未能解析——请人工核对 `%s/cyclictest.txt`" % run_dir)
    todo.append("P99.9 分位数：cyclictest 只稳定输出 Min/Avg/Max，"
                "分位数请在 D8 用自建直方图（bench_util.hpp 的 LatencyHistogram）测")
    todo.append("机器 / 云实例规格（控制台信息）需人工填写到 docs/realtime.md")
    if str(kv.get("MACHINE_PERF_HW", "")).lower() == "no":
        todo.append("perf 硬件事件不可用（PMU 未透传）——D4 的 `perf c2c` 伪共享实测会受影响，"
                    "需在 docs/realtime.md 中如实标注")

    block = render_block(kv, per_cpu, summary, bench, run_dir, todo)

    # ---- 更新 docs/baseline.md（只动标记块）
    doc_path = "docs/baseline.md"
    cur = read(doc_path) or DEFAULT_TEMPLATE
    begin, end = pick_marker(cur)
    if begin in cur and end in cur:
        head, _, rest = cur.partition(begin)
        _, _, tail = rest.partition(end)
        new = head + begin + "\n" + block + "\n" + end + tail
    else:
        new = cur.rstrip() + "\n\n" + begin + "\n" + block + "\n" + end + "\n"
    write(doc_path, new)
    print("  [ok] 已更新 %s（仅标记块，标记=%s）" % (doc_path, begin))

    # ---- 冻结本次渲染结果，便于回溯
    frozen = os.path.join(run_dir, "baseline.md")
    write(frozen, new)
    print("  [ok] 本次渲染已冻结 -> %s" % frozen)

    print()
    print("=" * 72)
    if todo:
        print("以下内容脚本无法替你判断，请手工补齐：")
        for t in todo:
            print("  - " + t)
    else:
        print("全部字段已自动填充。")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
