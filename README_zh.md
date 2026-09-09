# BezierEditing 插件（版本 1.4.0）

BezierEditing 是一个用于通过贝塞尔曲线编辑要素的 [QGIS 插件](https://plugins.qgis.org/plugins/BezierEditing/)。

![BezierEditing 插件界面](https://github.com/tmizu23/BezierEditing/wiki/images/BezierEditing.png)

## 安装

可以直接在 QGIS 中安装此插件：

**插件 → 管理并安装插件… → 搜索“Bezier Editing” → 安装插件**

## 文档

- [英文文档](https://github.com/tmizu23/BezierEditing/wiki/Document-(English))
- [日文文档](https://github.com/tmizu23/BezierEditing/wiki/%E3%83%89%E3%82%AD%E3%83%A5%E3%83%A1%E3%83%B3%E3%83%88%EF%BC%88Japanese%EF%BC%89)

## 依赖的 Python 库和资源

- [fitCurves](https://github.com/volkerp/fitCurves)：用于将一条或多条三次贝塞尔曲线拟合到折线。
- [cubic_bezier_curve.ipynb](https://github.com/tmizu23/cubic_bezier_curve/blob/master/cubic_bezier_curve.ipynb)

## 更新日志

### 版本 1.4.0

- 增加对 QGIS 4（Qt 6／PyQt 6）的兼容性。
- 保持对 QGIS 3.20 及更高版本的向后兼容性。

### 版本 1.3.10

- 修复在 Linux 环境中安装失败的问题。

### 版本 1.3.9

- 为手绘工具新增流式绘制模式（通过“单击—移动—单击”绘制，无需按住鼠标拖动）。
- 新增手绘工具设置的上下文菜单（Ctrl + 右键单击）。
- 修复 Linux 上的 `reuseLastValues` 错误。

### 版本 1.3.8

- 修复使用分割工具后属性消失的问题。

### 版本 1.3.7

- 修复工具按钮无法切换的问题。
- 修复 `disable_enter_attribute_values_dialog` 设置不生效的问题。
- 修复 `UseLastValue` 设置不生效的问题。
- 修复表单默认值未应用的问题。

### 版本 1.3.6

- 增加由 @BathoryPeter 提供的匈牙利语翻译。
- 为“贝塞尔编辑”按钮增加详细的工具提示。
- 改进提示消息的措辞。
- 修复 macOS 上无法合并曲线的问题。

### 版本 1.3.5

- 支持重复使用上次输入的值。
- 修复 `fid` 自动填充问题。

### 版本 1.3.4

- 修复 `initGui()` 错误。

### 版本 1.3.3

- 支持移动两侧控制柄（按住 Alt 拖动）。
- 支持添加锚点时固定第一个控制柄（按住 Alt 单击并拖动）。
- 支持将第二个控制柄固定到锚点（按住 Shift 单击并拖动）。
- 支持设置插值点数量。
- 默认显示控制柄。

## 参与贡献

### 翻译

1. 打开 `bezierediting.pro`，在 `TRANSLATIONS` 部分添加 `i18n/bezierediting_{lang}.ts`。`{lang}` 必须是双字母语言代码。
2. 运行 `pylupdate5 bezierediting.pro` 生成翻译文件。在 Debian 上可以通过 `apt install pyqt5-dev-tools` 安装 `pylupdate`。
3. 使用 Qt Linguist 或文本编辑器打开 `i18n` 目录中新生成的 `.ts` 文件并完成翻译。
4. 翻译完成后运行 `lrelease bezierediting.pro` 生成 `.qm` 文件。
5. 可选：将 `.qm` 文件复制到 QGIS 配置目录中的插件文件夹以测试翻译。在 Linux 上，该目录通常为 `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/BezierEditing/i18n`。复制后重新启动 QGIS。
6. 在 GitHub 上创建拉取请求，或将 `.ts` 文件发送给插件维护者。

简体中文翻译文件使用 `bezierediting_zh.ts` 和 `bezierediting_zh.qm`。将 QGIS 用户界面语言设置为简体中文并重启 QGIS 后，插件会自动加载中文翻译。

## 许可证

BezierEditing 插件依据 GNU 通用公共许可证第 2 版（GPL v2）发布。

_版权所有 © 2019 Takayuki Mizutani_
