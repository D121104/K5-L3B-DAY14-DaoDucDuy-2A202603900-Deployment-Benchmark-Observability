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

**Trạng thái deploy K5:** đã deploy agent Part 6 từ `06-lab-complete/` lên Railway; URL public là `https://k5-l3b-day14-daoducduy-2a202603900-deployment-be-production.up.railway.app`. Part 6 đạt `PASS 12/12`. Bốn lệnh kiểm tra CP6 do sinh viên chạy trả lần lượt `200`, `200`, `401`, `200`; kiểm tra độc lập từ môi trường này cũng xác nhận `/health` 200, `/ready` 200 và `/ask` không có key 401. Thông tin deploy nằm trong `DEPLOYMENT.md`; ảnh dashboard, deployment và test đã được thêm vào `screenshots/` và không thấy API key trong ảnh.

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

Ảnh Railway dashboard, service đang chạy và kết quả bốn lệnh CP6 được lưu trong `screenshots/`; API key không được ghi vào tài liệu hoặc ảnh.

## Part 4: API Security

### Exercise 4.1: API Key authentication

Trong `04-api-gateway/develop/app.py`, `APIKeyHeader` đọc header `X-API-Key`; dependency `verify_api_key` được gắn vào endpoint `/ask`. Key mong đợi lấy từ `AGENT_API_KEY` (có fallback demo nếu không đặt env). Thiếu key trả `401`, key sai trả `403`, key đúng mới được gọi agent. Đã chạy thử với key kiểm thử tạm, không phải secret cloud:

```text
POST /ask without X-API-Key: 401
POST /ask with invalid X-API-Key: 403
POST /ask with valid test X-API-Key: 200
```

Muốn rotate key thì tạo key mới, cập nhật secret `AGENT_API_KEY` ở nơi chạy app rồi restart/redeploy. Với demo chỉ chấp nhận một key nên key cũ bị vô hiệu khi config mới có hiệu lực; hệ thống cần rotation không gián đoạn nên hỗ trợ khoảng overlap giữa key cũ/mới. Ví dụ này còn có fallback demo và in API key ra stdout khi chạy, vì vậy không dùng nguyên trạng trong production và tuyệt đối không đặt secret thật vào lệnh hiển thị/log.

### Exercise 4.2: JWT authentication

`POST /auth/token` xác thực user demo rồi ký JWT HS256 với claims `sub`, `role`, `iat`, `exp`; token có hiệu lực 60 phút. Client gửi token ở `Authorization: Bearer <token>`. `verify_token` kiểm tra chữ ký và expiry, rồi trả danh tính/role. Thiếu credentials trả `401`; token không hợp lệ trả `403`. User demo là `student` (role `user`) và `teacher` (role `admin`); đây chỉ là tài khoản bài lab.

Đã đăng nhập bằng user demo mà không in token ra output, gửi request với token và quan sát: login thành công; student request được phép ban đầu; teacher/admin request được phép. Token không được lưu trong repo hay báo cáo. Trong production phải đưa `JWT_SECRET` từ secret manager; giá trị mặc định hardcode trong ví dụ chỉ phục vụ bài học.

### Exercise 4.3: Rate limiting

`production/rate_limiter.py` lưu timestamp từng request trong deque và loại bỏ timestamp cũ hơn cửa sổ 60 giây. Đây là rolling/sliding window dựa trên log request, không phải token bucket. Tier user giới hạn **10 request/phút**, admin **100 request/phút**; vượt quota trả `429` cùng `Retry-After` và các header `X-RateLimit-*`. `app.py` chọn limiter theo `role` lấy từ JWT đã xác minh.

Đã lấy token student và gọi `/ask` 12 lần tuần tự trong một cửa sổ:

```text
Requests 1–10: 200
Requests 11–12: 429
```

Thiết kế này giữ state trong RAM của một process; restart làm mất bộ đếm, nhiều worker/replica có bộ đếm riêng. Bản Part 6 đã dùng Redis-backed limiter để chia sẻ state giữa worker/restart. Không nên bypass rate limit chỉ theo dữ liệu do client gửi; quyền admin phải nằm trong token đã ký và chỉ cấp sau khi xác thực/ủy quyền đúng.

### Exercise 4.4: Cost guard

`production/cost_guard.py` cung cấp `check_budget(user_id, estimated_cost) -> bool`, reserve chi phí ước tính nguyên tử bằng Redis Lua trước LLM, mặc định budget **$10/user/tháng** và **$100 global/tháng**. Sau request, `record_usage(...)` ghi token thực và điều chỉnh reservation trong Redis transaction; nếu LLM lỗi thì giải phóng reservation. Keys theo tháng UTC và hết hạn đầu tháng kế tiếp. Cảnh báo bắt đầu ở **80%**. Khi không còn đủ budget, API từ chối request với `402`; Redis lỗi trả `503`. `/me/usage` trả usage/budget còn lại; `/admin/stats` đọc global total từ Redis.

Đã kiểm tra hợp đồng `check_budget(user_id, estimated_cost)` với Redis riêng trên port 16379, namespace cô lập và budget tạm $0.01:

```text
check_budget(student, $0.008): True, reservation accepted
record_usage: actual cost $0.006; reservation reconciled
new CostGuard instance, check_budget(student, $0.005): False
check_budget(other user, $0.005): True
POST /ask after monthly budget set to cap: HTTP 402
```

Đã chạy app tích hợp Redis: student đăng nhập JWT, 10 request đầu trả `200`, request 11–12 trả `429`; `/me/usage` báo 10 request, 40 input tokens, 304 output tokens, `$0.000188` đã dùng và `$9.9998116` còn lại. Teacher/admin `/ask` và `/admin/stats` trả `200`. Tests dùng mock LLM và Redis, không gọi provider hay phát sinh phí thật. Reservation được giới hạn nguyên tử trước khi gọi LLM; chi phí ước tính có thể lệch actual token cost nên hệ thống reconcile sau request.

### Câu hỏi thảo luận

1. **API Key vs JWT vs OAuth2:** API key phù hợp xác thực service-to-service đơn giản hoặc client nội bộ; JWT phù hợp session/user identity stateless có claims và expiry; OAuth2 phù hợp ủy quyền qua scopes/consent và tích hợp identity provider. OAuth2 là protocol cấp quyền; access token có thể là JWT hoặc dạng opaque.
2. **Rate limit cho AI agent:** đặt theo chi phí/latency và quota provider, giới hạn đồng thời và mức sử dụng từng user/plan; ví dụ bắt đầu 10 request/phút cho user thường, cao hơn cho admin/service đã được xác minh. Kèm giới hạn token/chi phí, trả `429` và `Retry-After`, theo dõi rồi điều chỉnh từ số liệu thực tế.
3. **Nếu API key bị lộ:** phát hiện qua log/metrics (địa chỉ, tần suất, mức chi phí và mẫu request bất thường); lập tức revoke/rotate key, cập nhật secret manager và redeploy, giới hạn quyền/quota, điều tra usage và scan nơi có thể đã lưu key. Không chỉ xóa key khỏi source vì Git history/log có thể vẫn chứa nó.

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks

- `GET /health` là **liveness**: process còn chạy không; orchestrator dùng để quyết định restart process/container.
- `GET /ready` là **readiness**: instance đã khởi tạo và có thể nhận traffic không; load balancer chỉ gửi traffic khi ready.
- Đã chạy app develop: `/health` trả `200` và status `ok`; `/ready` trả `200` và `ready=true`; `/ask?question=hello` trả `200`. Memory probe ghi `psutil not installed` nhưng endpoint vẫn hoạt động.

### Exercise 5.2: Graceful shutdown

Uvicorn xử lý SIGTERM, dừng nhận connection mới, đợi request đang chạy hoàn tất rồi gọi FastAPI lifespan shutdown. Middleware theo dõi `_in_flight_requests`; lifespan đưa readiness về false và đợi tối đa 30 giây. Tôi bỏ signal handler riêng trong `develop/app.py` vì handler cũ chỉ log rồi nuốt SIGTERM, làm Uvicorn không bắt đầu shutdown.

Đã chạy đúng lệnh `python app.py`, gửi hai POST `/ask` song song, chờ 0.5 giây rồi gửi SIGTERM trực tiếp tới process Uvicorn. Kết quả:

```text
in-flight statuses: [200, 200]
Uvicorn log: Shutting down
Uvicorn log: Waiting for application shutdown.
App log: Graceful shutdown initiated...
App log: Shutdown complete
Uvicorn log: Application shutdown complete.
Uvicorn log: Finished server process
```

### Exercise 5.3–5.5: Stateless, load balancing và failover

Production demo lưu conversation trong Redis với TTL 1 giờ và giới hạn lịch sử 20 message; agent không cần giữ session trong RAM nên request tiếp theo có thể đến instance khác. Nginx cân bằng round-robin tới service `agent`; Redis là store dùng chung.

Đã chạy stack riêng với ba replica bằng `docker compose -p k5-day14-scaling -f docker-compose.yml up -d --build --scale agent=3`. Compose xác nhận ba agent healthy, Redis healthy, Nginx expose cổng 8080; `/health` qua Nginx trả `200` và báo `storage=redis`, `redis_connected=true`.

`python3 test_stateless.py` gửi 5 turn, được phục vụ bởi cả 3 instance (`instance-d62a6e`, `instance-15a571`, `instance-6c1c5e`); history vẫn có đủ 10 message. Tôi kiểm tra thêm failover: tạo session trên `instance-d62a6e`, dừng container đó, gửi turn kế tiếp qua Nginx; instance khác trả `200` và Redis vẫn trả lịch sử đủ 4 message.

Sau kiểm tra đã dừng stack bằng `docker compose -p k5-day14-scaling -f docker-compose.yml down -v` và xóa `.env.local` tạm. Cấu hình Compose phát cảnh báo `version` đã obsolete ở Docker Compose mới, nhưng config hợp lệ và stack chạy được.

**Lưu ý thiết kế:** production demo có fallback sang in-memory nếu Redis không kết nối; khi fallback như vậy app chạy được nhưng không còn stateless/failover-safe. Kết quả Part 5 ở trên được lấy khi Redis healthy. Rate limiter của Part 4 là demo in-memory; Part 6 dùng Redis cho rate-limit state.

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

Smoke test Compose cũng đã chạy: `/health` 200, `/ready` 200, `/ask` thiếu API key 401 và `/ask` với key kiểm thử 200. Stack test đã được dừng và volume Redis tạm đã xóa. Agent đã deploy lên Railway; URL và bằng chứng deploy được ghi ở Part 3 và `DEPLOYMENT.md`.

## Part 7: Benchmark & Observability

### Exercise 7.2: Load test và SLO

Đã chạy v2 với 300 request ở concurrency 1/10/50/100 và `MOCK_SLOW_RATE=0/0.03/0.1`; số đo đầy đủ nằm trong `06-lab-complete/benchmark-observability/develop/reports/`. RPS đạt 107.47 ở concurrency 50 rồi giảm còn 75.42 ở 100; p95 tăng từ khoảng 220–227 ms lên 2,033 ms, vượt SLO 500 ms. Error rate ở 100 vẫn 0.67%, dưới SLO 2%. Slow rate 10% đẩy p95 lên 1,681.9 ms và p99 1,708.6 ms.

### Exercise 7.3: Eval và quality gate

Eval v1 đạt 1/23 (4.35%); v2 ban đầu đạt 21/23 (91.3%). Hai câu thiếu keyword là `security-02` và `scaling-03`; đã thêm nội dung JWT/API key và Kubernetes HPA vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py`, không sửa golden dataset. Eval v2 sau sửa đạt 23/23 (100%), quality gate min 100% pass và không có regression. Đã thêm workflow `.github/workflows/eval.yml` để fail PR nếu accuracy dưới 85%; báo cáo v1 so với v2 fixed thể hiện 22 regression và gate fail.

### Exercise 7.4–7.6: Observability, trace và alerts

Đã chạy stack Prometheus/Grafana/Jaeger/Locust. Đã sửa `production/Dockerfile` đặt `PYTHONUSERBASE=/home/agent/.local`; nếu không agent crash vì dependencies cài bằng `pip --user` không nằm trong Python user path.

Đã lưu Grafana dashboard khi có 30 Locust users tại `screenshots/grafana-dashboard.png`. Nginx chặn `/metrics` bằng 404; Prometheus scrape metrics qua network nội bộ. Jaeger slow trace `0dadee55e7fe10983684585d5ddf42ba` dài 1,723.69 ms, chủ yếu ở `chat mock-llm-small` (1,683.30 ms). Error trace `2e121925eb96a0b5396ffde584703b8b` trả HTTP 503 và có event exception. Cả hai ảnh và JSON trace đã lưu trong `screenshots/` và `production/benchmark-results/`; JSON/CSV cũng đã copy ra thư mục gốc `reports/` và `benchmark-results/` theo cấu trúc nộp.

Các alert đã kiểm chứng: A `AgentHighErrorRate` khoảng 68.1 giây; B `AgentHighLatencyP95` 132.1 giây; C `LLMCostBurnRateHigh` 147.1 giây với large model và burn rate $16.12/giờ; D `AgentInstanceDown` 42.1 giây sau khi pause một container. E chuyển sang v1 không tạo alert; eval gate phát hiện quality regression. Ảnh `screenshots/prometheus-alert-firing.png` cho thấy đồng thời `AgentHighErrorRate` và `LLMCostBurnRateHigh` đang firing; `promtool test rules` pass. Chi tiết times/screenshots trong `fault_experiment_A.json` đến `_E.json`.

### Exercise 7.7: Benchmark report và scale

`BENCHMARK_REPORT.md` đã được điền từ report JSON/CSV thật. Với 100 users trong 2 phút, một instance đạt 65.90 RPS và ba instance 65.83 RPS; p50/p95/p99 tương đương 190/220/1,700 ms, nên workload async/mock này không cho thấy throughput gain khi scale. CSV `scale_1_*` và `scale_3_*` nằm trong `production/benchmark-results/`. Dùng `--no-deps` cho Locust one-off để Compose không tự khởi động lại số replica mặc định và làm sai phép đo scale=1.

## AI log

- Hỗ trợ: đọc và đối chiếu yêu cầu Part 1, tìm anti-patterns trong hai phiên bản app, soạn nháp câu trả lời và lệnh kiểm tra.
- Tôi đã tự đối chiếu các nhận xét với `develop/app.py`, `production/app.py`, `production/config.py` và chạy thử hai server. Basic trả HTTP 200 với query parameter; production-style trả HTTP 200 cho JSON `/ask`, `/health` và `/ready`.
- Kết quả ban đầu Part 1 chỉ test endpoint; graceful shutdown sau đó được kiểm tra ở Part 5 và deploy thật được kiểm tra ở Part 3.
- Part 2: hỗ trợ đọc Dockerfiles/Compose và tổng hợp câu trả lời; tôi đã tự build hai image, lấy kích thước bằng `docker image inspect`, chạy container basic và Compose stack, rồi thử endpoint qua container/Nginx.
- Part 3: hỗ trợ đọc tiêu chí/config, soạn phần so sánh/pipeline và hồ sơ deploy; sinh viên cung cấp Railway URL và tự chạy bốn lệnh CP6. Tôi xác minh độc lập `/health`, `/ready` trả 200 và unauthenticated `/ask` trả 401; không ghi lại giá trị API key.
- Part 6: hỗ trợ triển khai các module và cấu hình theo hợp đồng checker; tôi chạy checker đầy đủ đến PASS 12/12 (41/41), smoke test Compose và kiểm tra các endpoint. Docker build/test dùng Python 3.11 trong image; môi trường host Python 3.14 không cài được pin `pydantic==2.9.0`, nên checker được chạy bằng venv tạm với dependency tương thích.
- Part 4: hỗ trợ đọc/sửa code và soạn đáp án; tôi chạy API key missing/invalid/valid (401/403/200), JWT/rate limit, Redis monthly budget reservation/reconciliation, xác nhận budget block 402, usage tách biệt theo user và admin endpoints.
- Part 5: hỗ trợ đọc/sửa phần shutdown và soạn đáp án; tôi kiểm tra health/readiness, gửi SIGTERM khi hai request đang chạy (cả hai 200), scale Compose lên ba agent, chạy `test_stateless.py` và dừng container đang sở hữu session để xác minh history vẫn còn qua Redis.
- Part 7: hỗ trợ sửa KB, Dockerfile observability và workflow quality gate, tổng hợp report; tôi chạy load/eval, Locust scale 1/3, promtool, fault injection, query Jaeger/Prometheus và xác minh screenshots/artifacts. Không dùng số liệu ước lượng thay cho file kết quả.
