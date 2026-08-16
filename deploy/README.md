# 认证服务部署说明

## 方式一：Docker 部署（推荐）

```bash
# 1. 准备配置文件
cp auth_config.example.json data/auth_config.json
# 编辑 data/auth_config.json 修改用户名/密码

# 2. 设置服务间通信密钥（重要！）
export SERVICE_TOKEN="your-random-secret-string"

# 3. 启动
docker-compose up -d

# 4. 验证
curl http://localhost:8001/health
# 返回 {"status":"ok"}
```

## 方式二：直接运行

```bash
pip install fastapi uvicorn httpx
export SERVICE_TOKEN="your-random-secret-string"
export AUTH_CONFIG_PATH=./data/auth_config.json
uvicorn auth_service:app --host 0.0.0.0 --port 8001
```

## 配置说明

### 配置文件 `data/auth_config.json`

```json
{
  "users": [
    {
      "username": "admin",
      "password": "admin123",
      "name": "管理员",
      "role": "admin",
      "enabled": true
    },
    {
      "username": "user1",
      "password": "user123",
      "name": "用户一",
      "role": "user",
      "enabled": true
    }
  ]
}
```

> `enabled` 字段可省略，默认为 `true`。设为 `false` 则该用户无法登录。

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AUTH_CONFIG_PATH` | `data/auth_config.json` | 配置文件路径 |
| `AUTH_CORS_ORIGINS` | `*` | 允许的 CORS 来源（逗号分隔） |
| `PASSWORD_SALT` | `excel-merger-salt` | 密码哈希盐值 |
| `AUTH_HOST` | `0.0.0.0` | 监听地址 |
| `AUTH_PORT` | `8001` | 监听端口 |
| `SERVICE_TOKEN` | `lx-internal-service-token` | 服务间通信密钥（桌面应用和认证服务必须一致） |

## 桌面应用连接

在桌面应用的 `data/auth_service_url.txt` 中写入认证服务地址：

```
http://your-server-ip:8001
```

或通过环境变量 `AUTH_SERVICE_URL=http://your-server-ip:8001` 设置。

### 服务间通信密钥

桌面应用通过 `SERVICE_TOKEN` 环境变量与认证服务进行内部通信（用户列表拉取、用户状态校验）。
两边必须配置相同的密钥值，否则桌面应用无法获取用户信息。

设置方式：
- **认证服务端**：`export SERVICE_TOKEN="your-random-secret-string"`
- **桌面应用端**：在系统环境变量中设置 `SERVICE_TOKEN`，或打包后在 `%APPDATA%/ExcelMerger/data/` 下创建 `service_token.txt` 写入密钥

## Nginx 反向代理（可选）

```nginx
location /auth/ {
    proxy_pass http://127.0.0.1:8001/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Service-Token $http_x_service_token;
}
```

此时桌面应用配置地址为 `https://your-domain.com/auth`。

## 管理后台

访问 `http://your-server-ip:8001/admin` 进入管理后台页面。

- 使用 admin 角色账号登录
- 可以在页面上增删用户、修改密码、启用/禁用用户
- admin session 有效期 2 小时

## API 接口

### 基础接口（供主应用调用）

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET  | `/health` | 健康检查 | 无 |
| POST | `/login` | 登录（用户名+密码） | 无 |
| GET  | `/users` | 用户列表 | 服务密钥 |
| POST | `/verify-user` | 校验用户状态 | 服务密钥 |

### 管理后台页面

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/admin` | 后台入口（自动重定向） |
| GET  | `/admin/login` | 管理员登录页 |
| GET  | `/admin/dashboard` | 管理面板页 |

### 管理后台 API（需 admin session）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/login` | 管理员登录 |
| POST | `/admin/logout` | 管理员退出 |
| GET  | `/admin/api/me` | 当前管理员信息 |
| GET  | `/admin/api/users` | 用户列表（含 enabled 状态） |
| POST | `/admin/api/users` | 新增用户 |
| PUT  | `/admin/api/users/{username}` | 编辑用户（姓名/角色/启用） |
| PUT  | `/admin/api/users/{username}/password` | 重置密码 |
| DELETE | `/admin/api/users/{username}` | 删除用户 |

### 安全约束

- 管理员不能删除自己
- 管理员不能禁用自己
- 管理员不能降级最后一个启用的管理员
- 至少保留一个管理员账号
- 禁用用户的旧 session 自动失效
- 禁用用户无法登录（返回 403）

## 应用配置

除了用户管理，管理后台还统一管理以下配置：

### 邮件配置

管理员在后台「邮件配置」标签页设置：
- 邮箱地址和授权码
- IMAP 服务器地址
- 主题关键词
- 筛选省份
- 轮询间隔

桌面应用启动时自动从服务器拉取配置，无需在本地设置。

### 功能开关

管理员可以在后台「功能开关」标签页控制桌面应用可用的功能：
- 文件合并功能 (file_merge)
- 邮件自动读取 (mail_reader)
- 规则查看 (rule_management)

关闭某功能后，桌面应用相应模块将自动隐藏。

### 规则管理

管理员在后台「规则管理」标签页管理 Excel 合并规则：
- 创建/编辑/删除规则
- 配置标准表头和源列名映射
- 配置值映射规则

桌面应用仅读取使用规则，不能修改。

### 配置文件

| 文件 | 说明 |
|------|------|
| `data/auth_config.json` | 用户配置（用户名/密码/角色/启用状态） |
| `data/app_config.json` | 应用配置（邮件/功能开关/规则） |

`app_config.json` 在首次访问管理后台时自动创建，无需手动编辑。
