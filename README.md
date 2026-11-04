# astrbot_plugin_error_image (报错喜报转换器)

<p align="center">
  <img src="https://raw.githubusercontent.com/mou-fang/astrbot_plugin_error_image/main/assets/cover.png" alt="Cover" width="600" />
</p>

优雅拦截 AstrBot 所有模型与插件报错，并转换为喜报图片发送，同时在后台日志中完整保留错误堆栈。支持可视化自由配置文字、底图与排版。

## ✨ 特性

- 🛡️ **全面拦截**：拦截 `AstrMessageEvent.send` 及回复装饰阶段的所有异常（LLM 超时、响应错误、插件崩溃、内容过滤等）。
- 🎨 **高度自由排版**：
  - 支持中英文多行文本，自动换行、对齐与居中。
  - 可视化调节字号（Slider）、字体主色、纯白描边粗细。
  - 支持关闭文字绘制直接发送纯底图。
- 🖼️ **支持自定义底图**：可使用插件自带的原生喜报底图，也可指定自定义图片绝对路径。
- ⚡ **智能缓存**：内置动态 MD5 渲染缓存，同套配置毫秒级复用，零性能负担。
- 🔍 **后台完整溯源**：对外发送幽默喜报的同时，后台 `logger.error` 完整记录并高亮原始错误堆栈，不影响运维排查。

## ⚙️ 配置项说明 (WebUI)

在 AstrBot 管理面板的「插件配置」中可以直接可视化调节：

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `enable_custom_text` | bool | `true` | 是否在喜报底图上绘制文字（关闭则直接发原图） |
| `text_content` | text | *(默认英文喜报)* | 绘制的文字内容，支持换行 |
| `custom_image_path`| string | `""` | 自定义底图文件路径（留空使用默认喜报图） |
| `font_size` | int | `56` | 文字大小（24 ~ 120 像素滑动条） |
| `text_color` | string | `#C40000` | 文字颜色（默认喜报红） |
| `stroke_color` | string | `#FFFFFF` | 描边颜色（默认白色） |
| `stroke_width` | int | `4` | 描边粗细（0 ~ 12 像素滑动条） |

## 📦 安装方法

在 AstrBot 插件市场安装，或使用 Git 克隆至 `data/plugins/` 目录：

```bash
cd data/plugins
git clone https://github.com/mou-fang/astrbot_plugin_error_image.git
```
