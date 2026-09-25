# Wonderland Assistant 插件目录

Core 从本仓库的 GitHub Pages 读取 `catalog/v1/index.json`。插件包由作者保存在各自公开 GitHub 仓库的 Release 中；本目录只收录经过 PR 审核的固定版本及下载校验信息。

## 提交插件

1. 按 `template_plugin` 规范生成 release `.wplug`，文件名应为 `{id}-{version}-windows-{architecture}.wplug`。
2. 在作者的公开 GitHub 仓库发布版本化 Release，上传该文件。不要替换已收录版本的 Release 附件。
3. 在 `catalog/v1/plugins/{id}.json` 新增一个插件记录文件，并提交 PR。JSON 内容是一条完整插件记录，文件名必须与记录中的 `id` 一致；字段格式参见 `v1/index.schema.json` 中 `plugins.items` 的定义。
4. 自动检查会扫描该目录下所有直接子级 `.json` 文件，下载附件并验证 URL、大小、SHA-256、ZIP 路径、插件 manifest 与目录元数据。至少一位维护者审核通过后合并。
5. 合并到 `main` 后，GitHub Actions 会按插件 ID 排序生成 `catalog/v1/index.json` 并部署到 Pages。这个总索引是构建产物，不直接编辑或提交。

登记新插件时新增一个记录文件；发布已登记插件的新版本时，更新该插件自己的记录文件。`maxCoreVersionExclusive` 和 `protocol.maxVersionExclusive` 是不包含上界。每个插件记录对应一个当前推荐版本；用户本地安装的旧版本不会因目录更新而被自动替换。

## 信任边界

Core 只接受仓库中审核过的目录记录、HTTPS GitHub Release 下载和匹配目录的 SHA-256，并继续执行 `.wplug` 内部校验、Core 兼容性检查及用户能力确认。SHA-256 校验的是包与审核记录是否一致，不等同于插件作者的数字签名。维护者应启用 `main` 分支保护，要求 PR 审核，并限制 Pages 部署工作流的写权限。

## 首次启用 Pages

在仓库 Settings → Pages → Build and deployment 中把 Source 设为 **GitHub Actions**。发布工作流会将 `catalog/v1/` 部署到项目 Pages 站点。首次创建仓库时还要按根目录 `REPOSITORY_SETUP.md` 启用 `main` 分支的必需 PR 审核和 `validate` 检查。
