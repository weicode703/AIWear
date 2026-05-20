import base64
import json
import os
import tempfile
import time
import traceback
import uuid
from io import BytesIO

import uvicorn
from PIL import Image
from dashscope import MultiModalConversation
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

try:
    from deepagents import create_deep_agent
except ImportError:
    create_deep_agent = None

from app.api.routes.file import router as file_router
from app.api.routes.rag import router as rag_router
from app.api.routes.record import router as record_router
from app.api.routes.user import router as user_router

from app.api.routes.recommend import router as recommend_router
from app.core.config import settings
from app.core.database import Base, engine

# 获取配置信息。
# override=True 表示优先使用 .env 中的新值，覆盖系统里可能残留的旧环境变量。
load_dotenv(override=True)
API_KEY=os.getenv("DASHSCOPE_API_KEY")
# 创建 FastAPI 应用实例。
# title 和 version 会显示在 Swagger 文档页面里。
app=FastAPI(title="AI wear",version="1.0.0")


@app.middleware("http")
async def log_request_info(request: Request, call_next):
    """打印每次接口访问日志，方便本地联调时定位问题。"""
    start_time = time.perf_counter()
    method = request.method
    path = request.url.path
    query = request.url.query
    full_path = f"{path}?{query}" if query else path

    print(f"[接口请求] {method} {full_path}")
    try:
        response = await call_next(request)
    except Exception as exc:
        cost_ms = (time.perf_counter() - start_time) * 1000
        print(f"[接口异常] {method} {full_path} | 耗时={cost_ms:.2f}ms")
        print(f"[异常类型] {type(exc).__name__}")
        print(f"[异常信息] {exc}")
        traceback.print_exc()
        raise

    cost_ms = (time.perf_counter() - start_time) * 1000
    print(f"[接口响应] {method} {full_path} | 状态码={response.status_code} | 耗时={cost_ms:.2f}ms")
    return response

# 将图片bytes转换成base_uri
def process_image(image_data : bytes) -> str:
    img = Image.open(BytesIO(image_data))      # 从字节数据解析为PIL图片对象
    image_format = (img.format).lower()         # 获取图片格式(jpg/png等)并转小写
    image_base64 = base64.b64encode(image_data).decode("utf-8")  # bytes→Base64字符串
    data_uri = f"data:image/{image_format};base64,{image_base64}"      # 构建标准 Data URI
    return data_uri
# 调用大模型生成图片文字描述信息
def describe_image(image_data : bytes) -> str:
    try:
        data_uri=process_image(image_data)
        model=ChatTongyi(model_name="qwen-vl-plus",
                         temperature=0.0,
                         dashscope_api_key=API_KEY
                         )
        result=model.invoke([HumanMessage(content=[
                            {"image": data_uri},
                            {"text": "用一句话简要地概括这张图片的内容，并给出3到5个关键词（使用逗号分隔开），不要过多地解释"}
                            ])
                        ]
                    )
        return result.content[0]['text']
    except Exception as e :
        print(f"生成图片的文字描述信息出现异常:{e}")
        return ""

# 对图片的描述信息做最终的判定
def validate_image(image_desc:str)->bool:
    try:
        prompt=ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个图片审核助手，当前的业务只允许两种图片："
                    "1) 衣服/服装/穿搭相关;"
                    "2) 人物人像(人脸照、半身照、全身照).\n"
                    "需要你来判断当前图片的内容是否是以上两类图片，如果是输出是，如果否输出否。"
                    "请严格只输出是或者否，不要别的内容"
                ),
                (
                    "human",f"图片文字描述{image_desc}"
                )
            ]
        )
        model=ChatTongyi(
            model_name="qwen-plus",
            temperature=0.7,
            dashscope_api_key=API_KEY
        )
        result=model.invoke(prompt.format_messages())
        text=result.content
        return text.startswith("是")
    except Exception as e:
        print(f"做图片内容判定的时候出现异常:{e}")
        return False

 
# 定义审核图片接口：POST /api/validate-image
@app.post("/api/validate-image")
async def validate_image_api(file:UploadFile=File(...))->dict:
    """审核图片接口：读取图片 -> 生成描述 -> 二次审核 -> 返回是否通过。"""
    try:
        image_data=file.file.read()
        desc=describe_image(image_data)    # 读取图片的二进制数据
        allow=validate_image(desc)          #调用AI模型，将图片转换为文字描述
        return {"code":200,"allow":allow}
    except Exception as e:
        print(f"执行审核图片操作捕获异常{e}")
        raise HTTPException(status_code=500,detail={"code":500,"allow":False})





# 全局的agent智能体
deep_agent = None
model = ChatTongyi(
    model_name="qwen-plus",      # 使用通义千问plus模型
    temperature=0.1,              # 低温度=输出更稳定
    dashscope_api_key=API_KEY
)


def _extract_image_url(response: object) -> str:
    """从模型返回结果中安全提取图片 URL。"""
    if not isinstance(response, dict):
        return ""

    output = response.get("output")
    if not isinstance(output, dict):
        return ""

    choices = output.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""

    message = first_choice.get("message")
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    if not isinstance(content, list) or not content:
        return ""

    first_content = content[0]
    if not isinstance(first_content, dict):
        return ""

    image_url = first_content.get("image")
    return image_url if isinstance(image_url, str) else ""


def _save_upload_file(upload_file: UploadFile, tmp_dir: str, suffix: str = "") -> str:
    """把上传文件保存到临时目录，并尽量保留原始扩展名。"""
    original_suffix = os.path.splitext(upload_file.filename or "")[1].lower()
    final_suffix = original_suffix or suffix or ".png"
    tmp_path = os.path.join(tmp_dir, f"aiwear_{uuid.uuid4().hex}{final_suffix}")

    with open(tmp_path, "wb") as f:
        f.write(upload_file.file.read())

    return tmp_path


def _has_real_file(upload_file: UploadFile | None) -> bool:
    """判断当前上传字段里是否真的有文件。"""
    return upload_file is not None and bool(upload_file.filename)


#编辑单张图片工具
@tool
def edit_image_tool(image_path:str,instruction: str) -> str:
    """编辑单张图片
    输入本地图片地址路径与编辑指令，调用Dashscope的图像编辑模型生成新的URL
    返回JSON字符串: {"success": true, "url":"..."} 或 {"success": false, "error":"..."}
    """
    try:
        #读取本地图片
        with open(image_path,"rb")as f:
            image_data=f.read()
        #转换格式
        image_data_uri=process_image(image_data)
        messages=[
            {
                "role":"user",
                "content":[
                    {"image":image_data_uri},
                    {"text":instruction}
                ]
            }
        ]
        # 调用阿里云图片编辑模型
        params={
            "model": "qwen-image-2.0",
            "messages": messages,
            "api_key": API_KEY,
        }
        response = MultiModalConversation.call(**params)
        print(f"编辑模型原始响应: {response}")
        # 提取生成的图片URL
        url = _extract_image_url(response)
        if not url:
            return json.dumps(
                {"success": False, "error": f"模型未返回图片地址，原始响应: {response}"},
                ensure_ascii=False,
            )
        return json.dumps({"success":True,"url":url},ensure_ascii=False)
    except Exception as e:
        print(f"调用编辑模型报错:{e}")
        return json.dumps({"success": False, "error": f"{e}"}, ensure_ascii=False)

#合并两张图片工具
@tool
def merge_image_tool(image_path1:str,image_path2:str,instruction:str)->str:
    """合并两张图片
    输入两张本地图片地址路径与合并指令，调用Dashscope的图像编辑模型生成新的URL
    """
    try:
        # 步骤1：读取两张图片
        with open(image_path1,"rb")as f:
            image_data1=f.read()
        with open(image_path2,"rb")as f:
            image_data2=f.read()
        # 步骤2：都转换为 Data URI
        image_data_uri1 = process_image(image_data1)
        image_data_uri2 = process_image(image_data2)
        # 步骤3：构建多图消息（关键区别：两张图同在一个content里）
        messages = [
            {
                "role": "user",
                "content": [
                    {"image": image_data_uri1},  # 第一张图
                    {"image": image_data_uri2},  # 第二张图
                    {"text": instruction},  # 合并指令
                ],
            }
        ]

        # 步骤4：调用模型
        params = {
            "model": "qwen-image-edit-plus",
            "messages": messages,
            "api_key": API_KEY,
        }
        response = MultiModalConversation.call(**params)
        print(f"合并模型原始响应: {response}")

        # 步骤5：提取结果URL
        url = _extract_image_url(response)
        if not url:
            return json.dumps(
                {"success": False, "error": f"模型未返回图片地址，原始响应: {response}"},
                ensure_ascii=False,
            )
        return json.dumps({"success": True, "url": url}, ensure_ascii=False)

    except Exception as e:
        print(f"调用合并模型报错:{e}")
        return json.dumps({"success": False, "error": f"{e}"}, ensure_ascii=False)
# 声明工具列表
skills_tools = [edit_image_tool, merge_image_tool]
# 创建agent
try:
    if create_deep_agent is not None:
        deep_agent = create_deep_agent(
            model=model,
            tools=skills_tools,
            skills=["/skills/"],
            system_prompt="""
            最终的输出格式JSON: {"success":true, "url":"字符串类型"}
            或者 {"success":false, "error":"字符串类型"}
            """
        )
        print("Agent 已经启用")
    else:
        print("Agent 未启用：缺少 deepagents 依赖")
except Exception as e:
    print("Agent 未启用")
    deep_agent = None

#调用agent
def invoke_agent(param: str) -> dict:
    try:
        state = deep_agent.invoke({"messages": [HumanMessage(content=param)]})
        content = state["messages"][-1].content
        return json.loads(content)
    except Exception as e:
        print(f"执行agent函数出现异常{e}")
        return {"success": False, "error": f"执行agent函数失败{e}"}

# 操作图片的函数
async def skill_image(
    instruction: str,
    file: UploadFile = None,
    file1: UploadFile = None,
    file2: UploadFile = None
) -> dict:
    try:
        if not instruction:
            return {"success": False, "error": "instruction 不能为空"}

        # 获取临时目录
        tmp_dir = tempfile.gettempdir()
        tmp_paths = []  # 记录临时文件，用于后续清理

        # 情况1：双图合并
        if _has_real_file(file1) and _has_real_file(file2):
            p1 = _save_upload_file(file1, tmp_dir, "_1.png")
            p2 = _save_upload_file(file2, tmp_dir, "_2.png")
            tmp_paths.extend([p1, p2])
            out = json.loads(
                merge_image_tool.invoke(
                    {
                        "image_path1": p1,
                        "image_path2": p2,
                        "instruction": instruction,
                    }
                )
            )

        # 情况2：单图编辑
        elif _has_real_file(file):
            p = _save_upload_file(file, tmp_dir, ".png")
            tmp_paths.append(p)
            out = json.loads(
                edit_image_tool.invoke(
                    {
                        "image_path": p,
                        "instruction": instruction,
                    }
                )
            )
        else:
            return {"success": False, "error": "请至少上传一张图片"}

        # 清理临时文件
        for tmp_path in tmp_paths:
            try:
                os.remove(tmp_path)
            except:
                pass

        if not isinstance(out, dict):
            return {"success": False, "error": "模型返回结果格式不正确"}

        if not out.get("success"):
            return {
                "success": False,
                "error": out.get("error", "图片处理失败"),
            }

        url = out.get("url", "")
        if not url:
            return {"success": False, "error": "模型未返回图片地址"}

        return {"success": True, "url": url}

    except Exception as e:
        print(f"执行skill异常{e}")
        return {"success": False, "error": f"执行 skill 失败: {e}"}

# 定义操作图片（编辑图片+合并图片）的接口路由
@app.post("/api/skill/image")
async def skill_image_api(instruction:str=Form(...),file:UploadFile=File(None),file1:UploadFile=File(None),file2:UploadFile=File(None),):
    try:
        out=await skill_image(instruction, file, file1, file2)
        if not out.get("success"):
            raise HTTPException(status_code=500, detail=out)
        return out
    except Exception as e:
        print(f"调用skill错误{e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail={"success":False, "error":str(e)}
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """启动时自动建表。"""
    Base.metadata.create_all(bind=engine)


app.include_router(user_router)
app.include_router(file_router)
app.include_router(record_router)
app.include_router(rag_router)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(settings.upload_dir)), name="uploads")


@app.get("/health")
def health() -> dict[str, str]:
    """健康检查接口。"""
    return {"status": "ok"}
#服务启动函数
if __name__=="__main__":
    print(" AI服务启动成功！")
    uvicorn.run(app,host="0.0.0.0",port=5000)
