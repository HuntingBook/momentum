# A股可视化选股与量化交易系统 (Momentum)

## 🛠 技术栈
- **Frontend**: React 18 + Vite + TypeScript + Tailwind CSS + Shadcn/ui
- **Backend**: FastAPI + SQLModel + Pandas
- **Database**: PostgreSQL 15 + Redis 7

## 🚀 启动指南 (How to Run)
1. 确保 Docker Desktop 已启动。
2. 在项目根目录 (`momentum`) 执行：
   ```bash
   docker compose up --build
   ```
3. 等待容器启动完成。

## 🔗 服务地址 (Services)
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs
- **Database**: localhost:5432 (user: postgres / pass: password)
- **Redis**: localhost:6379

## 🧪 测试账号
*(暂无，目前无需登录)*

---

## ⚠️ 开发注意
- 前端代码位于 `frontend/`，后端代码位于 `backend/`。
- 修改后端代码后，热重载会自动生效 (挂载了 volume)。
- 数据库数据持久化存储在 Docker Volume `postgres_data` 中。
