# 鲸鲨 MAS 第一阶段开发 Prompt：后端基础与数据持久化

你是一名资深 Python 后端架构师、AI Agent 系统架构师和数据工程师。

现在需要从零开始开发：

**鲸鲨 MAS 多智能体研判系统**

当前只实施**第一阶段**。

本阶段不要开发完整业务功能，不要开发前端，不要提前实现复杂 Agent。

目标是建立后续 LangGraph、多 Agent、Human-in-the-loop、案件研判流程能够稳定运行的基础工程。

---

# 一、本阶段目标

本阶段只完成：

```text
Backend Project Foundation
        +
PostgreSQL
        +
Alembic
        +
SQLAlchemy Async
        +
MinIO
        +
Case 数据模型
        +
Evidence 数据模型
        +
AuditEvent 审计模型
        +
基础 Repository / Service
        +
案件 API
        +
证据上传 API
        +
SHA-256 证据固化
        +
Docker Compose
        +
自动化测试
```

本阶段完成以后，必须能够：

```text
创建案件
    ↓
上传案件证据
    ↓
计算 SHA-256
    ↓
文件保存到 MinIO
    ↓
元数据保存到 PostgreSQL
    ↓
写 AuditEvent
    ↓
通过 API 查询案件和证据
```

---

# 二、本阶段明确不要做的内容

本阶段禁止扩展以下内容：

```text
前端
Vue
React

真实 LLM

Evidence Agent
Analysis Agent
Relation Agent
Report Agent

完整 LangGraph Workflow

LangGraph interrupt

LangGraph checkpoint

Human-in-the-loop

LangSmith

MCP

AgentTeams

A2A

OCR 实际识别

银行流水业务分析

邮件语义提取

报关四维比对

风险评分

报告生成
```

这些属于后续阶段。

但是代码架构必须为这些功能留下清晰扩展位置。

不要提前实现。

---

# 三、技术栈

后端使用：

```text
Python 3.12+

FastAPI

Pydantic v2

SQLAlchemy 2.x Async

PostgreSQL

asyncpg

Alembic

MinIO

pytest

pytest-asyncio

httpx

ruff

mypy
```

依赖通过：

```text
pyproject.toml
```

管理。

优先使用现代 Python async 架构。

---

# 四、项目目录

创建如下项目结构：

```text
whale-mas/
│
├── backend/
│   │
│   ├── app/
│   │   │
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   │
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       ├── health.py
│   │   │       ├── cases.py
│   │   │       └── evidence.py
│   │   │
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── types.py
│   │   │
│   │   ├── models/
│   │   │   ├── case.py
│   │   │   ├── evidence.py
│   │   │   └── audit_event.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── case.py
│   │   │   ├── evidence.py
│   │   │   ├── audit.py
│   │   │   └── common.py
│   │   │
│   │   ├── repositories/
│   │   │   ├── case_repository.py
│   │   │   ├── evidence_repository.py
│   │   │   └── audit_repository.py
│   │   │
│   │   ├── services/
│   │   │   ├── case_service.py
│   │   │   ├── evidence_service.py
│   │   │   └── audit_service.py
│   │   │
│   │   ├── storage/
│   │   │   ├── base.py
│   │   │   └── minio_storage.py
│   │   │
│   │   ├── security/
│   │   │   └── file_validation.py
│   │   │
│   │   └── utils/
│   │       ├── hashing.py
│   │       └── ids.py
│   │
│   ├── alembic/
│   │
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── api/
│   │
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── Dockerfile
│
├── docs/
│   ├── architecture.md
│   ├── database.md
│   ├── development.md
│   └── progress.md
│
├── scripts/
│
├── docker-compose.yml
├── .env.example
├── Makefile
├── .gitignore
└── README.md
```

可以根据最佳实践微调，但是不要把所有逻辑写进：

```text
main.py
```

---

# 五、架构分层要求

必须严格采用：

```text
API
 ↓
Service
 ↓
Repository
 ↓
Database
```

文件存储：

```text
API
 ↓
EvidenceService
 ↓
Storage abstraction
 ↓
MinIOStorage
```

禁止：

```text
FastAPI endpoint
直接写 SQL
```

禁止：

```text
FastAPI endpoint
直接操作 MinIO Client
```

---

# 六、配置管理

使用：

```text
pydantic-settings
```

创建统一：

```python
Settings
```

至少支持：

```env
APP_NAME=Whale MAS
APP_ENV=development
APP_DEBUG=true

API_V1_PREFIX=/api/v1

DATABASE_URL=postgresql+asyncpg://...

MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
MINIO_BUCKET=whale-mas
MINIO_SECURE=false

MAX_UPLOAD_SIZE_MB=100

ALLOWED_FILE_EXTENSIONS=.eml,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.jpg,.jpeg,.png

AUDIT_HASH_CHAIN_ENABLED=true
```

所有 secret 从环境变量加载。

禁止把密码写入代码。

提供：

```text
.env.example
```

但不能提交真实密码。

---

# 七、数据库基础要求

使用：

```text
PostgreSQL

SQLAlchemy 2.x

AsyncSession
```

数据库 session 必须使用依赖注入。

建议：

```python
async_sessionmaker
```

不要使用同步 SQLAlchemy。

---

# 八、数据库 ID

数据库内部 ID 不使用业务编号作为主键。

推荐：

```text
UUID
```

至少包括：

```text
case_id
evidence_id
audit_event_id
```

业务案件编号单独保存：

```text
case_no
```

例如：

```text
CASE-2026-000001
```

---

# 九、Case 数据模型

建立：

```text
cases
```

字段至少：

```text
id UUID PK

case_no VARCHAR UNIQUE NOT NULL

name VARCHAR NOT NULL

description TEXT NULL

status VARCHAR NOT NULL

created_by VARCHAR NULL

created_at TIMESTAMP WITH TIME ZONE

updated_at TIMESTAMP WITH TIME ZONE
```

案件状态定义 Enum：

```text
CREATED
UPLOADING
READY
RUNNING
WAITING_RISK_REVIEW
WAITING_REPORT_REVIEW
COMPLETED
FAILED
ARCHIVED
```

虽然当前阶段只使用前几个状态，但是完整 Enum 可以提前定义。

不要使用数据库业务字段作为主键。

---

# 十、Evidence 数据模型

建立：

```text
evidence
```

字段至少：

```text
id UUID PK

case_id UUID FK

original_filename

stored_filename

object_key

mime_type

file_extension

file_size

sha256

source_type

document_type

parent_evidence_id UUID NULL

metadata_json JSONB

created_by

created_at
```

其中：

```text
source_type
```

Enum：

```text
EMAIL
BANK
CUSTOMS
OTHER
```

document_type 第一阶段可以：

```text
UNKNOWN
EMAIL
PDF
EXCEL
CSV
WORD
IMAGE
TEXT
```

以后业务解析阶段再扩展：

```text
PI
PO
INVOICE
PACKING_LIST
EIR
CONTRACT
CONTAINER_RELEASE
```

---

# 十一、Evidence 父子关系

需要支持：

```text
邮件
 ↓
邮件附件
```

因此 Evidence 要有：

```text
parent_evidence_id
```

第一阶段暂时不需要真正解析 EML 附件。

但是数据库模型必须支持后续：

```text
email evidence

attachment evidence
```

之间的父子关系。

---

# 十二、MinIO 对象路径

所有案件证据按照：

```text
cases/{case_id}/evidence/{evidence_id}/{safe_filename}
```

保存。

例如：

```text
cases/
  4bb...
    evidence/
      12aa...
        invoice.pdf
```

禁止：

```text
用户提供什么路径
就直接写什么路径
```

必须防止：

```text
../
```

path traversal。

---

# 十三、SHA-256

实现：

```python
sha256_file(...)
```

或者流式：

```python
sha256_stream(...)
```

大文件必须采用 streaming hash。

禁止：

```text
一次性把 500MB 文件读进内存
```

SHA-256 在上传 MinIO 前计算。

最终：

```text
Evidence.sha256
```

必须保存。

---

# 十四、上传流程

证据上传流程必须严格为：

```text
接收 UploadFile
      ↓
验证文件
      ↓
生成 evidence_id
      ↓
写临时文件 / streaming
      ↓
计算 SHA-256
      ↓
生成安全文件名
      ↓
上传 MinIO
      ↓
创建 Evidence DB record
      ↓
写 AuditEvent
      ↓
返回 EvidenceResponse
```

必须考虑失败清理。

例如：

```text
MinIO 成功
DB 失败
```

不能留下完全无法管理的垃圾对象。

采用补偿删除，或者清晰可靠的失败处理机制。

---

# 十五、文件安全

实现：

```text
FileValidator
```

至少检查：

```text
扩展名

MIME type

文件大小

空文件

文件名清洗
```

禁止：

```text
.exe
.sh
.bat
```

默认上传。

禁止相信：

```text
Content-Type
```

作为唯一判断依据。

第一阶段至少结合：

```text
extension
+
declared MIME
```

未来可以增加 magic bytes。

---

# 十六、AuditEvent

建立独立：

```text
audit_events
```

表。

它不是应用日志。

它是业务审计事件。

字段至少：

```text
id UUID PK

case_id UUID NULL

event_type

actor_id

resource_type

resource_id

operation

input_hash

output_hash

metadata_json JSONB

previous_hash

event_hash

created_at
```

AuditEvent 默认：

```text
append-only
```

应用层禁止：

```text
UPDATE audit_events
DELETE audit_events
```

---

# 十七、第一阶段 Audit Event 类型

至少实现：

```text
CASE_CREATED

CASE_UPDATED

EVIDENCE_UPLOAD_STARTED

EVIDENCE_HASHED

EVIDENCE_STORED

EVIDENCE_CREATED

EVIDENCE_UPLOAD_FAILED

EVIDENCE_DELETED

AUDIT_CHAIN_VERIFIED
```

如果实现 DELETE Evidence API：

只删除业务证据和 MinIO 文件。

AuditEvent 本身不能删除。

---

# 十八、审计 Hash Chain

实现基础防篡改链。

每个案件自己的 AuditEvent 按时间形成：

```text
Event 1
 ↓
Event 2
 ↓
Event 3
```

字段：

```text
previous_hash
event_hash
```

event_hash：

```text
SHA256(
 previous_hash
 +
 canonical_event_content
)
```

canonical_event_content 必须使用稳定 JSON 序列化。

例如：

```text
sort_keys=True
固定 UTF-8
固定 datetime ISO 格式
```

实现：

```python
verify_audit_chain(case_id)
```

用于检查链是否完整。

注意：

这是系统审计增强能力。

不要在代码或者文档中声称它本身等价于司法电子取证认证。

---

# 十九、Storage 抽象

建立：

```python
class ObjectStorage(Protocol):
```

接口至少：

```python
async def put(...)
async def get(...)
async def delete(...)
async def exists(...)
```

实现：

```text
MinIOStorage
```

业务 Service 不直接依赖：

```text
Minio(...)
```

方便未来替换：

```text
S3
OSS
私有对象存储
```

---

# 二十、Repository

至少实现：

```text
CaseRepository

EvidenceRepository

AuditRepository
```

Repository 负责数据库 CRUD。

Service 负责业务。

Repository 不负责：

```text
HTTP
MinIO
业务规则
```

---

# 二十一、CaseService

实现：

```python
create_case()

get_case()

list_cases()

update_case()
```

创建案件时生成：

```text
case_no
```

不要使用：

```text
SELECT MAX(case_no) + 1
```

这种并发不安全方式。

可以采用：

```text
UUID-based readable ID
```

或者 PostgreSQL sequence。

如果使用格式：

```text
CASE-2026-000001
```

必须保证并发安全。

---

# 二十二、EvidenceService

至少实现：

```python
upload_evidence()

get_evidence()

list_evidence()

delete_evidence()
```

upload_evidence 必须统一负责：

```text
validation
hash
storage
database
audit
```

而不是分散到 API endpoint。

---

# 二十三、API

统一：

```text
/api/v1
```

---

## Health

实现：

```text
GET /api/v1/health
```

返回：

```json
{
  "status": "ok"
}
```

另外实现：

```text
GET /api/v1/health/ready
```

检查：

```text
PostgreSQL
MinIO
```

---

## Case API

实现：

```text
POST /api/v1/cases

GET /api/v1/cases

GET /api/v1/cases/{case_id}

PATCH /api/v1/cases/{case_id}
```

---

## Evidence API

实现：

```text
POST /api/v1/cases/{case_id}/evidence

GET /api/v1/cases/{case_id}/evidence

GET /api/v1/cases/{case_id}/evidence/{evidence_id}

DELETE /api/v1/cases/{case_id}/evidence/{evidence_id}
```

上传采用：

```text
multipart/form-data
```

同时允许参数：

```text
source_type
```

例如：

```text
EMAIL
BANK
CUSTOMS
OTHER
```

---

## Audit API

实现：

```text
GET /api/v1/cases/{case_id}/audit
```

以及：

```text
GET /api/v1/cases/{case_id}/audit/verify
```

verify 返回类似：

```json
{
  "valid": true,
  "event_count": 8,
  "broken_event_id": null
}
```

---

# 二十四、Pydantic Schema

必须严格区分：

```text
ORM Model

Request Schema

Response Schema
```

例如：

```text
CaseCreate

CaseUpdate

CaseResponse

EvidenceResponse

AuditEventResponse
```

不要直接把 SQLAlchemy Model 返回 API。

---

# 二十五、统一响应和错误

建立统一异常：

```text
DomainError

NotFoundError

StorageError

EvidenceValidationError

ConflictError
```

API 错误结构：

```json
{
  "error": {
    "code": "EVIDENCE_INVALID_TYPE",
    "message": "Unsupported evidence file type",
    "request_id": "..."
  }
}
```

不要向客户端暴露：

```text
数据库密码
MinIO Secret
完整 Python Stack Trace
```

---

# 二十六、Request ID

每个 HTTP Request 自动生成：

```text
request_id
```

通过 middleware 注入。

日志和错误返回均包含：

```text
request_id
```

方便以后结合：

```text
case_id
run_id
thread_id
```

形成完整链路。

---

# 二十七、日志

使用 Python logging 或 structlog。

推荐：

```text
structlog
```

使用结构化 JSON log。

至少包含：

```text
timestamp
level
request_id
case_id
operation
```

禁止日志直接输出：

```text
文件完整内容
银行流水内容
邮件正文
Secret
API Key
数据库密码
```

---

# 二十八、Alembic

必须初始化：

```text
Alembic
```

创建第一版 migration。

Migration 至少创建：

```text
cases

evidence

audit_events
```

运行：

```bash
alembic upgrade head
```

能够成功初始化数据库。

不要依赖：

```text
Base.metadata.create_all()
```

作为正式 migration 方案。

---

# 二十九、Docker Compose

第一阶段只需要：

```text
postgres

minio

minio-init

backend
```

不要启动前端。

例如：

```text
docker compose up -d
```

必须能够启动：

```text
PostgreSQL

MinIO

Backend
```

MinIO init 自动创建：

```text
whale-mas
```

bucket。

---

# 三十、Backend Dockerfile

创建生产化基础 Dockerfile。

注意：

```text
非 root 用户运行

合理利用 Docker layer cache

不要把 .env 打进镜像

不要复制 tests/demo data 到生产镜像，除非确有必要
```

同时提供开发模式。

---

# 三十一、Makefile

提供至少：

```text
make up

make down

make logs

make migrate

make test

make lint

make format

make typecheck
```

---

# 三十二、测试

必须认真写测试。

不要只写空测试。

---

## Unit Test

至少覆盖：

```text
SHA256

safe filename

file validation

case number generator

audit canonical JSON

audit event hash

audit hash chain verification
```

---

## Repository Test

覆盖：

```text
Case create/get/list

Evidence create/get/list

Audit append
```

---

## API Test

至少：

```text
GET /health

POST /cases

GET /cases

GET /cases/{id}

POST evidence

GET evidence
```

---

## Integration Test

使用测试文件：

```text
sample.eml

bank.csv

customs.csv
```

内容全部使用虚构数据。

测试：

```text
创建 Case
 ↓
上传 sample.eml
 ↓
SHA256 生成
 ↓
MinIO 存在对象
 ↓
PostgreSQL 存在 Evidence
 ↓
AuditEvent 存在
 ↓
GET evidence 返回正确
 ↓
audit verify = true
```

---

# 三十三、事务与一致性

重点处理：

```text
PostgreSQL
+
MinIO
```

之间不存在分布式事务的问题。

不要假装有 ACID 跨系统事务。

实现明确的补偿逻辑。

例如上传流程：

```text
MinIO put success
 ↓
DB insert fails
 ↓
attempt MinIO delete
 ↓
记录 error log
```

如果补偿也失败：

必须记录明确错误。

代码中注释说明：

```text
eventual cleanup / compensation strategy
```

未来可以增加 orphan cleanup job。

第一阶段不需要实现复杂任务队列。

---

# 三十四、幂等性

证据上传至少考虑：

```text
同案件
+
相同 SHA256
```

的重复上传。

不要简单偷偷忽略。

推荐行为：

返回：

```text
409 CONFLICT
```

并告诉调用方：

```text
duplicate evidence
```

同时在数据库增加适当唯一约束：

例如：

```text
(case_id, sha256)
```

如果产品未来允许同一文件重复出现，则要重新评估。

第一阶段按：

```text
同案件相同 SHA256 不重复存储
```

实现。

---

# 三十五、数据库索引

至少为以下字段建立索引：

```text
cases.case_no

cases.status

evidence.case_id

evidence.sha256

evidence.source_type

audit_events.case_id

audit_events.created_at
```

考虑：

```text
(case_id, sha256)
```

复合唯一约束。

---

# 三十六、删除 Evidence

如果实现：

```text
DELETE evidence
```

流程：

```text
检查 Case

检查 Evidence

删除 MinIO object

删除 Evidence DB record

写 EVIDENCE_DELETED AuditEvent
```

不能删除历史 AuditEvent。

如果 MinIO 删除失败：

不要静默成功。

---

# 三十七、README

第一阶段 README 必须写清楚：

```text
项目介绍

第一阶段范围

技术栈

目录结构

环境要求

启动 PostgreSQL + MinIO + Backend

环境变量

数据库 migration

运行测试

API 使用方式
```

并给出 curl 示例。

例如：

```bash
curl -X POST http://localhost:8000/api/v1/cases \
  -H "Content-Type: application/json" \
  -d '{
    "name":"测试低报价格案件",
    "description":"第一阶段测试案件"
  }'
```

以及：

```bash
curl -X POST \
  http://localhost:8000/api/v1/cases/{case_id}/evidence \
  -F "file=@demo_data/sample.eml" \
  -F "source_type=EMAIL"
```

---

# 三十八、文档

创建：

```text
docs/architecture.md

docs/database.md

docs/development.md

docs/progress.md
```

architecture.md 使用 Mermaid 表示：

```text
FastAPI
 ↓
Service
 ↓
Repository
 ↓
PostgreSQL

EvidenceService
 ↓
MinIO
```

database.md 使用 Mermaid ER Diagram。

---

# 三十九、预留 LangGraph 目录

虽然第一阶段不实现 LangGraph：

仍创建：

```text
backend/app/graph/
```

可以只保留：

```text
__init__.py
README.md
```

README 说明：

下一阶段将在这里增加：

```text
CaseState

StateGraph

Postgres Checkpointer

interrupt

resume
```

不要现在伪实现。

---

# 四十、预留 Agent 目录

创建：

```text
backend/app/agents/
```

仅：

```text
__init__.py
README.md
```

不要创建大量空的：

```text
evidence_agent.py
analysis_agent.py
```

下一阶段实际使用时再创建。

---

# 四十一、预留 Parser 和 Tool

可以创建：

```text
app/parsers/
app/tools/
```

但第一阶段只实现真正需要的：

```text
hashing
file validation
```

不要提前写：

```text
OCR
报关比对
税额计算
```

的空壳。

---

# 四十二、代码质量

必须执行：

```bash
ruff check .

ruff format --check .

mypy app

pytest
```

如果失败：

修复以后才能完成本阶段。

禁止：

```text
为了通过 mypy
大量使用 Any
```

---

# 四十三、不要出现以下代码

禁止：

```text
TODO: implement later
```

出现在当前第一阶段已经要求实现的功能。

禁止：

```python
pass
```

作为正式实现。

禁止：

```text
mock database

mock MinIO
```

作为最终运行逻辑。

测试中可以 mock。

生产代码必须真正连接：

```text
PostgreSQL
MinIO
```

---

# 四十四、第一阶段验收测试

最终必须能够实际完成以下流程。

启动：

```bash
docker compose up -d
```

查看：

```bash
docker compose ps
```

PostgreSQL：

```text
healthy
```

MinIO：

```text
healthy
```

Backend：

```text
running
```

然后：

### Step 1

```text
GET /api/v1/health
```

返回：

```json
{
  "status": "ok"
}
```

### Step 2

创建案件。

返回：

```text
case_id
case_no
status=CREATED
```

### Step 3

上传：

```text
sample.eml
```

系统必须：

```text
校验文件
计算 SHA256
上传 MinIO
保存 Evidence
写 AuditEvent
```

### Step 4

查询 Evidence。

必须返回：

```text
evidence_id

original_filename

object_key

sha256

source_type

file_size
```

### Step 5

直接检查 MinIO。

文件必须真实存在。

### Step 6

直接查询 PostgreSQL。

必须存在：

```text
Case

Evidence

AuditEvent
```

### Step 7

调用：

```text
GET /api/v1/cases/{case_id}/audit
```

能够看到：

```text
CASE_CREATED

EVIDENCE_UPLOAD_STARTED

EVIDENCE_HASHED

EVIDENCE_STORED

EVIDENCE_CREATED
```

等事件。

### Step 8

调用：

```text
GET /api/v1/cases/{case_id}/audit/verify
```

必须：

```json
{
  "valid": true
}
```

### Step 9

再次上传完全相同文件。

必须正确返回：

```text
409
```

不得生成重复 Evidence。

### Step 10

运行：

```bash
make test
```

全部通过。

---

# 四十五、本阶段完成标准

只有同时满足以下条件才算第一阶段完成：

```text
[ ] 项目目录合理

[ ] FastAPI 可以启动

[ ] PostgreSQL 可以正常连接

[ ] MinIO 可以正常连接

[ ] Alembic migration 可以执行

[ ] 可以创建 Case

[ ] 可以上传 Evidence

[ ] Evidence 真正保存到 MinIO

[ ] SHA256 正确保存

[ ] Evidence 元数据保存 PostgreSQL

[ ] AuditEvent 正常写入

[ ] Audit hash chain 可以验证

[ ] duplicate evidence 有幂等保护

[ ] API tests 通过

[ ] integration tests 通过

[ ] ruff 通过

[ ] mypy 通过

[ ] docker compose 可以完整启动

[ ] README 完整
```

任何一个核心项目失败，不要宣布第一阶段完成。

---

# 四十六、Codex 工作方式

现在检查当前 repository。

如果目录为空：

立即开始创建项目。

如果已有代码：

先检查现有结构和实现，不要直接覆盖正确代码。

首先创建：

```text
docs/progress.md
```

记录：

```text
Task
Status
Files
Test Result
Notes
```

然后开始实现。

工作顺序：

```text
1. Repository bootstrap

2. pyproject.toml

3. Settings

4. FastAPI

5. Docker Compose

6. PostgreSQL

7. SQLAlchemy

8. Alembic

9. Models

10. Repositories

11. MinIO Storage

12. AuditService

13. Services

14. APIs

15. Tests

16. Documentation

17. Full verification
```

每完成一个模块：

立即运行相关测试。

不要等整个系统写完以后再测试。

---

# 四十七、不要停在“生成代码”

你有终端和项目文件访问能力。

因此必须实际：

```text
创建文件

安装依赖

运行 migration

运行测试

运行 lint

运行 typecheck

构建 Docker image

启动 docker compose

检查服务日志

实际调用 API

修复错误
```

不要只告诉用户：

```text
“代码已经准备好了，你可以运行……”
```

你自己必须先运行验证。

---

# 四十八、遇到技术问题

如果某个库 API 不确定：

优先检查：

```text
当前安装版本
官方文档
本地 package API
```

不要根据旧版本记忆猜 API。

如果存在多个工程方案：

选择：

```text
简单
可靠
异步友好
可测试
可扩展
低耦合
```

的方案。

不要为了“架构高级”增加不必要组件。

---

# 四十九、当前阶段的核心原则

始终记住：

```text
第一阶段不是做 Agent。

第一阶段不是做 LangGraph。

第一阶段是在建立：

案件数据底座
+
证据数据底座
+
对象存储
+
业务审计底座
+
稳定后端工程。
```

下一阶段才会在这套底座上增加：

```text
LangGraph
+
PostgreSQL Checkpointer
+
CaseState
+
interrupt
+
resume
```

因此本阶段的数据库模型和 Service API 必须足够干净，能够被下一阶段直接复用。

---

# 五十、立即执行

现在立即：

```text
1. 检查 repository

2. 输出当前目录状态

3. 创建 docs/progress.md

4. 搭建 backend 项目骨架

5. 配置 PostgreSQL + MinIO Docker Compose

6. 实现数据库和 migration

7. 实现 Case / Evidence / AuditEvent

8. 实现 MinIO Storage

9. 实现 SHA256 和文件验证

10. 实现 Service / Repository

11. 实现 REST API

12. 编写测试

13. 启动完整环境

14. 实际创建一个测试案件

15. 实际上传一个测试文件

16. 验证 PostgreSQL / MinIO / AuditEvent

17. 运行完整测试

18. 修复全部发现的问题

19. 更新 docs/progress.md

20. 输出第一阶段最终完成情况
```

不要继续开发第二阶段。

完成第一阶段并验证所有验收项以后停止。
