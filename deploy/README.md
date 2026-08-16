# 认证服务部署说明

## 方式一：Docker 部署（推荐）

```bash
# 1. 准备配置文件
cp auth_config.example.json data/auth_config.json
# 编辑 data/auth_config.json 修改用户名/密码

# 2. 启动
docker-compose up -d

# 3. 验证
curl http://localhost:8001/health
# 返回 {"status":"ok"}
```

## 方式二：直接运行

```bash
pip install fastapi uvicorn httpx
AUTH_CONFIG_PATH=./data/auth_config.json
uvicorn auth_service:app --host 0.0.0.0 --port 8001
```

## 配置说明

### 配置文件 `data/auth_config.json`

```json
{
  "users": [
    {"username": "admin", "password": "admin123", "name": "管理员", "role": "admin"},
    {"username": "user1", "password": "user123", "name": "用户一", "role": "user"}
  ]
}
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AUTH_CONFIG_PATH` | `data/auth_config.json` | 配置文件路径 |
| `AUTH_CORS_ORIGINS` | `*` | 允许的 CORS 来源（逗号分隔） |
| `PASSWORD_SALT` | `excel-merger-salt` | 密码哈希盐值 |
| `AUTH_HOST` | `0.0.0.0` | 监听地址 |
| `AUTH_PORT` | `8001` | 监听端口 |

## 桌面应用连接

在桌面应用的 `data/auth_service_url.txt` 中写入认证服务地址：

```
http://your-server-ip:8001
```

或通过环境变量 `AUTH_SERVICE_URL=http://your-server-ip:8001` 设置。

## Nginx 反向代理（可选）

```nginx
location /auth/ {
    proxy_pass http://127.0.0.1:8001/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

此时桌面应用配置地址为 `https://your-domain.com/auth`。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/health` | 健康检查 |
| POST | `/login` | 登录（用户名+密码） |
| GET  | `/users` | 用户列表 |
| POST | `/users` | 添加用户 |
| PUT  | `/users/{username}/password` | 修改密码 |
| DELETE | `/users/{username}` | 删除用户 |
