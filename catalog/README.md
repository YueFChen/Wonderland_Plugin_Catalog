# Wonderland Assistant 插件目录

Core 从本仓库的 GitHub Pages 读取 `catalog/v2/index.json`。目录记录插件身份、公开仓库及 Ed25519 公钥，不登记插件版本。插件作者在每个 GitHub Release 中发布版本化 `.wplug` 安装包和 `<id>-update.json` 签名更新清单。

当前只维护 v2 协议，不保留旧版目录兼容；旧版 Core 将无法读取新目录。

## 登记插件

1. 在插件仓库生成 Ed25519 密钥。将 32 字节私钥种子以 Base64 保存为插件仓库的 Actions secret `PLUGIN_UPDATE_SIGNING_KEY`；不得提交或写入日志。
2. 插件 Release 工作流根据实际 `.wplug` 计算 SHA-256 和大小，将版本、下载地址、兼容范围、capabilities、网络范围及服务声明写入更新清单，并对清单签名。
3. 在 `catalog/v2/plugins/{id}.json` 提交插件身份记录，包含稳定的 `releases/latest/download/{id}-update.json` 地址和对应 Ed25519 公钥。目录 PR 校验该清单签名、Release 包、内部 checksums 与 manifest 元数据。
4. 至少一位维护者审核并合并登记 PR。GitHub Actions 生成 `catalog/v2/index.json` 并部署到 Pages；生成的索引不直接编辑或提交。

插件发布后续版本时，只需由插件仓库发布新的签名清单和安装包，无需更新目录。每条目录记录仍由人工 PR 审核；插件版本和能力声明由该插件的签名密钥负责。用户本地安装的插件不会自动替换，Core 仍会检查兼容性并在安装或更新前展示能力请求。

## 签名与信任边界

Core 使用目录登记的 Ed25519 公钥验证插件更新清单，再用签名清单里的 SHA-256 与大小校验下载包，并核对包内 manifest。HTTPS 和 SHA-256 单独不足以证明发布者身份，因为被控制的仓库可以同时替换清单与安装包；签名私钥应只保存在插件仓库的 Actions secret 中。密钥轮换需要先经目录 PR 更新公钥，再用新密钥重新签发当前更新清单；两步之间插件会暂时显示为版本信息不可用，不会接受未验签的版本。

维护者应启用 `main` 分支保护，要求目录 PR 审核，并限制 Pages 部署工作流的写权限。

## 首次启用 Pages

在仓库 Settings → Pages → Build and deployment 中把 Source 设为 **GitHub Actions**。发布工作流会将 `catalog/v2/` 部署到项目 Pages 站点。首次创建仓库时还要按根目录 `REPOSITORY_SETUP.md` 启用 `main` 分支的必需 PR 审核和 `validate` 检查。
