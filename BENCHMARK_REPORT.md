# Benchmark & Observability Report — Day 14

**Họ tên:** Đào Đức Duy  
**Ngày chạy:** 2026-11-26  
**Môi trường:** Ubuntu 7.0.0-44-generic, x86_64; Docker Engine 29.9.2; 16 CPU, 14 GiB RAM; production containers dùng Python 3.11. Local scripts chạy trong temporary venv trên host Python 3.14.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---:|---|
| p95 latency `/ask` | < 500 ms | Ngưỡng phản hồi tương tác; đo tail thay vì chỉ average. Đây cũng là ngưỡng load-test script kiểm tra. |
| Error rate `/ask` | < 2% | Cho phép lỗi mock/provider hiếm nhưng cảnh báo khi lỗi vượt đáng kể default 1%. |
| Accuracy trên golden dataset | ≥ 80% | Quality gate tối thiểu; với dataset 23 câu tương đương tối thiểu 19 câu đúng. Sau khi sửa KB, v2 đạt 100%. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 4.85 | 187.8 | 217.2 | 1,659.3 | 1.33% | PASS |
| 10 | 37.33 | 190.1 | 217.3 | 1,701.9 | 0.00% | PASS |
| 50 | 107.47 | 193.8 | 226.9 | 1,679.2 | 0.33% | PASS |
| 100 | 75.42 | 267.2 | 2,033.4 | 2,749.2 | 0.67% | FAIL (p95) |

**Nhận xét:** RPS không tăng tuyến tính: đạt cao nhất ở concurrency 50 rồi giảm ở 100. p95 giữ quanh 217–227 ms đến 50 users nhưng tăng lên 2.03 giây ở 100 users; lỗi vẫn dưới SLO. Kết quả cho thấy tail/queueing dưới tải cao là nút thắt trước error rate. Đây là 300 request/run, nên xem như phép đo lab ngắn trên mock, không phải capacity guarantee.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|
| 0 | 189.2 | 215.9 | 221.3 |
| 0.03 (mặc định) | 243.8 | 220.6 | 1,710.9 |
| 0.1 | 315.2 | 1,681.9 | 1,708.6 |

**Nhận xét:** p99 phản ứng rõ khi slow rate còn 3%: p95 gần như không đổi nhưng p99 tăng khoảng 1.49 giây. Khi 10% request chậm, trên 5% mẫu bị ảnh hưởng nên cả p95 và p99 tăng lên khoảng 1.7 giây. SLO không nên chỉ dựa trên average vì một nhóm request chậm có thể làm UX xấu dù average vẫn dưới 500 ms.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 ban đầu | Agent v2 sau khi sửa KB |
|---|---:|---:|---:|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 55.9 | 109.3 | 111.8 |
| Tổng cost (USD) | $0.000387 | $0.000764 | $0.000775 |
| Cost / câu đúng (USD) | $0.00038715 | $0.00003639 | $0.00003368 |
| Quality gate | FAIL | PASS (min 80%, không regression so với v1) | PASS (min 100%, không regression so với v2 ban đầu) |

**Những câu v2 trả lời sai ban đầu và cách đã sửa:**

| ID | Keyword bị thiếu | Đã sửa |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry KB mô tả JWT là token có chữ ký và expiry, đối chiếu với API key. |
| `scaling-03` | `CPU`, `memory`, `custom metrics` | Thêm entry KB cho Kubernetes HPA và các metrics dùng để scale. |

**Trade-off:** v2 dùng thêm context nên trung bình tốn gần gấp đôi token/cost mỗi câu so với v1, nhưng accuracy tăng từ 4.35% lên 91.3%, rồi 100% sau cập nhật. Cost/câu đúng của v2 đã sửa thấp hơn v1 khoảng 11.5 lần. Các lần chạy dùng mock LLM; không phát sinh phí provider thật.

Đã thêm CI quality gate tại `.github/workflows/eval.yml`: chạy v2 khi pull request/push `main`, đặt error/slow injection bằng 0 và fail nếu accuracy dưới 85%. Chạy eval v1 so với v2 đã fail gate với 22 regressions; v2 sau sửa KB pass ngưỡng 100%.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải: [`screenshots/grafana-dashboard.png`](screenshots/grafana-dashboard.png)
- [x] Trace chậm trong Jaeger: [`screenshots/jaeger-slow-trace.png`](screenshots/jaeger-slow-trace.png)
- [x] Trace lỗi có exception trong Jaeger: [`screenshots/jaeger-error-trace.png`](screenshots/jaeger-error-trace.png)
- [x] Ảnh rubric Prometheus Alerts với ít nhất 2 alert cùng firing: [`screenshots/prometheus-alert-firing.png`](screenshots/prometheus-alert-firing.png) (`AgentHighErrorRate` và `LLMCostBurnRateHigh`); thêm ảnh riêng cho p95/cost: [`screenshots/prometheus-alert-p95.png`](screenshots/prometheus-alert-p95.png), [`screenshots/prometheus-alert-cost-burn.png`](screenshots/prometheus-alert-cost-burn.png)

Dashboard screenshot khi ba instance có traffic ghi nhận khoảng 1.7 req/s, error rate 0%, p95 289.85 ms, ba instance up và in-flight 3. Prometheus query trong cửa sổ đo phân phối traffic tới cả ba instance, khoảng 0.76–1.15 req/s mỗi instance. Token input/s cao hơn output/s (197.6 so với 104.9 trong query sample) vì input gồm system prompt, câu hỏi và retrieved context, còn mock output ngắn. Nginx trả `404` cho `/metrics`; metrics chỉ mở nội bộ cho Prometheus.

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert firing | Thời gian từ lúc đổi → firing | Panel phản ánh rõ nhất |
|---|---|---|---:|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~68.1 s (activeAt + rule `for: 1m`) | Error rate / Requests theo status |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 132.1 s | Latency p95; load run ghi p95 1,700 ms |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | 147.1 s | Cost burn rate; đạt $16.12/giờ |
| D | `docker pause k5-day14-observability-agent-2` | `AgentInstanceDown` | 42.1 s | Instances up / Prometheus targets |
| E | `AGENT_VERSION=v1` | Không có alert firing | Không firing trong kiểm tra | Metrics không đo semantic quality; eval gate phát hiện accuracy 4.35% và 22 regressions |

**E không làm metric alert firing** vì request vẫn trả `200` và latency/error có thể bình thường dù câu trả lời kém chất lượng. Cần chạy golden-dataset eval/quality gate trước deploy và theo dõi accuracy/feedback; workflow CI mới thêm sẽ chặn merge nếu accuracy < 85%.

Alert screenshot A ban đầu đồng thời hiển thị `LLMCostBurnRateHigh` do cost burn cũng vượt ngưỡng trong load test mặc định. Để đo experiment C riêng, Prometheus container/TSDB tạm được reset trước khi chạy large model; các ảnh A/B và JSON timings đã lưu trước khi reset.

### 4.3 Debug bằng trace

Trace chậm nhất được lấy từ fault experiment B:

- `trace_id`: `0dadee55e7fe10983684585d5ddf42ba`
- Tổng thời gian: 1,723.69 ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1,683.30 ms, khoảng 97.7% tổng latency); retrieval chiếm 21.18 ms.
- Trace JSON: `06-lab-complete/benchmark-observability/production/benchmark-results/slow-trace.json`.

Trace lỗi được tạo khi `MOCK_ERROR_RATE=0.2`:

- `trace_id`: `2e121925eb96a0b5396ffde584703b8b`
- Tổng thời gian: 143.40 ms; HTTP 503.
- Span `chat mock-llm-small` chứa event `exception` với `LLMError: Upstream LLM error: 503 Service Unavailable (mock)`.
- JSON log tương ứng (cùng trace ID):

```json
{"ts":"2026-11-26T10:30:02.475743+00:00","level":"INFO","service":"observable-agent","instance":"0b8bdd427f01","event":"llm_error","trace_id":"2e121925eb96a0b5396ffde584703b8b","span_id":"d3163685aba1f237","request_id":"68e8a10515a1","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---:|---:|---:|---:|---:|---:|
| 1 | 65.90 | 190 | 220 | 1,700 | 76 / 7,855 (0.97%) |
| 3 | 65.83 | 190 | 220 | 1,700 | 65 / 7,841 (0.83%) |

**Giải thích:** trong workload này scale 1→3 không cải thiện RPS/p95 đáng kể. Mock agent chủ yếu `async` chờ latency giả lập, một instance đã xử lý đồng thời được 100 users; wait time 0.5–2 giây trong Locust cũng giới hạn tốc độ phát request. Kết quả này không chứng minh scale vô ích: cần tăng tải/giảm think time hoặc dùng workload CPU-bound để làm lộ giới hạn replica. CSV được chạy ở scale chính xác bằng `docker compose run --no-deps locust`; `--no-deps` tránh Compose tự khôi phục default `deploy.replicas: 2` khi chạy Locust one-off.

---

## 6. Kết luận

- p95/p99 cho thấy tail latency và vì sao average một mình không đủ làm SLO.
- Retrieval KB nâng accuracy mạnh; quality gate bắt regression mà metrics vận hành không thấy.
- Prometheus phát hiện latency/error/cost/availability; Jaeger tìm span chậm và exception; ba thứ cần được liên kết với structured log bằng trace ID.

Production thật nên bổ sung alert cho quality regression/feedback, budget theo tenant, queue/concurrency, Redis errors, memory/CPU saturation và deploy/version change. Test setup dùng `mock-llm`; không đại diện cho latency/cost của provider thật.

**Artifacts:** local load/eval JSON gốc ở `06-lab-complete/benchmark-observability/develop/reports/` và bản nộp ở `reports/`; Locust CSV, trace JSON và experiment JSON gốc ở `06-lab-complete/benchmark-observability/production/benchmark-results/` và bản nộp ở `benchmark-results/`; ảnh ở `screenshots/`. `promtool test rules` đã pass. Observability image ban đầu crash do `pip --user` path không được cấu hình; đã sửa Dockerfile bằng `PYTHONUSERBASE=/home/agent/.local` và rebuild trước khi benchmark.
