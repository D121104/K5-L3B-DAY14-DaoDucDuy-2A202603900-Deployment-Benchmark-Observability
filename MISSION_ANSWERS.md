# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`

1. **Hardcode API key:** `OPENAI_API_KEY` được gán trực tiếp trong source (dòng 17). Nếu đẩy repository public, người khác có thể sao chép secret; kể cả khi xóa ở commit sau, key vẫn có thể còn trong lịch sử Git. Key thật cần được thu hồi/đổi và lấy từ secret manager hoặc environment.
2. **Hardcode database credential:** `DATABASE_URL` chứa username/password trực tiếp trong code (dòng 18), có cùng rủi ro lộ thông tin và khó thay đổi giữa các môi trường.
3. **Debug bật cố định:** `DEBUG = True` (dòng 21), không thể tắt theo môi trường. Cấu hình debug không phù hợp production có thể làm lộ thông tin nội bộ hoặc bật hành vi phát triển ngoài ý muốn.
4. **Không có quản lý cấu hình:** `MAX_TOKENS` được gán cố định (dòng 22), không có cấu hình tập trung hay đọc từ environment; thay đổi hành vi phải sửa code và build/deploy lại.
5. **In secret vào log:** endpoint `/ask` in `OPENAI_API_KEY` (dòng 34). Secret có thể bị lưu trong terminal, log tập trung hoặc hệ thống hỗ trợ sự cố.
6. **Dùng `print()` thay structured logging:** các dòng 33–38 không có cấu trúc/trường thống nhất, khó lọc, tìm kiếm và phân tích bằng hệ thống log.
7. **Không có health check:** không có endpoint `/health` (dòng 42–43), nên nền tảng/load balancer khó xác định process còn sống để cảnh báo hoặc khởi động lại.
8. **Port cố định và bind vào localhost:** `port=8000`, `host="localhost"` (dòng 49–52). Không dùng được port do Railway/Render cấp và kết nối từ bên ngoài container có thể không tới được ứng dụng.
9. **Bật auto-reload:** `reload=True` (dòng 53) là tùy chọn phục vụ phát triển, không phù hợp tiến trình production ổn định.
10. **Không có xử lý shutdown rõ ràng:** app không khai báo lifecycle/cleanup; việc tắt process có nguy cơ ngắt request đang xử lý hoặc không đóng tài nguyên đúng cách.

### Exercise 1.2: Chạy basic version

Đã chạy app develop trên cổng 8000 và gửi request theo đúng giao diện của bản này (query parameter):

```bash
curl -i -X POST 'http://localhost:8000/ask?question=Hello'
```

Kết quả thực tế: HTTP `200 OK`, response JSON có trường `answer` từ mock LLM. Bản develop nhận `question` qua query parameter; gửi JSON body không phải cách gọi đúng cho phiên bản này.

### Exercise 1.3: So sánh develop và production

| Feature | Develop (`develop/app.py`) | Production (`production/app.py`, `config.py`) | Tại sao quan trọng? |
|---|---|---|---|
| Cấu hình | Một số giá trị như `DEBUG`, `MAX_TOKENS` gán trong code. | `Settings` đọc `HOST`, `PORT`, `DEBUG`, `ENVIRONMENT`, `LLM_MODEL`, `MAX_TOKENS` và các giá trị khác từ environment; tập trung ở `config.py`. | Cùng một artifact có thể chạy ở dev/staging/production với cấu hình khác nhau mà không sửa source. |
| Secrets | API key và database URL được hardcode; API key còn được in ra log. | Đọc `OPENAI_API_KEY`/`AGENT_API_KEY` từ environment; không log key. `.env.example` là template, không phải file secret thật. | Giảm nguy cơ lộ credential trong source, Git history và log; secret thật có thể được quản lý riêng theo môi trường. |
| Bind/port | Chỉ bind `localhost`, cổng cố định 8000. | Mặc định bind `0.0.0.0`, đọc port từ biến `PORT`. | Cho phép nhận traffic từ bên ngoài container và tuân theo cổng do nền tảng cloud cấp. |
| Debug | `DEBUG=True` và Uvicorn `reload=True` cố định. | Debug mặc định tắt; reload chỉ bật khi `DEBUG=true`. | Tránh hành vi dành cho phát triển chạy ngoài ý muốn trong production. |
| Health check | Không có endpoint health. | `GET /health` trả trạng thái và uptime; `GET /ready` cho biết app đã sẵn sàng. | Nền tảng có thể kiểm tra liveness/readiness để quản lý traffic và phát hiện process lỗi. |
| Logging | `print()` và một dòng còn in secret. | Cấu hình logging có cấu trúc JSON; log request/response không chứa API key. | Log dễ parse, lọc và giám sát; giảm rủi ro lộ dữ liệu nhạy cảm. |
| Shutdown | Không khai báo cơ chế lifecycle/cleanup. | Có FastAPI lifespan để chạy startup/shutdown; Uvicorn quản lý vòng đời server và SIGTERM. | Tạo điểm dọn tài nguyên và cho server cơ hội xử lý request đang chạy trước khi thoát. Cần kiểm tra hành vi trên nền tảng triển khai thực tế. |
| Kiểm tra input | Đọc JSON trực tiếp rồi tự kiểm tra `question` rỗng. | Cũng đọc JSON trực tiếp và trả lỗi `422` khi thiếu câu hỏi; chưa dùng schema Pydantic cho request ở ví dụ này. | Cả hai cần từ chối input không hợp lệ; schema/validation rõ ràng giúp API nhất quán và dễ bảo trì. |

Đã chạy bản production-style với `PORT=8000`, `DEBUG=false`, `ENVIRONMENT=development`. Các lệnh kiểm tra và kết quả thực tế:

```bash
curl -i -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
# HTTP 200; response có question, answer và model

curl -i http://localhost:8000/health
# HTTP 200; status=ok

curl -i http://localhost:8000/ready
# HTTP 200; ready=true
```

### Câu hỏi thảo luận

1. **Nếu push code có API key hardcode lên GitHub public:** coi key đã bị lộ. Cần thu hồi/rotate key ngay, kiểm tra log/lịch sử sử dụng và chuyển secret sang biến môi trường hoặc secret manager. Xóa dòng code trong commit mới không xóa key khỏi Git history.
2. **Tại sao stateless quan trọng khi scale:** request kế tiếp có thể được load balancer chuyển sang instance khác. Nếu session/state chỉ nằm trong RAM của một instance, instance khác không thấy dữ liệu đó; restart cũng làm mất state. Đưa state dùng chung vào Redis/database giúp các instance xử lý request nhất quán.
3. **“Dev/prod parity” nghĩa là gì:** giữ môi trường phát triển, staging và production càng giống nhau càng tốt về runtime, dependencies, cách cấu hình và cách chạy. Khác biệt cấu hình nên được đưa qua environment, không tạo các nhánh code vận hành hoàn toàn khác nhau; nhờ vậy giảm lỗi chỉ xuất hiện khi deploy.

## Part 2: Docker

### Exercise 2.1: Dockerfile cơ bản

1. **Base image:** `python:3.11` trong `02-docker/develop/Dockerfile`.
2. **Working directory:** `/app`, được đặt bằng `WORKDIR /app`.
3. **Vì sao copy requirements trước source:** Docker cache theo layer. Khi source thay đổi nhưng `requirements.txt` không đổi, layer cài dependencies có thể được dùng lại, giúp build nhanh hơn. Nếu copy toàn bộ source trước, thay đổi code cũng làm mất cache của các bước phía sau.
4. **CMD và ENTRYPOINT:** `CMD` đặt lệnh mặc định/đối số mặc định và thường có thể bị thay thế khi `docker run` truyền lệnh khác. `ENTRYPOINT` xác định chương trình chính của container; các đối số khi chạy container thường được thêm vào chương trình đó. Có thể kết hợp ENTRYPOINT cố định với CMD làm đối số mặc định.

### Exercise 2.2–2.3: Build, chạy và so sánh image

Đã build từ gốc repo theo hướng dẫn K5:

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images my-agent
```

Kích thước lấy từ Docker image inspect trong môi trường chạy bài (Docker Engine 29.9.2, Linux/amd64):

| Image | Kích thước Docker hiển thị | Kích thước inspect |
|---|---:|---:|
| `my-agent:develop` | 1.67 GB | 1,667,780,330 bytes (xấp xỉ 1,590.7 MiB) |
| `my-agent:advanced` | 240 MB | 239,810,932 bytes (xấp xỉ 228.7 MiB) |

Image advanced nhỏ hơn khoảng **85.6%** so với develop, tính theo byte: `(1,667,780,330 - 239,810,932) / 1,667,780,330 × 100`.

**Cấu trúc multi-stage trong Dockerfile production:**

- Stage `builder` dùng `python:3.11-slim`, cài gcc/libpq-dev và Python dependencies vào `/root/.local`.
- Stage `runtime` bắt đầu từ image `python:3.11-slim` sạch, chỉ copy packages cần chạy cùng source; sau đó chạy non-root `appuser`.
- Build tools và các package hệ thống chỉ cần lúc cài đặt nằm ở stage builder, không được đưa vào image cuối. Điều này giảm kích thước image và thu hẹp thành phần runtime.

Đã chạy container basic và kiểm tra `POST /ask?question=What%20is%20Docker%3F` cùng `GET /health`; cả hai trả HTTP `200`. Câu trả lời `/ask` nhận được là “Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!”.

### Exercise 2.4: Docker Compose stack

Đã chạy stack với project name riêng `k5-day14-docker` để tránh trùng tên project `production` của các thư mục khác. Tạo `.env.local` trống theo hướng dẫn repo để Compose đọc env file; file tạm đã được xóa sau khi dừng stack.

```text
Client
  │ HTTP :80 / HTTPS :443
  ▼
Nginx (reverse proxy, security headers, rate limit)
  │ Docker internal network
  ▼
Agent (FastAPI :8000)
  ├── REDIS_URL=redis://redis:6379/0 ── Redis 7 (healthcheck, volume)
  └── QDRANT_URL=http://qdrant:6333 ── Qdrant (healthcheck, volume)
```

Compose tạo bốn service: `nginx`, `agent`, `redis` và `qdrant`. Nginx công bố cổng 80/443 ra host và proxy request tới agent; agent, Redis và Qdrant nằm trong network nội bộ. Redis và Qdrant có healthcheck/volume; agent đợi hai service này healthy trước khi start. Mã agent mẫu minh họa các URL service qua environment, nhưng bản demo `main.py` chưa thực hiện thao tác Redis/Qdrant.

Đã kiểm tra qua Nginx:

```bash
curl -i http://localhost/health
# HTTP 200; JSON status=ok, version=2.0.0

curl -i -X POST http://localhost/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Explain microservices"}'
# HTTP 200; response có answer từ mock LLM
```

Stack đã được dừng bằng `docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml down`.

## Part 3: Cloud Deployment

### Exercise 3.1–3.2: Railway và Render

**Trạng thái deploy K5:** chưa deploy và chưa có URL public. Theo hướng dẫn K5, Part 3 phải deploy agent Part 6 trong `06-lab-complete/`, không deploy app mẫu trong `03-cloud-deployment/`. Part 6 hiện đã hoàn tất và checker đạt `PASS 12/12`, cấu hình Railway dùng Dockerfile và health check `/health`. Môi trường hiện tại không có Railway CLI, Render CLI hoặc `gcloud`; chưa có thao tác deploy/đăng nhập cloud trong môi trường này. Không ghi URL/ảnh deploy giả.

**So sánh các cấu hình ví dụ có sẵn trong `03-cloud-deployment/`:**

| Khía cạnh | Railway (`railway/railway.toml`) | Render (`render/render.yaml`) |
|---|---|---|
| Định dạng/cách khai báo | TOML với các section `[build]` và `[deploy]`; cấu hình một service Railway. | YAML dạng Blueprint; khai báo danh sách service và thuộc tính từng service. |
| Build/runtime mẫu | `builder = "NIXPACKS"`; start command chạy Uvicorn và dùng `$PORT`. | `runtime: python`, có `buildCommand` và `startCommand`, cũng bind vào `$PORT`. |
| Health check | `healthcheckPath = "/health"`; có timeout và restart policy. | `healthCheckPath: /health`; bật `autoDeploy`. |
| Secret/service phụ | Comment hướng dẫn đặt biến bằng Railway CLI/dashboard. | `envVars` hỗ trợ `sync: false` hoặc `generateValue: true`; Blueprint ví dụ còn khai báo Redis riêng. |
| Khi dùng cho bài K5 | Cấu hình trong `06-lab-complete/` phải dùng Docker builder theo hợp đồng Part 6, không phải Nixpacks mẫu này. | Cấu hình Part 6 cần `runtime: docker`, health check `/health` và secret không ghi thẳng vào YAML. |

Khác biệt cốt lõi là Railway dùng file TOML ngắn để mô tả cấu hình service/build/deploy; Render Blueprint dùng YAML để khai báo service và hạ tầng dưới dạng tài nguyên. Cả hai đều hỗ trợ health check, biến môi trường và triển khai từ repository. Các file trên trong `03-cloud-deployment/` là ví dụ cho app mẫu, chưa phải cấu hình triển khai agent K5.

### Exercise 3.3: Cloud Run CI/CD

Khi Cloud Build được kích hoạt sau push, pipeline trong `cloudbuild.yaml` chạy test trước; nếu test đạt thì build Docker image có tag commit SHA và `latest`; tiếp theo push các tag lên Container Registry; cuối cùng deploy image theo commit SHA lên Cloud Run ở `asia-southeast1`. Cấu hình deploy đặt giới hạn min/max instance, CPU/RAM/timeout và lấy secret từ Secret Manager thay vì ghi key trực tiếp vào source. `service.yaml` mô tả service Cloud Run cùng concurrency, probes, scaling và secret references.

### Câu hỏi thảo luận

1. **Vì sao serverless không phải lúc nào cũng phù hợp cho AI agent:** cold start có thể làm tăng thời gian phản hồi; request LLM/streaming có thể kéo dài; giới hạn concurrency, timeout, bộ nhớ hoặc accelerator có thể không phù hợp workload. Serverless vẫn phù hợp nếu workload/stateless và các giới hạn dịch vụ đáp ứng được yêu cầu.
2. **Cold start:** thời gian khởi tạo instance/container khi chưa có instance sẵn sàng nhận request, ví dụ tải runtime, dependencies hoặc model. Nó làm request đầu sau thời gian idle chậm hơn và ảnh hưởng UX; giữ instance tối thiểu có thể giảm cold start nhưng tăng chi phí.
3. **Khi nào cân nhắc chuyển từ Railway sang Cloud Run:** khi cần kiểm soát scaling/concurrency, cấu hình tài nguyên, tích hợp IAM/Secret Manager, CI/CD và quan sát ở mức production hơn; cần cân đối thêm độ phức tạp vận hành và chi phí.

**Các bước còn lại để hoàn thành điểm deploy chính:** tạo/cấu hình Redis cloud; đăng nhập Railway hoặc tạo Render Blueprint, đặt `AGENT_API_KEY` và `REDIS_URL`, deploy đúng thư mục `06-lab-complete/`, ghi URL thật vào `DEPLOYMENT.md`, rồi chạy bốn lệnh tự kiểm ở CP6 (`/health` 200, `/ready` 200, `/ask` không key 401, `/ask` có key 200). Phần này còn chờ truy cập tài khoản/nền tảng cloud.

## Part 6: Final Project

Đã hoàn thiện ứng dụng trong `06-lab-complete/`: cấu hình env, API key auth, rate limit và daily cost guard dùng Redis; `/health` và `/ready`; JSON logs; multi-stage Dockerfile; Compose agent + Redis; `.dockerignore`; Railway Dockerfile builder và health check.

Kết quả checker đầy đủ (chạy trong `06-lab-complete/`, Docker Engine 29.9.2):

```text
📋 Checklist Deliverable
✅ Dockerfile (multi-stage, < 500 MB)
✅ docker-compose.yml (agent + redis)
✅ .dockerignore
✅ Health check endpoint (GET /health)
✅ Readiness endpoint (GET /ready)
✅ API Key authentication
✅ Rate limiting
✅ Cost guard
✅ Config từ environment variables
✅ Structured logging
✅ Graceful shutdown
✅ Public URL ready (Railway / Render config)
Result: PASS 12/12 tiêu chí đạt · 41/41 checks passed
```

Checker xác nhận rate limit còn hiệu lực sau restart agent; Redis mất kết nối khiến `/ready` trả 503 trong khi `/health` vẫn 200; budget guard trả 402; request đang chạy hoàn thành khi nhận SIGTERM; Docker stop thoát mã 0 trong 0.6 giây. Image runtime build được, dung lượng **273 MB**.

Smoke test Compose cũng đã chạy: `/health` 200, `/ready` 200, `/ask` thiếu API key 401 và `/ask` với key kiểm thử 200. Stack test đã được dừng và volume Redis tạm đã xóa. Chưa deploy lên Railway/Render nên chưa có URL public; phần đó ghi nhận ở Part 3 và cần thực hiện sau khi đăng nhập tài khoản cloud.

## AI log

- Hỗ trợ: đọc và đối chiếu yêu cầu Part 1, tìm anti-patterns trong hai phiên bản app, soạn nháp câu trả lời và lệnh kiểm tra.
- Tôi đã tự đối chiếu các nhận xét với `develop/app.py`, `production/app.py`, `production/config.py` và chạy thử hai server. Basic trả HTTP 200 với query parameter; production-style trả HTTP 200 cho JSON `/ask`, `/health` và `/ready`.
- Các kết quả thử trên là từ môi trường hiện tại; chưa xác minh hành vi graceful shutdown hoặc triển khai cloud.
- Part 2: hỗ trợ đọc Dockerfiles/Compose và tổng hợp câu trả lời; tôi đã tự build hai image, lấy kích thước bằng `docker image inspect`, chạy container basic và Compose stack, rồi thử endpoint qua container/Nginx.
- Part 3: hỗ trợ đọc tiêu chí/config và soạn phần so sánh, mô tả pipeline; lúc đánh giá ban đầu Part 6 chưa hoàn tất. Part 6 hiện đã đạt checker, nhưng tôi chưa deploy vì các CLI nền tảng không có trong PATH và chưa cấu hình tài khoản cloud.
- Part 6: hỗ trợ triển khai các module và cấu hình theo hợp đồng checker; tôi chạy checker đầy đủ đến PASS 12/12 (41/41), smoke test Compose và kiểm tra các endpoint. Docker build/test dùng Python 3.11 trong image; môi trường host Python 3.14 không cài được pin `pydantic==2.9.0`, nên checker được chạy bằng venv tạm với dependency tương thích.
