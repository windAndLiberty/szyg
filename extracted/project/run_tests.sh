#!/usr/bin/env bash
#
# 「域灵」数字员工系统 — 分层测试运行脚本
#
# 用法:
#   ./run_tests.sh              # 运行全部测试 + 覆盖率报告
#   ./run_tests.sh unit         # 仅单元测试
#   ./run_tests.sh integration  # 仅集成测试
#   ./run_tests.sh e2e          # 仅端到端/契约测试
#   ./run_tests.sh coverage     # 运行全部 + HTML覆盖率报告
#   ./run_tests.sh quick        # 快速单元测试（无覆盖率）
#
# 退出码:
#   0 — 全部通过
#   1 — 有失败

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 颜色输出 ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

log_section() {
    echo ""
    echo -e "${BOLD}━━━ $1 ━━━${NC}"
}

log_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

log_fail() {
    echo -e "${RED}✗${NC} $1"
}

log_info() {
    echo -e "${YELLOW}→${NC} $1"
}

# ── 确保 venv 存在 ──────────────────────────────────────────────────────────
ensure_venv() {
    if [ ! -f ".venv/bin/python" ]; then
        log_info "创建虚拟环境..."
        uv venv --python 3.12 --clear
        uv pip install -e ".[dev]"
        log_pass "虚拟环境就绪"
    fi
}

PYTEST=".venv/bin/python -m pytest"
COV_OPTS="--cov=yuling --cov-report=term-missing"
UNIT_DIR="tests/unit"
INTEGRATION_DIR="tests/integration"
MOCK_TESTS="tests/test_config.py tests/test_memory.py tests/test_skill_registry.py tests/test_model_router.py tests/test_mcp.py tests/test_integrations.py tests/test_api.py tests/test_wechaty.py tests/test_e2e.py"

# ── 解析参数 ────────────────────────────────────────────────────────────────
MODE="${1:-all}"

case "$MODE" in
    quick)
        log_section "快速单元测试（无覆盖率）"
        $PYTEST $UNIT_DIR -v --tb=short -q
        ;;

    unit)
        log_section "第1层：真单元测试"
        $PYTEST $UNIT_DIR -v --tb=short $COV_OPTS
        ;;

    mock)
        log_section "第2层：Mock 契约测试"
        $PYTEST $MOCK_TESTS -v --tb=short
        ;;

    integration)
        log_section "第3层：集成冒烟测试"
        $PYTEST $INTEGRATION_DIR -v --tb=short $COV_OPTS
        ;;

    e2e)
        log_section "端到端/契约测试"
        $PYTEST $MOCK_TESTS -v --tb=short
        ;;

    coverage)
        log_section "全量测试 + HTML 覆盖率报告"
        $PYTEST tests/ $COV_OPTS --cov-report=html \
            --cov-report=term \
            --no-header -q
        log_info "HTML 报告: ${SCRIPT_DIR}/htmlcov/index.html"
        ;;

    real)
        log_section "真实服务集成测试（需要 Ollama/ComfyUI 运行）"
        $PYTEST tests/integration/test_real_services.py -v --tb=short
        ;;

    all)
        log_section "全量分层测试 + 覆盖率"
        log_info "第1层: 真单元测试"
        $PYTEST $UNIT_DIR -v --tb=short --no-header -q

        log_info "第2层: Mock 契约测试"
        $PYTEST $MOCK_TESTS -v --tb=short --no-header -q

        log_info "第3层: 集成冒烟测试"
        $PYTEST $INTEGRATION_DIR -v --tb=short --no-header -q

        log_section "全量覆盖率汇总"
        $PYTEST tests/ $COV_OPTS --no-header -q

        # 提取覆盖率摘要
        COVERAGE_LINE=$($PYTEST tests/ --cov=yuling --cov-report=term --no-header -q 2>&1 \
            | grep "^TOTAL" | awk '{print $NF}')
        log_info "总体覆盖率: ${COVERAGE_LINE}"

        echo ""
        echo -e "${GREEN}${BOLD}✓ 全部测试通过${NC}"
        ;;

    *)
        echo "用法: $0 {quick|unit|mock|integration|e2e|coverage|all}"
        echo ""
        echo "  quick       快速单元测试（无覆盖率）"
        echo "  unit        第1层: 真单元测试 + 覆盖率"
        echo "  mock        第2层: Mock 契约测试"
        echo "  integration 第3层: 集成冒烟测试"
        echo "  e2e         端到端测试"
        echo "  coverage    全量测试 + HTML 覆盖率报告"
        echo "  all         全量分层测试 + 覆盖率汇总 (默认)"
        exit 1
        ;;
esac

echo ""
