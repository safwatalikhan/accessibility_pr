#!/bin/bash

# Run all benchmark commands sequentially, waiting for each to finish before starting the next.

TOTAL_START=$(date +%s%3N)
CMD_NUM=0
TOTAL_CMDS=48

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

run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_909833569 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_909833569 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_918881766 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_918881766 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cylc_cylc-ui/issues/PR_579637170 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cylc_cylc-ui/issues/PR_579637170 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2127762492 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2127762492 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2385490709 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2385490709 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/gympass_yoga/issues/PR_2756476017 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/gympass_yoga/issues/PR_2756476017 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/gympass_yoga/issues/PR_2921068887 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/gympass_yoga/issues/PR_2921068887 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/inclusive-design_wecount.inclusivedesign.ca/issues/PR_2179910857 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/inclusive-design_wecount.inclusivedesign.ca/issues/PR_2179910857 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1102620289 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1102620289 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1134423997 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1134423997 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1213690009 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1213690009 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_321967871 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_321967871 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_321982888 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_321982888 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_328812522 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_328812522 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1329807888 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1329807888 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1335734686 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1335734686 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1348102534 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1348102534 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1701725770 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1701725770 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_795221767 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_795221767 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_1515922121 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_1515922121 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_254146241 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_254146241 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_580066898 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_580066898 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_714819179 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_714819179 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_231402510 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_231402510 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_891146471 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_891146471 --model codex

TOTAL_END=$(date +%s%3N)
TOTAL_ELAPSED=$(echo "scale=2; ($TOTAL_END - $TOTAL_START) / 1000" | bc)
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  ✅ All $TOTAL_CMDS commands completed."
echo "  Total elapsed time: ${TOTAL_ELAPSED} seconds"
echo "════════════════════════════════════════════════════════════════════"