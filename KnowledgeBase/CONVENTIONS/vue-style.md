# 🟢 Vue 前端编码风格 (web/)

## 技术栈

- **框架**: Vue 3 (Composition API 或 Options API)
- **UI**: Element Plus + @element-plus/icons-vue
- **路由**: Vue Router 4 (createWebHistory)
- **状态**: Pinia
- **HTTP**: axios
- **构建**: Vite 8
- **Markdown**: marked + dompurify

## 组件命名

| 类型 | 风格 | 示例 |
|------|------|------|
| 页面组件 | PascalCase.vue | `ContentStudio.vue`, `SuperAgent.vue` |
| Shell 组件 | PascalCase + Shell | `ContentShell.vue` |
| 公共组件 | PascalCase | `AppLayout.vue` |
| 路由 path | kebab-case | `/content/video-editor` |

## 路由规范

- 所有业务页面无需 `meta.requiresAuth`（已移除登录页，自动认证）
- 管理员页面保留 `meta.requiresAdmin: true`（可选）
- 每个版块使用 Shell 组件作为父路由
- 懒加载: `() => import('./pages/Xxx.vue')`
- 向后兼容重定向: 旧路径 → 新路径 redirect

## API 调用

- 统一使用 `web/src/api.js` 导出的 axios 实例
- JWT 自动附加: 请求拦截器从 `localStorage.getItem('token')` 读取
- 响应错误处理: 401 → 自动重新获取 token（不跳转登录页）

## 样式

- 全局样式: `style.css` + `tech-theme.css`
- 组件内样式: `<style scoped>`
- 主题: 科技风 (tech-theme)

## 目录结构

```
web/src/
├── pages/        # 页面组件 (一页一文件)
├── components/   # 公共组件
├── stores/       # Pinia store
├── assets/       # 静态资源
├── api.js        # axios 实例
├── router.js     # 路由定义
└── main.js       # 应用入口
```
