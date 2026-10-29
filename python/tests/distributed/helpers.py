from core.distributed.contracts import DistributedRunRequest, RunOperation


def spec(request_id="r1", question="复习"):
    return DistributedRunRequest(
        learner_id="student",
        request_id=request_id,
        operation=RunOperation.LEARNING_TASK,
        payload={
            "learner_id": "student",
            "request_id": request_id,
            "knowledge_id": "grammar_tenses",
            "question": question,
        },
    )
