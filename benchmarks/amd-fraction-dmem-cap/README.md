# AMD GPU fractions in KAI: a hard memory cap at no performance cost

Report: https://openinferencefabric.us.ci/benchmarks/amd-fraction-dmem-cap/ (3 November 2026)

[Open Inference Fabric](https://github.com/openinferencefabric/oif) added an AMD backend to `fractiond`, the node agent of
KAI Scheduler's [gpu-fractioning](https://github.com/kai-scheduler/gpu-fractioning). It caps each fractional pod's GPU
memory with the Linux dmem cgroup (`dmem.max` on the pod cgroup, kernel 6.14+). This folder holds the benchmark that
checks what the cap costs, with NVIDIA's gpu-fractioning on an RTX A6000 as the reference, and everything needed to
read or rerun it.

Code: [openinferencefabric/gpu-fractioning](https://github.com/openinferencefabric/gpu-fractioning) (`fractiond --gpu-vendor=amd`).
Upstream proposal: [kai-scheduler/gpu-fractioning#173](https://github.com/kai-scheduler/gpu-fractioning/issues/173).

## Result

| Capped 0.5 pod against the whole GPU (worst case over concurrency 1, 8, 32) | W7900, dmem cap | A6000, NVIDIA gpu-fractioning |
|---|---|---|
| Time per output token (median) | −1.1% | +0.6% |
| End-to-end latency (median) | +1.1% | +1.1% |
| Throughput at concurrency 32 | −1.4% | −0.1% |
| Time to first token at concurrency 32 (median, one run) | +16.6% | +8.6% |

A 0.5 pod whose vLLM asked for 0.9 of the W7900 was refused by the kernel at its 22.5 GiB cap (HIP out of memory); on the
A6000 the same pod fit, because CUDA shows the container only its share. Two 0.5 pods on one GPU delivered 4,777 (W7900)
and 5,876 (A6000) output tokens/s together, about 1.7× one engine on both.

## Contents

| Path | What |
|---|---|
| `index.html` | The report (self-contained) |
| `images/` | Report and console images |
| `scripts/bench-qwen3.sh` | The vLLM benchmark: scenarios A (whole GPU), B (one 0.5 pod), C (two 0.5 pods together), D (0.5 pod asking vLLM for 0.9); the node's `oif.ai/gpu-vendor` label picks AMD or NVIDIA |
| `scripts/quick-dmem-cap.sh` | The functional test of the cap: a 0.25 pod with and without the cap, a 0.5 neighbour |
| `scripts/vram-probe/` | Source of the 122 MB probe image the quick test uses (`docker.io/manmohanbrahma/oif-vram-probe:0.1`) |
| `results/w7900/`, `results/a6000/` | Per run: `<scenario>-c<concurrency>.json` (vLLM `bench serve` result), `.log` (its output), `console.txt` (the script's output) |
| `results/quick-test/console.txt` | Output of the quick test |

The lab's storage path is replaced by `<kit-dir>` in the console files.

## Setup

- **Host:** AMD EPYC 9684X; each GPU passed through to its own KVM VM (48 vCPU, Ubuntu 26.04.1, kernel 7.0.0-38).
- **GPUs:** Radeon PRO W7900 48 GB (amdgpu in kernel 7.0) and RTX A6000 48 GB (driver 615.71.09).
- **Platform:** Kubernetes 1.35.9 built by Open Inference Fabric; KAI v0.18.3 through Run:ai 3.0.20 (with OIF's AMD patches).
- **Engine:** vLLM 0.19.1 on both: `rocm/vllm:rocm7.13.0_gfx110X-all_ubuntu24.04_py3.13_pytorch_2.10.0_vllm_0.19.1` and `vllm/vllm-openai:v0.19.1` (digests in the script).
- **Model and load:** Qwen/Qwen3-0.6B (BF16, max model length 4096); `vllm bench serve`, random prompts, 512 tokens in and 128 out, concurrency 1, 8 and 32 (16, 64 and 256 requests). One GPU loaded at a time.
- **vLLM memory:** whole GPU 0.9; 0.5 pods 0.45 on the W7900 (ROCm reports the whole GPU) and 0.9 of the share on the A6000 (CUDA reports the share).

## Rerun

On a host with passwordless `ssh` to the control node and the GPU node of an Open Inference Fabric cluster, with
`fractiond` (built from the code above with `--gpu-vendor=amd` support) next to the scripts:

```sh
./quick-dmem-cap.sh  cp1 gpu-amd    runai-team-c   # the cap works
./bench-qwen3.sh     cp1 gpu-amd    runai-team-c   # AMD benchmark
./bench-qwen3.sh     cp1 gpu-nvidia runai-team-c   # NVIDIA reference
```

Each script undoes what it set up. The vLLM images stay on the nodes.

## Reading the numbers

- One run per scenario. The time-to-first-token rise at concurrency 32 appeared on both GPUs; three repeats would settle it.
- Throughput at concurrency 1 and 8 includes each run's first request, which pays vLLM's warm-up (the 4–5 s p99 time to first token). Compare time per token there.
- In scenario C each pod steps through the concurrency levels at its own pace; the concurrency 32 steps overlapped for most of their run.
- The W7900 run used an earlier revision of `bench-qwen3.sh` (AMD only, pods named `q-*`). The NVIDIA run and the copy here are the vendor-aware revision; scenarios, settings and load are the same.
