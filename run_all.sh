#!/bin/bash

TOTAL_START=$(date +%s%3N)
CMD_NUM=0
TOTAL_CMDS=18

run_cmd() {
    CMD_NUM=$((CMD_NUM + 1))
    local CMD="$*"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  [$CMD_NUM/$TOTAL_CMDS] Running: $CMD"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    local START=$(date +%s%3N)

    eval "$CMD"
    local EXIT_CODE=$?

    local END=$(date +%s%3N)
    local ELAPSED=$(echo "scale=2; ($END - $START) / 1000" | bc)
    echo ""
    echo "  Total elapsed time: ${ELAPSED} seconds  (exit code: $EXIT_CODE)"

    if [ $EXIT_CODE -ne 0 ]; then
        echo "  ⚠️  Command exited with non-zero status: $EXIT_CODE"
    fi
}

run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1154179361 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1154179361 --model codex --codex-model gpt-6-astra
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1154179361 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1336005533 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1336005533 --model codex --codex-model gpt-6-astra
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1336005533 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1348102534 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1348102534 --model codex --codex-model gpt-6-astra
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1348102534 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1701725770 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1701725770 --model codex --codex-model gpt-6-astra
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1701725770 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1845281685 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1845281685 --model codex --codex-model gpt-6-astra
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1845281685 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1163893375 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1163893375 --model codex --codex-model gpt-6-astra
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1163893375 --model qwen

TOTAL_END=$(date +%s%3N)
TOTAL_ELAPSED=$(echo "scale=2; ($TOTAL_END - $TOTAL_START) / 1000" | bc)
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  ✅ All $TOTAL_CMDS commands completed."
echo "  Total elapsed time: ${TOTAL_ELAPSED} seconds"
echo "════════════════════════════════════════════════════════════════════"

# Desktop notification (falls back to terminal bell if notify-send unavailable)
if command -v notify-send &> /dev/null; then
    notify-send "Benchmark finished" "All $TOTAL_CMDS commands completed at $(date). Elapsed: ${TOTAL_ELAPSED}s"
else
    echo -e "\a"
fi
