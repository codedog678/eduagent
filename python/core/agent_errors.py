"""委派边界的稳定失败码；不携带供应商响应或原始异常文本。"""


class AgentExecutionError(ValueError):
    def __init__(self, code, cause_type=None, details=None):
        super().__init__(code)
        self.code = code
        self.cause_type = cause_type
        self.details = details or []
