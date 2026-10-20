# 导入 Streamlit，用原生组件搭建翻译页面。
import streamlit as st
# 导入路径工具，读取与前端放在同一文件夹的翻书动画。
from pathlib import Path
# 导入兼容接口客户端的错误类型，用于提供具体的调用提示。
from openai import APIConnectionError, APIStatusError, APITimeoutError
# 导入已经完成的 LangChain 翻译后端。
from utils import translate_text, TranslationResponseError

# 设置浏览器标签、宽屏布局，并默认展开侧边栏。
st.set_page_config(page_title="简体中文翻译器", page_icon="🌐", layout="wide", initial_sidebar_state="expanded")

# 为当前用户保存翻译结果，避免修改配置后译文消失。
if "translation_result" not in st.session_state:
    # 初始化空结果，不保存或缓存用户的 API 密钥。
    st.session_state.translation_result = {"translation": "", "terms": [], "annotations": [], "source": ""}

# 将 API 配置放在侧边栏，沿用原来的布局。
with st.sidebar:
    # 显示侧边栏标题。
    st.subheader("连接你的模型", icon=":material/settings:")
    # 告诉用户支持的模型平台。
    st.caption("支持 Kimi、千问、DeepSeek、OpenAI 及兼容接口。")
    # 接收用户自己的 API 密钥，并隐藏输入内容。
    api_key = st.text_input("API 密钥", type="password", placeholder="请输入对应平台的 API 密钥", key="api_key")
    # 接收用户提供的 API 基础地址，不使用默认地址。
    base_url = st.text_input("API URL", placeholder="请输入平台提供的 API 基础地址", key="base_url", help="填写 OpenAI 兼容接口的基础地址，不包含 /chat/completions 后缀。")
    # 接收对应平台实际支持的模型名称。
    model_name = st.text_input("模型名称", placeholder="请输入平台支持的模型 ID", key="model_name")
    # 说明三个输入框应来自同一个平台或网关。
    st.caption("密钥、地址和模型名称，请使用同一平台或网关提供的信息。")

# 显示页面主标题。
st.title("简体中文翻译器", anchor=False)
# 明确告诉用户输入语言和输出语言的规则。
st.markdown("输入任意语言，统一翻译为 **简体中文**。")
# 用简短说明介绍专业名词注解功能。
st.caption("粘贴文字，读懂原意；专业名词也有中文百科参考。")

# 在两个文本框上方预留小型等待提示，空闲时不显示。
loading_placeholder = st.empty()

# 创建等宽的左右两列，实现原文与译文对照布局。
left, right = st.columns(2, gap="medium")

# 在左侧创建原文输入区域。
with left:
    # 使用原生边框容器，让输入区成为一张独立卡片。
    with st.container(border=True):
        # 显示输入区域标题。
        st.markdown("**原文**")
        # 告知用户不必选择输入语言。
        st.caption("自动识别语言 → 中文（简体）")
        # 将输入和按钮放进表单，点击翻译时才提交文字。
        with st.form("translation_form", border=False):
            # 使用紧凑的多行输入框，长文本仍可在框内滚动。
            text = st.text_area("待翻译文本", height=240, placeholder="在这里输入或粘贴文字……\n\n支持英语、日语、韩语等任意语言，也可以输入多种语言混合的内容。", label_visibility="collapsed", key="source_text")
            # 提醒用户可以直接粘贴文章段落。
            st.caption("支持多行输入，无需手动选择原文语言。")
            # 创建占满卡片宽度的主要操作按钮。
            submit = st.form_submit_button("翻译成简体中文", type="primary", icon=":material/translate:", width="stretch")

# 在右侧创建模型输出区域。
with right:
    # 使用与输入区一致的边框容器，使两列视觉统一。
    with st.container(border=True):
        # 显示输出区域标题。
        st.markdown("**译文**")
        # 显示固定目标语言和当前完成状态。
        st.caption("中文（简体） · 已完成" if st.session_state.translation_result["translation"] else "中文（简体） · 等待翻译")
        # 使用等高只读文本框显示纯文本译文，方便与左侧逐段对照。
        st.text_area("简体中文译文", value=st.session_state.translation_result["translation"], height=240, placeholder="翻译结果将显示在这里。", disabled=True, label_visibility="collapsed")
        # 提供简短的结果使用提示。
        st.caption("可选中复制译文，也可下载为文本文件。")
        # 提供下载入口，尚无译文时禁用，下载时不重复调用模型。
        st.download_button("下载译文", data=st.session_state.translation_result["translation"].encode("utf-8"), file_name="简体中文译文.txt", mime="text/plain; charset=utf-8", icon=":material/download:", width="stretch", disabled=not st.session_state.translation_result["translation"], on_click="ignore")

# 在两栏下方保留维基百科结果的折叠展示方式。
with st.expander("维基百科搜索结果 👀", expanded=False):
    # 有专业名词注解时，逐项显示百科查询结果。
    if st.session_state.translation_result["annotations"]:
        # 遍历后端返回的专业名词及其注解。
        for item in st.session_state.translation_result["annotations"]:
            # 显示当前专业名词。
            st.markdown(f"**{item['term']}**")
            # 显示原文片段和实际百科标题，便于逐项核对术语与释义。
            if item.get("original") and item.get("title"):
                # 保留百科实际名称，不将相关但不同的概念冒充为同一术语。
                st.caption(f"原文术语：{item['original']} · 百科词条：{item['title']}")
            # 查询失败时使用警告框，避免把错误提示当成百科定义。
            if item.get("status") in ("error", "not_found"):
                # 提示具体的术语或百科问题，同时保留右侧译文。
                st.warning(item["explanation"])
            # 查询成功时沿用原页面的信息框展示百科内容。
            else:
                # 显示当前专业名词的参考注解。
                st.info(item["explanation"])
            # 为每个术语提供中文百科查询链接，失败时也能手动查找。
            if item.get("search_url"):
                # 保持原来的折叠布局，只在注解后补充一个小链接。
                st.markdown(f"[在中文维基百科中查看]({item['search_url']})")
        # 说明搜索到的词条只是帮助理解原文的参考资料。
        st.caption("百科搜索结果仅供参考，请结合原文语境核对。")
    # 已翻译但没有提取出专业名词时，显示明确说明。
    elif st.session_state.translation_result["translation"]:
        # 避免用户误以为注解区域未加载。
        st.caption("本次没有可展示的百科术语注解；未匹配到对应词条或暂时未能核验的候选已过滤。")
    # 未翻译时显示折叠区域的用途。
    else:
        # 说明翻译完成后会自动查询专业名词。
        st.caption("翻译完成后，这里会显示专业名词的中文维基百科注解。")

# 仅在用户点击翻译按钮后检查输入并调用后端。
if submit:
    # 检查用户是否提供 API 密钥。
    if not api_key.strip():
        # 用原页面相同的信息框方式提示缺少配置。
        st.info("请在侧边栏输入 API 密钥。")
        # 停止本次执行，避免发送无效请求。
        st.stop()
    # 检查用户是否提供 API 基础地址。
    if not base_url.strip():
        # 提示用户填写自己的服务商或网关地址。
        st.info("请在侧边栏输入 API URL。")
        # 不使用默认地址，也不继续调用模型。
        st.stop()
    # 检查是否填写了模型名称。
    if not model_name.strip():
        # 提示用户补充目标模型。
        st.info("请在侧边栏输入模型名称。")
        # 停止执行，等待配置完整。
        st.stop()
    # 检查用户是否输入待翻译文字。
    if not text.strip():
        # 提醒用户在左侧输入内容。
        st.info("请在左侧输入需要翻译的文字。")
        # 阻止空文本请求。
        st.stop()
    # 单独加载动画，避免缺少动画文件时阻断翻译。
    try:
        # 读取本地动画文件，并在等待区域显示翻书动画与指定文字。
        loading_placeholder.html(Path(__file__).with_name("loading.html").read_text(encoding="utf-8"))
    # 动画文件缺失或渲染失败时降级为文字提示。
    except Exception:
        # 告知用户需要把动画文件放到当前前端文件旁边。
        st.warning("翻书动画未能加载，请将 loading.html 放在前端文件同一文件夹；翻译仍会继续。")
        # 没有动画时仍显示用户指定的等待文字。
        loading_placeholder.caption("AI正在努力翻译ing……")
    # 捕获模型调用错误，按原因提供提示而不显示完整请求或密钥。
    try:
        # 将用户提供的文字、密钥、地址和模型名称交给简单版后端，浏览器会在等待期间自动播放动画。
        translation, terms, annotations = translate_text(text, api_key.strip(), base_url.strip().rstrip("/"), model_name.strip())
        # 将结果保存到当前会话，供右侧译文和下方百科区域展示。
        st.session_state.translation_result = {"translation": translation, "terms": terms, "annotations": annotations, "source": text}
        # 刷新页面读取新结果；刷新不会再次触发翻译按钮。
        st.rerun()
    # 单独展示后端已经处理过的翻译响应错误，指出失败的具体步骤。
    except TranslationResponseError as exc:
        # 展示安全的定位提示，不输出原始接口响应或密钥。
        st.error(f"{exc} 右侧如有译文，是上一次的结果。")
    # 单独处理模型请求超时。
    except APITimeoutError:
        # 提示用户当前是模型调用超时，保留上一次结果。
        st.error("模型请求超时，请稍后重试，或减少输入文字。右侧如有译文，是上一次的结果。")
    # 单独处理模型地址无法连接的问题。
    except APIConnectionError:
        # 提醒用户检查模型 API 地址、代理和网络。
        st.error("无法连接模型接口，请检查 API URL、网络或代理设置。右侧如有译文，是上一次的结果。")
    # 按服务商返回的 HTTP 状态码区分常见错误。
    except APIStatusError as exc:
        # 根据状态码给出可操作的提示，不输出包含凭据的原始响应。
        reasons = {400: "请求参数或模型不兼容，请核对模型名称和接口格式。", 401: "API 密钥无效，请使用当前平台或网关颁发的密钥。", 403: "没有访问权限，请检查密钥权限及模型授权。", 404: "接口地址或模型不存在，请核对 API URL 和模型名称。", 429: "调用频率受限或账户额度不足，请检查账户状态后重试。"}
        # 显示状态码和对应原因，便于进一步定位。
        st.error(f"模型调用失败（HTTP {exc.status_code}）：{reasons.get(exc.status_code, '服务商暂时异常，请稍后重试。')}右侧如有译文，是上一次的结果。")
    # 处理其他未预料的问题。
    except Exception as exc:
        # 显示错误类别帮助定位，同时避免暴露密钥或完整请求内容。
        st.error(f"处理失败（{type(exc).__name__}）。请检查模型配置及依赖；右侧如有译文，是上一次的结果。")
    # 无论翻译成功、失败或触发页面刷新，都清除等待动画。
    finally:
        # 翻译结束后移除翻书动画和等待文字。
        loading_placeholder.empty()

# 在对应环境中，从这三个文件所在文件夹启动页面。
# streamlit run main.py
