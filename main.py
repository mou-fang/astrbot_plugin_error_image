import os
import re
import hashlib
from typing import Any, List

from PIL import Image as PILImage, ImageDraw, ImageFont

from astrbot.api import logger
from astrbot.api.all import *
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.message.components import Image, Plain
from astrbot.core.message.message_event_result import MessageChain, MessageEventResult
from astrbot.core.persona_error_reply import (
    PERSONA_CUSTOM_ERROR_MESSAGE_EXTRA_KEY,
    extract_persona_custom_error_message_from_event,
)

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASE_IMAGE = os.path.join(PLUGIN_DIR, "assets", "default_xibao.png")
CACHE_DIR = os.path.join(PLUGIN_DIR, "assets", "cache")

# 系统字体备选路径（优先使用支持中英双全的 CJK 粗体）
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# 常见报错特征码
ERROR_PATTERNS = [
    r"Error occurred while processing agent",
    r"Error occurred during AI execution",
    r"Error occurred while processing agent request",
    r"LLM 响应错误",
    r"^:\(\s*\n+在调用插件",
    r"Third party agent runner error",
    r"content_filter",
    r"内容安全过滤被拒绝",
]
ERROR_REGEX = re.compile("|".join(ERROR_PATTERNS), re.IGNORECASE)

_ORIGINAL_SEND = None
_GLOBAL_PLUGIN_INSTANCE = None


def _find_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue
    return ImageFont.load_default()


def _is_error_chain(chain: List[Any], persona_custom_msg: str | None = None) -> tuple[bool, str]:
    """判断消息链是否包含报错信息，返回 (是否报错, 报错文本摘要)"""
    if not chain:
        return False, ""

    text_content = ""
    for comp in chain:
        if isinstance(comp, Plain) and comp.text:
            text_content += comp.text

    if not text_content:
        return False, ""

    if persona_custom_msg and persona_custom_msg.strip() in text_content:
        return True, text_content

    if ERROR_REGEX.search(text_content):
        return True, text_content

    return False, ""


def _render_xibao(
    base_image_path: str,
    text: str,
    font_size: int = 56,
    text_color: str = "#C40000",
    stroke_color: str = "#FFFFFF",
    stroke_width: int = 4,
) -> str:
    """按参数生成喜报图片并缓存，返回生成的图片绝对路径"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    # 构造唯一哈希作为缓存 key
    cache_key_raw = f"{base_image_path}|{text}|{font_size}|{text_color}|{stroke_color}|{stroke_width}"
    cache_hash = hashlib.md5(cache_key_raw.encode("utf-8")).hexdigest()
    output_path = os.path.join(CACHE_DIR, f"xibao_{cache_hash}.png")

    if os.path.exists(output_path):
        return output_path

    try:
        base_img = PILImage.open(base_image_path).convert("RGBA")
    except Exception as e:
        logger.error(f"[ErrorImage] 打开底图失败 ({base_image_path}): {e}，回退默认底图")
        base_img = PILImage.open(DEFAULT_BASE_IMAGE).convert("RGBA")

    w_total, h_total = base_img.size
    draw = ImageDraw.Draw(base_img)
    font = _find_font(font_size)

    lines = text.strip().split("\n")
    line_metrics = []
    total_text_h = 0
    line_spacing = int(font_size * 0.35)

    for line in lines:
        if not line:
            empty_h = int(font_size * 0.8)
            total_text_h += empty_h
            line_metrics.append((line, 0, empty_h))
            continue
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_metrics.append((line, w, h))
        total_text_h += h + line_spacing

    total_text_h -= line_spacing

    # 喜报区域的纵向视觉中心通常位于高度的 48% 左右
    center_y = int(h_total * 0.485)
    start_y = center_y - total_text_h // 2

    current_y = start_y
    for line, w, h in line_metrics:
        if line:
            x = (w_total - w) // 2
            draw.text(
                (x, current_y),
                line,
                font=font,
                fill=text_color,
                stroke_width=stroke_width,
                stroke_fill=stroke_color,
            )
        current_y += h + line_spacing

    base_img.convert("RGB").save(output_path, "PNG")
    return output_path


def _get_active_image_path() -> str:
    """获取当前要发送的喜报图片路径"""
    global _GLOBAL_PLUGIN_INSTANCE
    config = _GLOBAL_PLUGIN_INSTANCE.config if _GLOBAL_PLUGIN_INSTANCE else {}

    # 用户是否指定了自定义底图
    custom_path = (config.get("custom_image_path") or "").strip()
    base_image = custom_path if (custom_path and os.path.exists(custom_path)) else DEFAULT_BASE_IMAGE

    # 是否开启文字绘制
    enable_text = config.get("enable_custom_text", True)
    if not enable_text:
        return base_image

    text_content = config.get(
        "text_content",
        "An unexpected error occurred\nwhile processing your request.\n\nPlease notify the administrator\nto investigate and fix it.",
    )

    font_size = int(config.get("font_size", 56))
    text_color = config.get("text_color", "#C40000")
    stroke_color = config.get("stroke_color", "#FFFFFF")
    stroke_width = int(config.get("stroke_width", 4))

    try:
        return _render_xibao(
            base_image_path=base_image,
            text=text_content,
            font_size=font_size,
            text_color=text_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
        )
    except Exception as e:
        logger.error(f"[ErrorImage] 动态渲染喜报图片异常: {e}", exc_info=True)
        return base_image


def _replace_chain_with_image(chain_obj: MessageChain, original_text: str):
    """将消息链清空并替换为喜报图片"""
    logger.error(
        f"[ErrorImage] ⚠️ 捕获到系统/插件报错，已将对外回复替换为喜报图片！\n"
        f"=================== 原始报错信息 ===================\n"
        f"{original_text.strip()}\n"
        f"==================================================="
    )
    chain_obj.chain.clear()
    img_path = _get_active_image_path()
    if os.path.exists(img_path):
        chain_obj.chain.append(Image.fromFileSystem(img_path))
    else:
        logger.warning(f"[ErrorImage] 喜报图片文件不存在: {img_path}，无法替换！")
        chain_obj.chain.append(Plain(original_text))


async def _patched_event_send(self: AstrMessageEvent, message: MessageChain, *args, **kwargs):
    """拦截直接通过 event.send(...) 发送的消息"""
    try:
        if message and hasattr(message, "chain"):
            persona_custom_msg = extract_persona_custom_error_message_from_event(self)
            is_err, err_text = _is_error_chain(message.chain, persona_custom_msg)
            if is_err:
                _replace_chain_with_image(message, err_text)
    except Exception as e:
        logger.error(f"[ErrorImage] 拦截 event.send 发生内部异常: {e}", exc_info=True)

    return await _ORIGINAL_SEND(self, message, *args, **kwargs)


@register(
    "astrbot_plugin_error_image",
    "mou-fang",
    "统一拦截所有报错并发送喜报图片，支持自定义文字与底图",
    "1.1.0",
)
class ErrorImagePlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context, config)
        self.config = config or {}
        global _GLOBAL_PLUGIN_INSTANCE
        _GLOBAL_PLUGIN_INSTANCE = self

        self._patch_event_send()
        
        # 预热渲染默认图片
        try:
            active_img = _get_active_image_path()
            logger.info(f"[ErrorImage] 插件加载完成！当前生效报错喜报图: {active_img}")
        except Exception as e:
            logger.warning(f"[ErrorImage] 预热渲染喜报图异常: {e}")

    def _patch_event_send(self):
        global _ORIGINAL_SEND
        if _ORIGINAL_SEND is None:
            _ORIGINAL_SEND = AstrMessageEvent.send
            AstrMessageEvent.send = _patched_event_send
            logger.info("[ErrorImage] 已挂载 AstrMessageEvent.send 报错拦截器")

    def _unpatch_event_send(self):
        global _ORIGINAL_SEND
        if _ORIGINAL_SEND is not None:
            AstrMessageEvent.send = _ORIGINAL_SEND
            _ORIGINAL_SEND = None
            logger.info("[ErrorImage] 已卸载 AstrMessageEvent.send 报错拦截器")

    async def terminate(self):
        self._unpatch_event_send()

    @filter.on_decorating_result(priority=100000)
    async def on_decorating_result(self, event: AstrMessageEvent):
        """在结果装饰阶段拦截即将发送的 LLM/插件结果"""
        result = event.get_result()
        if not result or not result.chain:
            return

        persona_custom_msg = extract_persona_custom_error_message_from_event(event)
        is_err, err_text = _is_error_chain(result.chain, persona_custom_msg)
        if is_err:
            _replace_chain_with_image(result, err_text)
