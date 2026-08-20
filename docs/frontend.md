# 最小研判控制台

前端使用 Vue 3、TypeScript 和 Vite，生产镜像通过 Nginx 提供静态文件，并将 `/api` 反向代理到 Backend。

## 功能

- 查看和快速创建案件
- 启动最小 LangGraph 研判流程
- 展示案件准备、人工复核、完成归档三个节点
- 通过 SSE 接收最新 checkpoint 快照
- 在 interrupt 节点批准或退回流程
- 使用 `thread_id` 在刷新、SSE 断线或 Backend 重启后恢复看板

当前 SSE 是状态快照流，不是完整的历史事件日志。它以 PostgreSQL checkpointer 为事实来源，每秒检查一次状态变化；后续业务节点变多、运行时间变长时，再增加 `workflow_runs`、`workflow_events` 表和持久化任务执行器。

## 启动

完整环境：

```bash
docker compose up -d --build
```

访问 `http://localhost:8080`。可通过 `.env` 中的 `FRONTEND_PORT` 修改宿主机端口。

仅启动本地前端开发服务器（Backend 需要运行在 8000 端口）：

```bash
cd frontend
npm install
npm run dev
```

类型检查和生产构建：

```bash
npm run typecheck
npm run build
```

SSE 接口为 `GET /api/v1/workflows/{thread_id}/events`，事件名为 `workflow_snapshot`。Nginx 已关闭该路径的响应缓冲。
