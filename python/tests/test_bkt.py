"""
BKT 算法测试。

测试贝叶斯知识追踪算法和遗忘曲线。
"""

import pytest
from datetime import datetime, timedelta
from core.learner_model import LearnerModel, KnowledgeState, MasteryLevel


class TestBKTAlgorithm:
    """BKT算法测试。"""

    def test_initial_mastery(self):
        """测试初始mastery值。"""
        model = LearnerModel("test_user")
        state = model.get_state("vocab_basic")

        assert state.mastery == 0.1  # 默认初始mastery
        assert state.attempts == 0
        assert state.correct_count == 0
        assert state.streak == 0

    def test_correct_answer_increases_mastery(self):
        """测试答对增加mastery。"""
        model = LearnerModel("test_user")
        initial_mastery = model.get_state("vocab_basic").mastery

        model.update_mastery("vocab_basic", is_correct=True)
        new_mastery = model.get_state("vocab_basic").mastery

        assert new_mastery > initial_mastery
        assert model.get_state("vocab_basic").attempts == 1
        assert model.get_state("vocab_basic").correct_count == 1
        assert model.get_state("vocab_basic").streak == 1

    def test_wrong_answer_decreases_mastery(self):
        """测试答错降低mastery。"""
        model = LearnerModel("test_user")
        initial_mastery = model.get_state("vocab_basic").mastery

        model.update_mastery("vocab_basic", is_correct=False)
        new_mastery = model.get_state("vocab_basic").mastery

        assert new_mastery < initial_mastery
        assert model.get_state("vocab_basic").attempts == 1
        assert model.get_state("vocab_basic").correct_count == 0
        assert model.get_state("vocab_basic").streak == 0

    def test_mastery_level_progression(self):
        """测试mastery等级递进。"""
        model = LearnerModel("test_user")

        # 初始状态
        state = model.get_state("vocab_basic")
        assert state.level == MasteryLevel.NOT_STARTED

        # 答对一次
        initial_mastery = state.mastery
        model.update_mastery("vocab_basic", is_correct=True)
        state = model.get_state("vocab_basic")
        assert state.mastery > initial_mastery
        assert state.level in {
            MasteryLevel.BEGINNER,
            MasteryLevel.DEVELOPING,
            MasteryLevel.PROFICIENT,
            MasteryLevel.MASTERED,
        }

        # 连续答对多次，提升mastery
        for _ in range(10):
            model.update_mastery("vocab_basic", is_correct=True)

        state = model.get_state("vocab_basic")
        assert state.mastery > 0.3  # 应该已经超过0.3

    def test_streak_tracking(self):
        """测试连续答对追踪。"""
        model = LearnerModel("test_user")

        # 连续答对3次
        for _ in range(3):
            model.update_mastery("vocab_basic", is_correct=True)

        state = model.get_state("vocab_basic")
        assert state.streak == 3

        # 答错一次，streak应该重置
        model.update_mastery("vocab_basic", is_correct=False)
        state = model.get_state("vocab_basic")
        assert state.streak == 0

    def test_weak_points_detection(self):
        """测试薄弱知识点检测。"""
        model = LearnerModel("test_user")

        # 创建多个知识点，部分mastery较低
        model.update_mastery("vocab_basic", is_correct=True)
        model.update_mastery("vocab_basic", is_correct=True)
        model.update_mastery("vocab_basic", is_correct=True)

        model.update_mastery("grammar_tenses", is_correct=False)
        model.update_mastery("grammar_tenses", is_correct=False)

        # 获取薄弱知识点
        weak_points = model.get_weak_points(threshold=0.4)

        # grammar_tenses应该在薄弱点列表中
        weak_ids = [wp.knowledge_id for wp in weak_points]
        assert "grammar_tenses" in weak_ids

    def test_overall_progress(self):
        """测试整体进度统计。"""
        model = LearnerModel("test_user")

        # 添加一些学习记录
        model.update_mastery("vocab_basic", is_correct=True)
        model.update_mastery("vocab_basic", is_correct=True)
        model.update_mastery("grammar_tenses", is_correct=False)

        progress = model.get_overall_progress()

        assert progress["total_knowledge_points"] == 2
        assert progress["total_attempts"] == 3
        assert progress["total_correct"] == 2
        assert progress["accuracy"] == 2 / 3

class TestForgettingCurve:
    """遗忘曲线测试。"""

    def test_immediate_retention(self):
        """测试立即复习的保持率。"""
        model = LearnerModel("test_user")
        model.update_mastery("vocab_basic", is_correct=True)
        model.update_mastery("vocab_basic", is_correct=True)

        # 刚学完立即复习，保持率应该很高
        retention = model.get_forgetting_curve("vocab_basic", days_since_last_review=0)
        assert retention > 0.9

    def test_forgetting_over_time(self):
        """测试随时间遗忘。"""
        model = LearnerModel("test_user")
        model.update_mastery("vocab_basic", is_correct=True)

        # 不同时间间隔的保持率
        retention_1day = model.get_forgetting_curve("vocab_basic", days_since_last_review=1)
        retention_7days = model.get_forgetting_curve("vocab_basic", days_since_last_review=7)
        retention_30days = model.get_forgetting_curve("vocab_basic", days_since_last_review=30)

        # 保持率应该随时间递减
        assert retention_1day > retention_7days > retention_30days

    def test_higher_mastery_slower_forgetting(self):
        """测试mastery越高遗忘越慢。"""
        model = LearnerModel("test_user")

        # 创建两个知识点，mastery不同
        # vocab_basic: 高mastery
        for _ in range(10):
            model.update_mastery("vocab_basic", is_correct=True)

        # grammar_tenses: 低mastery
        model.update_mastery("grammar_tenses", is_correct=False)

        # 7天后的保持率
        retention_high = model.get_forgetting_curve("vocab_basic", days_since_last_review=7)
        retention_low = model.get_forgetting_curve("grammar_tenses", days_since_last_review=7)

        # 高mastery应该保持率更高
        assert retention_high > retention_low

    def test_streak_affects_retention(self):
        """测试连续正确次数影响保持率。"""
        model = LearnerModel("test_user")

        # 创建两个知识点，streak不同
        # vocab_basic: 高streak
        for _ in range(5):
            model.update_mastery("vocab_basic", is_correct=True)

        # grammar_tenses: 低streak
        model.update_mastery("grammar_tenses", is_correct=True)
        model.update_mastery("grammar_tenses", is_correct=False)
        model.update_mastery("grammar_tenses", is_correct=True)

        # 7天后的保持率
        retention_high_streak = model.get_forgetting_curve("vocab_basic", days_since_last_review=7)
        retention_low_streak = model.get_forgetting_curve("grammar_tenses", days_since_last_review=7)

        # 高streak应该保持率更高
        assert retention_high_streak > retention_low_streak
