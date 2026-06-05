from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import html


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "doc" / "EduAgent系统设计文档.docx"


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def run_props(font_size: int = 21, bold: bool = False, color: str | None = None) -> str:
    parts = [
        '<w:rFonts w:ascii="SimSun" w:eastAsia="SimSun" w:hAnsi="SimSun"/>',
        f'<w:sz w:val="{font_size}"/>',
    ]
    if bold:
        parts.append("<w:b/>")
    if color:
        parts.append(f'<w:color w:val="{color}"/>')
    return f"<w:rPr>{''.join(parts)}</w:rPr>"


def para(text: str = "", style: str | None = None, align: str | None = None, size: int = 21,
         bold: bool = False, color: str | None = None, spacing_after: int = 120) -> str:
    ppr = []
    if style:
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    ppr.append(f'<w:spacing w:after="{spacing_after}" w:line="360" w:lineRule="auto"/>')
    ppr_xml = f"<w:pPr>{''.join(ppr)}</w:pPr>"
    if not text:
        return f"<w:p>{ppr_xml}</w:p>"
    return (
        f"<w:p>{ppr_xml}<w:r>{run_props(size, bold, color)}"
        f"<w:t xml:space=\"preserve\">{esc(text)}</w:t></w:r></w:p>"
    )


def bullet(text: str) -> str:
    return para("• " + text, size=21, spacing_after=60)


def page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def cell(text: str, width: int = 2400, shade: str | None = None, bold: bool = False) -> str:
    tcpr = [f'<w:tcW w:w="{width}" w:type="dxa"/>']
    if shade:
        tcpr.append(f'<w:shd w:fill="{shade}"/>')
    return (
        f"<w:tc><w:tcPr>{''.join(tcpr)}</w:tcPr>"
        f"{para(text, size=19, bold=bold, spacing_after=0)}</w:tc>"
    )


def table(rows: list[list[str]], widths: list[int] | None = None) -> str:
    if not rows:
        return ""
    widths = widths or [int(9000 / len(rows[0]))] * len(rows[0])
    xml = [
        '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/>'
        '<w:tblW w:w="0" w:type="auto"/>'
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:color="D9E2F3"/>'
        '<w:left w:val="single" w:sz="4" w:color="D9E2F3"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="D9E2F3"/>'
        '<w:right w:val="single" w:sz="4" w:color="D9E2F3"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="D9E2F3"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="D9E2F3"/>'
        '</w:tblBorders></w:tblPr>'
    ]
    for row_index, row in enumerate(rows):
        xml.append("<w:tr>")
        for col_index, value in enumerate(row):
            xml.append(cell(value, widths[col_index], "EAF2FF" if row_index == 0 else None, row_index == 0))
        xml.append("</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml) + para("", spacing_after=80)


def placeholder(title: str, desc: str) -> str:
    return table(
        [
            [title],
            [desc + "\n截图后可直接替换此占位区域。"],
        ],
        [9000],
    )


def document_body() -> str:
    parts: list[str] = []
    parts.append(para("EduAgent 系统设计文档", align="center", size=36, bold=True, spacing_after=260))
    parts.append(para("多Agent智能教育与个性化学习系统", align="center", size=26, color="1D4ED8", spacing_after=300))
    parts.append(para("课程设计/软件工程设计文档", align="center", size=22, spacing_after=160))
    parts.append(para(f"生成日期：{datetime.now().strftime('%Y年%m月%d日')}", align="center", size=20))
    parts.append(para("项目路径：eduagent", align="center", size=20))
    parts.append(page_break())

    parts.append(para("目录", "Heading1"))
    for item in [
        "1 项目概述", "2 需求分析", "3 系统总体架构", "4 主要界面设计", "5 后端接口与数据流设计",
        "6 EventBus 事件总线设计", "7 Agent 模块设计", "8 核心算法设计", "9 数据库设计",
        "10 部署与运行环境", "11 测试设计", "12 总结与改进方向",
    ]:
        parts.append(para(item, size=21, spacing_after=50))
    parts.append(page_break())

    parts.append(para("1 项目概述", "Heading1"))
    parts.append(para(
        "EduAgent 是一个面向英语学习场景的多Agent智能教育系统。系统通过 AssessmentAgent、TutorAgent、"
        "CurriculumAgent 和 EngagementAgent 的协作，实现知识掌握评估、个性化辅导、学习路径规划和参与度感知。"
        "项目目标是构建一个可运行、可测试、可演示的智能教育原型系统，用工程方式验证多Agent协作与教育算法融合的可行性。"
    ))
    parts.append(table([
        ["项目要素", "说明"],
        ["系统名称", "EduAgent 多Agent智能教育与个性化学习系统"],
        ["应用场景", "英语知识点练习、测验反馈、导师问答、复习提醒和学习分析"],
        ["核心特点", "事件驱动 Mesh 架构、四大 AI Agent、BKT/SM-2/知识图谱、WebSocket 实时反馈"],
        ["前后端结构", "React + TypeScript 前端，FastAPI + PostgreSQL 后端"],
    ], [2500, 6500]))

    parts.append(para("2 需求分析", "Heading1"))
    parts.append(para("2.1 功能需求", "Heading2"))
    for text in [
        "学习者能够选择英语知识点，生成测验题目并提交答案。",
        "系统能够判断答题正误，并给出评价、正确答案和解释。",
        "系统能够根据答题记录更新知识点掌握度，识别薄弱点。",
        "系统能够提供导师式问答和渐进式提示。",
        "系统能够根据知识图谱推荐下一学习主题，根据 SM-2 算法安排复习。",
        "系统能够展示学习统计、知识掌握分布、薄弱知识点和近期学习曲线。",
        "前端能够通过 WebSocket 实时接收各 Agent 的事件反馈。",
    ]:
        parts.append(bullet(text))
    parts.append(para("2.2 非功能需求", "Heading2"))
    parts.append(table([
        ["需求类型", "设计说明"],
        ["可用性", "无 LLM API Key 时自动降级为本地模板模式，保证系统可演示"],
        ["可扩展性", "新增 Agent 只需订阅事件类型，不需要改动现有 Agent"],
        ["可维护性", "前端、API、Agent、算法、数据库分层清晰"],
        ["实时性", "WebSocket 推送事件流，使学习反馈及时展示"],
        ["可测试性", "后端包含 API、BKT、Agent、EventBus、知识图谱等测试模块"],
    ], [2400, 6600]))

    parts.append(para("3 系统总体架构", "Heading1"))
    parts.append(para(
        "系统采用前后端分离和事件驱动 Mesh 架构。用户在 React 前端完成测验或提问，FastAPI 后端接收请求后由 "
        "Orchestrator 发布根事件，EventBus 将事件分发给各 Agent。各 Agent 独立处理后再发布结果事件，最终由后端聚合为一次完整交互，"
        "并通过 REST 和 WebSocket 返回给前端。"
    ))
    parts.append(table([
        ["层次", "组成", "职责"],
        ["表现层", "React、TypeScript、Vite、Nginx", "学习界面、分析仪表板、事件流展示、复习提醒"],
        ["接口层", "FastAPI REST API、WebSocket", "处理测验、问答、进度、分析、复习计划等请求"],
        ["智能协作层", "Orchestrator、EventBus、四大 Agent", "发布事件、并行处理、聚合反馈"],
        ["算法层", "BKT、SM-2、知识图谱、LLM Service", "学习者建模、复习调度、路径推荐、自然语言反馈"],
        ["数据层", "PostgreSQL、SQLAlchemy async", "持久化学习者、掌握状态、学习记录、事件日志和 Agent 状态"],
    ], [1800, 3300, 3900]))
    parts.append(para("系统逻辑结构示意：", "Heading2"))
    parts.append(para(
        "浏览器 → React 前端 → REST/WebSocket → FastAPI 后端 → EventBus → Assessment/Tutor/Curriculum/Engagement Agent → PostgreSQL/LLM Service",
        size=20,
        color="1D4ED8",
    ))

    parts.append(para("4 主要界面设计", "Heading1"))
    parts.append(para(
        "系统前端主要由学习流程页、交互反馈区、实时事件流、复习提醒组件和学习分析仪表板组成。以下位置用于插入老师要求的系统主要界面截图。"
    ))
    parts.append(para("4.1 学习主界面", "Heading2"))
    parts.append(placeholder("图4-1 学习主界面截图", "建议截图内容：顶部系统标题、WebSocket 状态、Learning Flow 标签页、知识点选择器、Quiz Practice、Ask the Tutor、Review Queue。"))
    parts.append(para("4.2 答题反馈与导师回复界面", "Heading2"))
    parts.append(placeholder("图4-2 答题反馈与导师回复截图", "建议截图内容：提交答案后的 Evaluation、Tutor Response、Teaching Decision、Review Snapshot、Suggested Next Topic。"))
    parts.append(para("4.3 实时事件流界面", "Heading2"))
    parts.append(placeholder("图4-3 Agent 事件流截图", "建议截图内容：Interaction Feed 中按 Batch 分组的 Assessment、Tutor、Curriculum、Engagement 事件卡片。"))
    parts.append(para("4.4 学习分析仪表板", "Heading2"))
    parts.append(placeholder("图4-4 Analytics 仪表板截图", "建议截图内容：Total Questions、Accuracy、Study Time、Hints Used、Knowledge Distribution、Weak Points、Recent Learning Curve。"))
    parts.append(para("4.5 API 文档界面", "Heading2"))
    parts.append(placeholder("图4-5 FastAPI Swagger 接口文档截图", "建议访问 http://localhost:8888/docs，截图展示主要 API 分组和接口列表。"))

    parts.append(para("5 后端接口与数据流设计", "Heading1"))
    parts.append(table([
        ["接口", "方法", "功能"],
        ["/api/health", "GET", "系统健康检查，包含 LLM 状态"],
        ["/api/demo/init", "POST", "初始化演示学习者数据"],
        ["/api/quiz/generate", "POST", "按知识点生成测验题目"],
        ["/api/quiz/answer", "POST", "提交测验答案并触发多 Agent 评估"],
        ["/api/question", "POST", "向导师 Agent 提问"],
        ["/api/progress/{learner_id}", "GET", "获取学习者进度"],
        ["/api/analytics/{learner_id}", "GET", "获取学习分析数据"],
        ["/api/review-schedule/{learner_id}", "GET", "获取复习计划和遗忘风险"],
        ["/ws/{learner_id}", "WebSocket", "实时推送 Agent 事件流"],
    ], [2600, 1300, 5100]))
    parts.append(para("一次完整学习交互的数据流：", "Heading2"))
    for text in [
        "前端调用 /api/quiz/generate 生成题目，学习者选择答案。",
        "前端调用 /api/quiz/answer 提交答案、正确答案、知识点和答题耗时。",
        "Orchestrator 发布 STUDENT_SUBMISSION 根事件并生成 correlation_id。",
        "AssessmentAgent 更新 BKT 掌握度并发布 MASTERY_UPDATED、ASSESSMENT_COMPLETE。",
        "TutorAgent 根据评估结果生成教学反馈或提示。",
        "CurriculumAgent 更新复习计划并推荐下一知识点。",
        "EngagementAgent 分析学习状态，必要时发布鼓励或节奏调整事件。",
        "后端聚合事件结果返回前端，WebSocket 同步推送实时事件。",
    ]:
        parts.append(bullet(text))

    parts.append(para("6 EventBus 事件总线设计", "Heading1"))
    parts.append(para(
        "EventBus 是系统中 Agent 协作的核心通信机制。它采用发布-订阅模式，Agent 不直接调用彼此，而是发布事件、订阅事件并自主响应。"
        "这种设计降低了模块耦合度，便于新增 Agent 和排查事件链路。"
    ))
    parts.append(table([
        ["机制", "说明"],
        ["发布-订阅", "事件发布后，所有订阅该事件类型的 Agent 并行处理"],
        ["异常隔离", "某个 Agent 处理失败不会影响其他订阅者继续执行"],
        ["关联链追踪", "同一次学生操作产生的事件共享 correlation_id，便于回溯"],
        ["事件溯源", "事件可写入 event_logs 表，支持审计、调试和回放"],
        ["内存限制", "内存事件历史保留最近 1000 条，避免无限增长"],
    ], [2300, 6700]))

    parts.append(para("7 Agent 模块设计", "Heading1"))
    parts.append(table([
        ["Agent", "订阅事件", "主要职责", "发布事件"],
        ["AssessmentAgent", "STUDENT_SUBMISSION", "基于 BKT 更新掌握度，分析错误类型，识别薄弱知识点", "MASTERY_UPDATED、WEAKNESS_DETECTED、ASSESSMENT_COMPLETE"],
        ["TutorAgent", "ASSESSMENT_COMPLETE、STUDENT_QUESTION、STUDENT_MESSAGE、ENGAGEMENT_ALERT", "生成导师回复、三级提示、苏格拉底式引导和问答", "TEACHING_RESPONSE、HINT_PROVIDED"],
        ["CurriculumAgent", "MASTERY_UPDATED、WEAKNESS_DETECTED、PACE_ADJUSTMENT", "使用知识图谱和 SM-2 规划学习路径与复习计划", "NEXT_TOPIC、REVIEW_SCHEDULED、REVIEW_REMINDER"],
        ["EngagementAgent", "STUDENT_SUBMISSION、ASSESSMENT_COMPLETE、STUDENT_MESSAGE", "检测专注、困难、挫败、无聊、疲劳、空闲等状态并触发干预", "ENGAGEMENT_ALERT、ENCOURAGEMENT、PACE_ADJUSTMENT"],
    ], [1700, 2600, 3500, 3200]))

    parts.append(para("8 核心算法设计", "Heading1"))
    parts.append(para("8.1 BKT 贝叶斯知识追踪", "Heading2"))
    parts.append(para(
        "BKT 将学习者对某个知识点的掌握状态建模为概率 P(L)。系统根据每次答题正误，通过贝叶斯公式更新掌握概率，"
        "并结合 Beta 分布记录成功与失败次数。项目中还做了产品优化：答错时不增加学习转移概率，避免出现“答错反而掌握度提升”的反直觉情况。"
    ))
    parts.append(para("8.2 SM-2 间隔重复", "Heading2"))
    parts.append(para(
        "SM-2 根据回答质量调整复习间隔和难度因子 EF。答得越好，下次复习间隔越长；答得较差，复习间隔重置为较短时间。"
        "系统将 BKT 的 mastery 转换为 quality，用于驱动复习计划。"
    ))
    parts.append(para("8.3 知识图谱 DAG", "Heading2"))
    parts.append(para(
        "知识图谱以有向无环图表示英语知识点之间的前置依赖关系。系统通过拓扑排序确定整体学习顺序，"
        "通过 get_ready_nodes() 推荐当前前置条件已满足、适合继续学习的知识点。"
    ))
    parts.append(table([
        ["算法", "输入", "输出", "作用"],
        ["BKT", "知识点、答题正误", "mastery、掌握等级、薄弱点", "判断学生现在掌握了什么"],
        ["SM-2", "知识点、回答质量、复习历史", "next_review、interval_days、EF", "判断什么时候复习"],
        ["知识图谱", "已掌握知识点集合、目标知识点", "就绪节点、学习路径", "判断接下来学什么"],
    ], [1700, 2700, 2700, 2600]))

    parts.append(para("9 数据库设计", "Heading1"))
    parts.append(table([
        ["表名", "主要字段", "说明"],
        ["learners", "learner_id、name、email、metadata", "学习者基础档案"],
        ["knowledge_states", "learner_id、knowledge_id、mastery、alpha、beta、attempts、streak", "知识点掌握状态"],
        ["learning_records", "learner_id、knowledge_id、is_correct、time_spent_seconds、mastery_before、mastery_after", "答题历史"],
        ["review_items", "knowledge_id、easiness_factor、interval_days、repetition、next_review", "SM-2 复习计划"],
        ["event_logs", "event_id、event_type、source、data、correlation_id", "事件溯源日志"],
        ["agent_states", "agent_name、learner_id、state_data", "Agent 运行时状态持久化"],
    ], [2100, 4200, 3300]))

    parts.append(para("10 部署与运行环境", "Heading1"))
    parts.append(para(
        "系统使用 Docker Compose 编排三个服务：PostgreSQL 数据库、FastAPI 后端服务和前端 Nginx 服务。"
        "生产/演示环境访问前端 3000 端口，前端通过 Nginx 将 /api 和 /ws 请求反向代理到 python-api:8888。"
    ))
    parts.append(table([
        ["服务", "端口", "技术", "职责"],
        ["frontend", "3000 → 80", "React 构建产物 + Nginx", "提供静态页面并代理 API/WebSocket"],
        ["python-api", "8888", "FastAPI、Uvicorn", "提供 REST API、WebSocket、Agent 协作逻辑"],
        ["postgres", "5432", "PostgreSQL 16", "持久化学习数据、事件日志和 Agent 状态"],
    ], [2000, 1600, 2600, 3400]))
    parts.append(para("运行命令：docker compose up --build -d", size=20, color="1D4ED8"))

    parts.append(para("11 测试设计", "Heading1"))
    parts.append(table([
        ["测试类型", "测试对象", "说明"],
        ["单元测试", "BKT、知识图谱、EventBus", "验证算法更新、拓扑排序、事件分发等核心逻辑"],
        ["接口测试", "FastAPI 路由", "验证健康检查、测验、提交答案、分析、复习计划等接口"],
        ["集成测试", "多 Agent 协作", "验证一次学生提交能触发评估、辅导、课程和参与度事件"],
        ["前端功能测试", "学习界面和分析界面", "验证题目生成、答案提交、事件展示、复习提醒和分析数据展示"],
    ], [2200, 2800, 4000]))
    parts.append(para("项目中已有 python/tests 与 python/tests/v2 测试目录，可使用 pytest 运行后端测试。", size=21))

    parts.append(para("12 总结与改进方向", "Heading1"))
    parts.append(para(
        "EduAgent 完成了一个较完整的智能教育原型系统：前端能够完成学习交互和数据展示，后端能够通过事件驱动方式协调多个 Agent，"
        "并将 BKT、SM-2、知识图谱等教育技术算法落地到真实交互流程中。系统具备可演示、可扩展、可测试的特点。"
    ))
    parts.append(para("后续可改进方向：", "Heading2"))
    for text in [
        "扩展题库覆盖范围，使 37 个英语知识点都有稳定练习题。",
        "引入更细粒度的学习者画像，实现 BKT 参数个性化。",
        "让遗忘曲线更深入参与复习调度，而不只作为风险提示。",
        "完善 Agent 状态恢复和事件回放机制。",
        "增加更多界面自动化测试和教学效果评估指标。",
    ]:
        parts.append(bullet(text))

    return "".join(parts)


def styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:rPr><w:rFonts w:ascii="SimSun" w:eastAsia="SimSun" w:hAnsi="SimSun"/><w:sz w:val="21"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>
    <w:pPr><w:spacing w:before="240" w:after="160"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="SimHei" w:eastAsia="SimHei" w:hAnsi="SimHei"/><w:b/><w:color w:val="1D4ED8"/><w:sz w:val="30"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>
    <w:pPr><w:spacing w:before="160" w:after="120"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="SimHei" w:eastAsia="SimHei" w:hAnsi="SimHei"/><w:b/><w:color w:val="0F172A"/><w:sz w:val="25"/></w:rPr>
  </w:style>
  <w:style w:type="table" w:default="1" w:styleId="TableGrid">
    <w:name w:val="Table Grid"/>
    <w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4"/><w:left w:val="single" w:sz="4"/><w:bottom w:val="single" w:sz="4"/><w:right w:val="single" w:sz="4"/><w:insideH w:val="single" w:sz="4"/><w:insideV w:val="single" w:sz="4"/></w:tblBorders></w:tblPr>
  </w:style>
</w:styles>"""


def write_docx() -> None:
    body = document_body()
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {body}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1080" w:bottom="1440" w:left="1080" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    core = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>EduAgent 系统设计文档</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>"""
    app = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>Codex</Application>
</Properties>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUT, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/styles.xml", styles_xml())
        zf.writestr("docProps/core.xml", core)
        zf.writestr("docProps/app.xml", app)


if __name__ == "__main__":
    write_docx()
    print(OUT)
