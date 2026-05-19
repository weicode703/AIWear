# AIWear 前端说明

这是 AIWear 的 Vue 前端项目，目录名为 `fronted`。

## 1. 技术栈

- Vue 3
- Vite
- Vue Router
- Pinia
- Axios
- Element Plus

## 2. 启动方式

```powershell
cd fronted
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173
```

## 3. 页面功能

| 页面 | 说明 |
|---|---|
| 登录页 | 邮箱验证码登录 |
| 图片编辑 | 上传本地图片，输入指令生成编辑结果 |
| 图片合并 | 上传两张本地图片，输入指令生成合并结果 |
| 我的图片 | 查看上传图片，支持文搜图和图搜图 |
| 历史记录 | 查看编辑和合并历史 |
| 穿搭问答 | RAG 穿搭聊天，支持会话列表和删除会话 |

## 4. 主要目录

```text
src/
  main.js                 应用入口
  App.vue                 根组件
  router/index.js         路由和登录守卫
  store/auth.js           登录状态
  services/http.js        Axios 实例和拦截器
  services/api.js         后端接口封装
  components/             公共组件
  views/                  页面组件
```

## 5. 接口代理

前端请求以 `/api` 开头，开发环境通过 Vite 代理到 FastAPI 后端。

后端默认地址：

```text
http://127.0.0.1:8000
```

如果代理地址不对，检查：

```text
fronted/vite.config.js
```

## 6. 学习顺序

1. `src/main.js`
2. `src/router/index.js`
3. `src/store/auth.js`
4. `src/services/http.js`
5. `src/services/api.js`
6. `src/views/LoginView.vue`
7. `src/views/EditView.vue`
8. `src/views/MergeView.vue`
9. `src/views/ImagesView.vue`
10. `src/views/RagView.vue`
