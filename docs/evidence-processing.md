# 证据读取与标准化底座

## 存储边界

- MinIO：原始证据、邮件附件、完整标准化 JSON。
- PostgreSQL：处理任务、租约与重试、标准化文档索引、正文预览、附件血缘。
- `evidence` 始终代表可追溯的原始或派生证据；`normalized_documents` 是解析结果，不替代原件。

## 处理链路

1. 上传证据并记录 SHA-256、对象键和审计事件。
2. 调用 `POST /api/v1/cases/{case_id}/evidence/{evidence_id}/processing-jobs` 入队。
3. `evidence-worker` 使用 `FOR UPDATE SKIP LOCKED` 原子领取任务并设置租约。
4. Worker 从 MinIO 下载到隔离临时目录，并再次核对文件大小和 SHA-256。
5. 解析器注册表按证据类型选择解析器；当前实现 `EML`。
6. 标准化 JSON 写入 MinIO，索引和最多 2000 字正文预览写入 PostgreSQL。
7. 邮件附件写入 MinIO，并创建带 `parent_evidence_id` 的子证据和 derivative 血缘。
8. 成功、待 OCR、不支持、失败均持久化；Worker 崩溃后租约到期可重新领取。

## 标准化协议 1.0

标准化 JSON 包含：

- `source`：证据 ID、原始文件名、SHA-256；
- `document`：文档类型、标题、纯文本正文、语言；
- `metadata`：解析器提取的结构化字段；
- `attachments`：附件文件名、MIME 和大小。

EML 的 `metadata.headers` 当前包含 From、To、Cc、Bcc、Date、Message-ID 和 In-Reply-To。HTML 邮件只提取纯文本，不在网页端直接渲染原始 HTML。

## 当前支持边界

- `.eml`：正文、核心邮件头、附件提取。
- `.txt`：UTF-8、GB18030、UTF-16 文本读取。
- `.csv`：编码与常见分隔符识别、行列结构提取。
- `.xls` / `.xlsx`：工作表、行列和单元格内容提取。
- `.docx`：段落、表格和核心文档属性提取。
- `.pdf`：逐页文本和文档属性提取；无文本扫描件会标记 `ocr_recommended`。
- `.doc`：旧版二进制格式仍为 `UNSUPPORTED`，后续通过隔离的 LibreOffice 转换服务处理。
- 图片：任务进入 `OCR_REQUIRED`，尚未接 OCR。
- 附件数量上限 100，总大小上限 100 MiB；可执行扩展名只作为隔离证据保存并标记 `quarantined`，不会执行。
- Office 压缩容器会检查文件数量、展开大小、压缩比和加密标记；PDF、表格及正文均设置资源上限。

## API

- `POST /api/v1/cases/{case_id}/evidence/{evidence_id}/processing-jobs`
- `GET /api/v1/cases/{case_id}/evidence/processing-jobs`
- `GET /api/v1/cases/{case_id}/evidence/{evidence_id}/normalized`

入队请求使用 `idempotency_key` 防止客户端重复提交。
